"""CoderService – Code Generation and Unified Diff Agent for Reflexion.

Orchestrates Phase 8 code generation incrementally per file:
1. Validates repository and workspace existence.
2. Iterates over files specified by ImplementationPlan.affected_files and new_files.
3. Loads only the current target file with safety checks (path traversal, binary, size limits).
4. Invokes LLMService for structured single-file generation (SingleFileGenerationResult).
5. Computes standard unified diffs per file on the backend.
6. Invokes lightweight LLM summarization for overall summary & reasoning based on per-file explanations.
7. Assembles and returns backward-compatible CodingResult.
"""

import difflib
import logging
import os
import uuid
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlmodel import Session

from app.models import Repository
from app.prompts.coder_prompt import (
    build_coder_prompt,
    build_coder_summary_prompt,
    build_single_file_coder_prompt,
)
from app.schemas.coder import (
    CodingResult,
    CodingSummaryResult,
    GeneratedFile,
    SingleFileGenerationResult,
)
from app.schemas.planner import ImplementationPlan
from app.schemas.repository import ProjectSummary
from app.services.llm import llm_service, LLMError, LLMValidationError

logger = logging.getLogger("reflexion.services.coder")

# Maximum thresholds for safe file loading
DEFAULT_MAX_FILE_BYTES = 100_000      # 100 KB per file
DEFAULT_MAX_TOTAL_BYTES = 500_000     # 500 KB total across all files


def is_binary_file(file_path: str, chunk_size: int = 1024) -> bool:
    """Check whether a file is binary by inspecting initial byte null bytes."""
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(chunk_size)
            if b"\x00" in chunk:
                return True
    except Exception:
        pass
    return False


def _load_single_file(
    workspace_path: str,
    rel_path: str,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
) -> Tuple[Optional[str], Optional[str]]:
    """Load text content for a single file cleanly with safety checks.

    Returns:
        Tuple[Optional[str], Optional[str]]: (file content or None, warning message or None)
    """
    if not rel_path or not isinstance(rel_path, str):
        return None, None

    workspace_abs = os.path.abspath(workspace_path)
    clean_rel = rel_path.strip().lstrip("/\\")
    target_abs = os.path.abspath(os.path.join(workspace_abs, clean_rel))

    # Security check: path traversal guard
    if not target_abs.startswith(workspace_abs):
        msg = f"Path traversal attempt blocked for requested file: '{rel_path}'"
        logger.warning(msg)
        return None, msg

    if not os.path.exists(target_abs):
        msg = f"Affected file '{clean_rel}' does not exist locally (will be treated as new file if created)."
        logger.info(msg)
        return None, None

    if os.path.isdir(target_abs):
        msg = f"Requested path '{clean_rel}' is a directory, skipping content read."
        logger.info(msg)
        return None, msg

    if is_binary_file(target_abs):
        msg = f"File '{clean_rel}' appears to be binary, skipping text content read."
        logger.info(msg)
        return None, msg

    file_size = os.path.getsize(target_abs)
    warning = None
    if file_size > max_file_bytes:
        warning = f"File '{clean_rel}' size ({file_size} bytes) exceeds limit ({max_file_bytes} bytes). Content truncated."
        logger.warning(warning)

    try:
        with open(target_abs, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(max_file_bytes)
            logger.info(f"Successfully loaded file '{clean_rel}' ({len(content)} chars)")
            return content, warning
    except Exception as e:
        msg = f"Failed to read file '{clean_rel}': {e}"
        logger.error(msg)
        return None, msg


def load_relevant_files(
    workspace_path: str,
    affected_files: List[str],
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
) -> Tuple[Dict[str, str], List[str]]:
    """Load text content for files specified in affected_files list.

    Args:
        workspace_path: Local filesystem workspace directory.
        affected_files: Relative paths requested by ImplementationPlan.
        max_file_bytes: Maximum size in bytes allowed per single file.
        max_total_bytes: Maximum total bytes allowed across all loaded files.

    Returns:
        Tuple[Dict[str, str], List[str]]: (map of rel_path -> content, list of warnings)
    """
    loaded_files: Dict[str, str] = {}
    warnings: List[str] = []
    accumulated_bytes = 0

    workspace_abs = os.path.abspath(workspace_path)

    for rel_path in affected_files:
        if not rel_path or not isinstance(rel_path, str):
            continue

        clean_rel = rel_path.strip().lstrip("/\\")
        target_abs = os.path.abspath(os.path.join(workspace_abs, clean_rel))

        if not target_abs.startswith(workspace_abs):
            msg = f"Path traversal attempt blocked for requested file: '{rel_path}'"
            logger.warning(msg)
            warnings.append(msg)
            continue

        if not os.path.exists(target_abs):
            msg = f"Affected file '{clean_rel}' does not exist locally (will be treated as new file if created)."
            logger.info(msg)
            warnings.append(msg)
            continue

        if os.path.isdir(target_abs):
            msg = f"Requested path '{clean_rel}' is a directory, skipping content read."
            logger.info(msg)
            warnings.append(msg)
            continue

        if is_binary_file(target_abs):
            msg = f"File '{clean_rel}' appears to be binary, skipping text content read."
            logger.info(msg)
            warnings.append(msg)
            continue

        file_size = os.path.getsize(target_abs)
        if file_size > max_file_bytes:
            msg = f"File '{clean_rel}' size ({file_size} bytes) exceeds limit ({max_file_bytes} bytes). Content truncated."
            logger.warning(msg)
            warnings.append(msg)

        if accumulated_bytes + file_size > max_total_bytes:
            msg = f"Total file size budget ({max_total_bytes} bytes) reached. Skipping further file reads."
            logger.warning(msg)
            warnings.append(msg)
            break

        try:
            with open(target_abs, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(max_file_bytes)
                loaded_files[clean_rel] = content
                accumulated_bytes += len(content.encode("utf-8"))
                logger.info(f"Successfully loaded file '{clean_rel}' ({len(content)} chars)")
        except Exception as e:
            msg = f"Failed to read file '{clean_rel}': {e}"
            logger.error(msg)
            warnings.append(msg)

    return loaded_files, warnings


def generate_unified_diff(
    path: str,
    original_content: Optional[str],
    generated_content: Optional[str],
    change_type: str,
) -> str:
    """Generate a standard unified diff patch string.

    Args:
        path: Relative file path.
        original_content: Prior file content (or None / empty if created).
        generated_content: New file content (or None / empty if deleted).
        change_type: 'create', 'modify', or 'delete'.

    Returns:
        Unified diff string.
    """
    orig_lines = (original_content or "").splitlines(keepends=True)
    gen_lines = (generated_content or "").splitlines(keepends=True)

    if change_type == "create":
        from_file = "/dev/null"
        to_file = f"b/{path}"
    elif change_type == "delete":
        from_file = f"a/{path}"
        to_file = "/dev/null"
    else:
        from_file = f"a/{path}"
        to_file = f"b/{path}"

    diff_lines = list(
        difflib.unified_diff(
            orig_lines,
            gen_lines,
            fromfile=from_file,
            tofile=to_file,
        )
    )

    if not diff_lines:
        return f"--- {from_file}\n+++ {to_file}\n@@ -0,0 +0,0 @@ (No changes detected)\n"

    return "".join(diff_lines)


def _generate_single_file(
    project_summary: ProjectSummary,
    implementation_plan: ImplementationPlan,
    file_path: str,
    original_content: Optional[str] = None,
    is_new_file: bool = False,
    user_prompt_override: Optional[str] = None,
) -> GeneratedFile:
    """Generate code changes for a single file using LLMService.

    Args:
        project_summary: High-level repository structure context.
        implementation_plan: Architectural plan.
        file_path: Relative path of file to generate.
        original_content: Prior content if existing file.
        is_new_file: True if new file being created.
        user_prompt_override: Optional extra instructions.

    Returns:
        GeneratedFile object with computed diff and original content attached.
    """
    sys_inst, user_prompt = build_single_file_coder_prompt(
        project_summary=project_summary,
        implementation_plan=implementation_plan,
        file_path=file_path,
        original_content=original_content,
        is_new_file=is_new_file,
        user_prompt_override=user_prompt_override,
    )

    result = llm_service.generate_json(
        prompt=user_prompt,
        response_schema=SingleFileGenerationResult,
        system_instruction=sys_inst,
        temperature=0.2,
    )

    diff_str = generate_unified_diff(
        path=file_path,
        original_content=original_content,
        generated_content=result.generated_content,
        change_type=result.change_type,
    )

    return GeneratedFile(
        path=file_path,
        change_type=result.change_type,
        original_content=original_content,
        generated_content=result.generated_content,
        explanation=result.explanation,
        unified_diff=diff_str,
    )


def _generate_overall_summary(
    implementation_plan: ImplementationPlan,
    generated_files: List[GeneratedFile],
) -> CodingSummaryResult:
    """Invoke LLM to produce cohesive high-level summary and reasoning based on goal and per-file explanations.

    Args:
        implementation_plan: Plan containing goal and summary.
        generated_files: List of generated file objects.

    Returns:
        CodingSummaryResult containing summary and reasoning strings.
    """
    if not generated_files:
        return CodingSummaryResult(
            summary="No code changes were generated.",
            reasoning="The implementation plan did not specify any target files to modify or create.",
        )

    file_explanations = [
        {
            "path": gf.path,
            "change_type": gf.change_type,
            "explanation": gf.explanation,
        }
        for gf in generated_files
    ]

    sys_inst, user_prompt = build_coder_summary_prompt(
        goal=implementation_plan.goal,
        plan_summary=implementation_plan.summary,
        file_explanations=file_explanations,
    )

    try:
        return llm_service.generate_json(
            prompt=user_prompt,
            response_schema=CodingSummaryResult,
            system_instruction=sys_inst,
            temperature=0.2,
        )
    except Exception as e:
        logger.warning(f"Final LLM summarization call failed ({e}). Falling back to backend synthesis.")
        summary_str = f"Implemented plan '{implementation_plan.goal}': updated {len(generated_files)} file(s)."
        reasoning_str = f"Successfully generated changes for {', '.join(gf.path for gf in generated_files)} based on plan."
        return CodingSummaryResult(summary=summary_str, reasoning=reasoning_str)


class CoderService:
    """Service responsible for orchestrating incremental code generation and diff computation."""

    def generate_code(
        self,
        repository_id: Optional[uuid.UUID] = None,
        session: Optional[Session] = None,
        implementation_plan: Optional[ImplementationPlan] = None,
        user_prompt_override: Optional[str] = None,
        project_summary: Optional[ProjectSummary] = None,
        reflection_result: Optional[Any] = None,
    ) -> CodingResult:
        """Generate implementation code changes based on an ImplementationPlan.

        Can be invoked either via DB context (repository_id, session) or directly
        with in-memory schemas (project_summary, implementation_plan). Completely
        filesystem agnostic.
        """
        repo = None
        repo_local_path = None

        if project_summary is None or implementation_plan is None:
            if not repository_id or not session:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Either (project_summary, implementation_plan) or (repository_id, session) must be provided.",
                )
            logger.info(f"Initiating code generation request for repository_id='{repository_id}'")
            repo = session.get(Repository, repository_id)
            if not repo:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Repository with ID '{repository_id}' not found.",
                )
            if not repo.project_summary:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Repository workspace has not been analyzed yet.",
                )
            project_summary = ProjectSummary.model_validate(repo.project_summary)
            plan = implementation_plan
            if not plan:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No ImplementationPlan provided.",
                )
            repo_local_path = repo.local_path
        else:
            plan = implementation_plan

        # Combine reflection_result guidance into prompt override if provided
        prompt_override = user_prompt_override or ""
        if reflection_result is not None:
            repair_notes = (
                f"\nREPAIR GUIDANCE (Previous attempt failed with {reflection_result.failure_category}):\n"
                f"Root Cause: {reflection_result.root_cause}\n"
                f"Recommendations:\n"
                + "\n".join(f"- {r}" for r in reflection_result.recommendations)
            )
            prompt_override = (prompt_override + "\n" + repair_notes).strip()

        # Resolve target files based on retry_scope if reflection_result provided
        new_files_set = set(plan.new_files or [])
        affected_files_list = plan.affected_files or []

        if reflection_result is not None and getattr(reflection_result, "retry_scope", None):
            from app.schemas.reflector import RetryScope
            scope = reflection_result.retry_scope
            if scope == RetryScope.SINGLE_FILE:
                if reflection_result.affected_files:
                    affected_files_list = reflection_result.affected_files[:1]
                    new_files_set = {f for f in affected_files_list if f in new_files_set}
                elif plan.affected_files:
                    affected_files_list = plan.affected_files[:1]
            elif scope == RetryScope.MULTIPLE_FILES:
                if reflection_result.affected_files:
                    affected_files_list = reflection_result.affected_files
                    new_files_set = {f for f in affected_files_list if f in new_files_set}

        all_target_files: List[Tuple[str, bool]] = []
        seen = set()

        for f in affected_files_list:
            if not f or not isinstance(f, str):
                continue
            clean_f = f.strip().lstrip("/\\")
            if clean_f and clean_f not in seen:
                seen.add(clean_f)
                is_new = clean_f in new_files_set
                all_target_files.append((clean_f, is_new))

        for f in (plan.new_files or []):
            if not f or not isinstance(f, str):
                continue
            clean_f = f.strip().lstrip("/\\")
            if clean_f and clean_f not in seen:
                seen.add(clean_f)
                all_target_files.append((clean_f, True))

        if not all_target_files:
            logger.warning(f"No affected or new files specified in ImplementationPlan for repo '{repository_id}'")
            return CodingResult(
                summary="No code changes requested.",
                generated_files=[],
                unified_diffs={},
                reasoning="ImplementationPlan specified no affected or new files.",
                warnings=["ImplementationPlan contained empty affected_files and new_files lists."],
            )

        logger.info(f"Target files for incremental generation ({len(all_target_files)} files): {[tf[0] for tf in all_target_files]}")

        processed_files: List[GeneratedFile] = []
        diff_map: Dict[str, str] = {}
        all_warnings: List[str] = []

        try:
            # 6. Iterate and generate each file individually
            for rel_path, is_new in all_target_files:
                logger.info(f"Generating code for file '{rel_path}' (is_new={is_new})")
                orig_content = None

                if not is_new and repo_local_path:
                    content, warn = _load_single_file(repo_local_path, rel_path)
                    orig_content = content
                    if warn:
                        all_warnings.append(warn)

                    abs_p = os.path.abspath(os.path.join(repo_local_path, rel_path))
                    if not os.path.exists(abs_p):
                        is_new = True

                gen_file = _generate_single_file(
                    project_summary=project_summary,
                    implementation_plan=plan,
                    file_path=rel_path,
                    original_content=orig_content,
                    is_new_file=is_new,
                    user_prompt_override=prompt_override,
                )
                processed_files.append(gen_file)
                if gen_file.unified_diff:
                    diff_map[rel_path] = gen_file.unified_diff

            # 7. Final lightweight LLM summarization call
            repo_name = repo.full_name if repo else project_summary.project_name
            logger.info(f"Invoking final LLM summarization call for repository '{repo_name}'")
            summary_result = _generate_overall_summary(plan, processed_files)

            final_result = CodingResult(
                summary=summary_result.summary,
                generated_files=processed_files,
                unified_diffs=diff_map,
                reasoning=summary_result.reasoning,
                warnings=all_warnings,
            )

            repo_id_str = repository_id or (project_summary.project_name if project_summary else "unknown")
            logger.info(
                f"Successfully completed incremental code generation for repository '{repo_id_str}' "
                f"[Files generated: {len(final_result.generated_files)}, Diffs: {len(final_result.unified_diffs)}]"
            )
            return final_result

        except (LLMValidationError, LLMError) as le:
            repo_id_str = repository_id or (project_summary.project_name if project_summary else "unknown")
            logger.error(f"LLM service failure during code generation for repository '{repo_id_str}': {le}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"LLM coder agent failed to generate structured code: {str(le)}",
            )
        except Exception as e:
            repo_id_str = repository_id or (project_summary.project_name if project_summary else "unknown")
            logger.error(f"Unexpected error during code generation for repository '{repo_id_str}': {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An unexpected error occurred while generating code: {str(e)}",
            )


# Global singleton instance
coder_service = CoderService()
