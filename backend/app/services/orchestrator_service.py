"""OrchestratorService – Complete Pipeline Orchestration and Self-Correction Agent for Reflexion (Phase 12).

Sequences execution across independent agents:
    Repository -> RepositoryAnalyzer -> ProjectSummary
               -> Planner -> ImplementationPlan
               -> [Retry Loop (Max N Attempts)]:
                    Coder (filesystem-agnostic code generation)
                    WorkspaceManager (isolated workspace creation & patch application)
                    Tester (workspace validation & test execution)
                    WorkspaceManager (workspace cleanup in try/finally)
                    Reflector (failure analysis & repair guidance if tests fail)
               -> FinalExecutionResult

Strict Boundaries:
- The Orchestrator is the ONLY component that creates, manages, patches, and cleans up workspaces.
- The Coder Agent is completely filesystem-agnostic.
- The Orchestrator alone manages retry decisions, retry limits, and final summary synthesis.
- Individual agents remain completely isolated and unaware of one another.
"""

import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional, Union

from app.prompts.planner_prompt import build_planner_prompt
from app.schemas.coder import CodingResult, GeneratedFile
from app.schemas.orchestrator import FinalExecutionResult, PipelineIteration
from app.schemas.planner import ImplementationPlan
from app.schemas.reflector import ReflectionResult, RetryScope
from app.schemas.repository import ProjectSummary
from app.schemas.tester import TestResult
from app.services.coder_service import coder_service
from app.services.llm import llm_service
from app.services.planner_service import planner_service
from app.services.reflector_service import reflector_service
from app.services.repository_analyzer import repository_analyzer
from app.services.tester_service import tester_service
from app.services.workspace_manager import workspace_manager

logger = logging.getLogger("reflexion.services.orchestrator")

DEFAULT_MAX_REPAIR_ATTEMPTS = 3


def _merge_coding_results(
    previous_result: CodingResult,
    new_result: CodingResult,
) -> CodingResult:
    """Merge newly generated files into previous iteration's generated_files map.

    Ensures that for targeted partial repair iterations (SINGLE_FILE or MULTIPLE_FILES),
    the resulting CodingResult contains the full set of generated/modified files.
    """
    new_file_map: Dict[str, GeneratedFile] = {gf.path: gf for gf in new_result.generated_files}
    merged_files: List[GeneratedFile] = []
    seen_paths = set()

    # Include untouched previous files first
    for gf in previous_result.generated_files:
        if gf.path in new_file_map:
            merged_files.append(new_file_map[gf.path])
            seen_paths.add(gf.path)
        else:
            merged_files.append(gf)
            seen_paths.add(gf.path)

    # Append any brand new files from new_result not present in previous_result
    for gf in new_result.generated_files:
        if gf.path not in seen_paths:
            merged_files.append(gf)
            seen_paths.add(gf.path)

    diff_map = {gf.path: gf.unified_diff for gf in merged_files if gf.unified_diff}

    return CodingResult(
        summary=new_result.summary or previous_result.summary,
        generated_files=merged_files,
        unified_diffs=diff_map,
        reasoning=new_result.reasoning or previous_result.reasoning,
        warnings=list(set(previous_result.warnings + new_result.warnings)),
    )


class OrchestratorService:
    """Service responsible for orchestrating the end-to-end Reflexion agent pipeline."""

    def run_pipeline(
        self,
        repository: Any,
        user_request: Optional[str] = None,
        max_repair_attempts: int = DEFAULT_MAX_REPAIR_ATTEMPTS,
        session: Optional[Any] = None,
    ) -> FinalExecutionResult:
        """Run the autonomous PR pipeline from analysis to testing and self-correction.

        Args:
            repository: Local repository path (str/Path) or DB Repository model instance.
            user_request: Natural language feature request or change instruction.
            max_repair_attempts: Maximum number of retry attempts allowed (default: 3).
            session: Optional SQLModel active database session.

        Returns:
            FinalExecutionResult: Complete execution outcome payload.
        """
        start_time = time.monotonic()
        history: List[PipelineIteration] = []
        logger.info("Initiating OrchestratorService pipeline run")

        try:
            # -------------------------------------------------------------
            # Stage 1: Resolve Repository Path and ProjectSummary
            # -------------------------------------------------------------
            repo_path = None
            project_summary: Optional[ProjectSummary] = None

            if isinstance(repository, (str, bytes, os.PathLike)):
                repo_path = str(repository)
                logger.info(f"Analyzing local repository path: '{repo_path}'")
                project_summary = repository_analyzer.analyze_repository(repo_path)
            elif hasattr(repository, "local_path"):
                repo_path = str(repository.local_path)
                if getattr(repository, "project_summary", None):
                    project_summary = ProjectSummary.model_validate(repository.project_summary)
                else:
                    project_summary = repository_analyzer.analyze_repository(repo_path)
            else:
                repo_path = str(repository)
                project_summary = repository_analyzer.analyze_repository(repo_path)

            logger.info(f"ProjectSummary resolved for '{project_summary.project_name}' ({project_summary.languages})")

            # -------------------------------------------------------------
            # Stage 2: Generate ImplementationPlan (Planner Agent)
            # -------------------------------------------------------------
            user_req = user_request or f"Implement feature changes for {project_summary.project_name}"
            logger.info(f"Generating ImplementationPlan for request: '{user_req[:80]}...'")

            if session and hasattr(repository, "id"):
                plan = planner_service.plan_change(repository.id, user_req, session)
            else:
                sys_inst, user_prompt = build_planner_prompt(
                    user_request=user_req,
                    project_summary=project_summary,
                )
                plan = llm_service.generate_json(
                    prompt=user_prompt,
                    response_schema=ImplementationPlan,
                    system_instruction=sys_inst,
                    temperature=0.2,
                )

            logger.info(f"ImplementationPlan generated: goal='{plan.goal}', affected_files={plan.affected_files}")

            # -------------------------------------------------------------
            # Stage 3: Self-Correction Retry Loop
            # -------------------------------------------------------------
            pipeline_success = False

            for attempt in range(1, max_repair_attempts + 1):
                logger.info(f"--- STARTING PIPELINE ITERATION {attempt}/{max_repair_attempts} ---")

                # Determine ReflectionResult from prior iteration (if any)
                prev_reflection: Optional[ReflectionResult] = None
                if attempt > 1 and history and history[-1].reflection_result:
                    prev_reflection = history[-1].reflection_result

                # 3a. Generate code (Coder Agent - Filesystem Agnostic)
                logger.info(f"Invoking Coder Agent (iteration {attempt})")
                new_coding_result = coder_service.generate_code(
                    project_summary=project_summary,
                    implementation_plan=plan,
                    reflection_result=prev_reflection,
                    user_prompt_override=user_request if attempt == 1 else None,
                )

                # Merge with previous generated files if partial repair iteration
                if prev_reflection and prev_reflection.retry_scope in (RetryScope.SINGLE_FILE, RetryScope.MULTIPLE_FILES) and history:
                    current_coding_result = _merge_coding_results(history[-1].coding_result, new_coding_result)
                else:
                    current_coding_result = new_coding_result

                # 3b. Create fresh isolated workspace (WorkspaceManager)
                ws_id = f"orch_{uuid.uuid4().hex[:8]}_iter_{attempt}"
                ws_path = workspace_manager.create_workspace(repo_path, workspace_id=ws_id)
                logger.info(f"Created isolated workspace at: '{ws_path}'")

                try:
                    # 3c. Apply generated file changes to workspace
                    patch_warnings = workspace_manager.apply_changes(ws_path, current_coding_result.generated_files)
                    if patch_warnings:
                        current_coding_result.warnings.extend(patch_warnings)

                    # 3d. Execute validation tests inside workspace (Tester Agent)
                    logger.info(f"Executing Tester Agent validation steps in workspace '{ws_path}'")
                    test_result = tester_service.run_tests(ws_path)
                    logger.info(f"Tester outcome: success={test_result.success}, exit_code={test_result.exit_code}")

                    # Record iteration output
                    iteration = PipelineIteration(
                        iteration_number=attempt,
                        coding_result=current_coding_result,
                        test_result=test_result,
                        reflection_result=None,
                    )

                    # Check for test success
                    if test_result.success:
                        logger.info(f"Iteration {attempt} PASSED all validation tests cleanly!")
                        history.append(iteration)
                        pipeline_success = True
                        break

                    # Test failed: invoke Reflector Agent if retries remain
                    if attempt < max_repair_attempts:
                        logger.info(f"Iteration {attempt} FAILED validation. Invoking Reflector Agent.")
                        reflection_result = reflector_service.reflect(
                            project_summary=project_summary,
                            implementation_plan=plan,
                            coding_result=current_coding_result,
                            test_result=test_result,
                        )
                        iteration.reflection_result = reflection_result
                        history.append(iteration)

                        logger.info(
                            f"Reflector guidance: category={reflection_result.failure_category.value}, "
                            f"should_retry={reflection_result.should_retry}, scope={reflection_result.retry_scope.value}"
                        )

                        if not reflection_result.should_retry:
                            logger.info("Reflector determined failure is unrepairable. Terminating retry loop.")
                            break
                    else:
                        logger.info(f"Iteration {attempt} FAILED. Maximum repair attempts reached.")
                        history.append(iteration)
                        break

                finally:
                    # Always cleanup workspace directory
                    logger.info(f"Cleaning up workspace '{ws_path}'")
                    workspace_manager.cleanup(ws_path)

            # -------------------------------------------------------------
            # Stage 4: Deterministic Summary & Response Construction
            # -------------------------------------------------------------
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            final_test = history[-1].test_result if history else None
            final_coding = history[-1].coding_result if history else None
            final_reflection = history[-1].reflection_result if history else None

            if pipeline_success:
                summary_str = f"Pipeline completed successfully after {len(history)} iteration(s)."
            elif final_reflection and not final_reflection.should_retry:
                summary_str = (
                    f"Pipeline stopped because Reflector determined the failure was not repairable "
                    f"({final_reflection.failure_category.value}: {final_reflection.root_cause})."
                )
            else:
                summary_str = f"Pipeline terminated after reaching the maximum retry limit ({max_repair_attempts} attempt(s))."

            logger.info(f"Pipeline execution finished in {elapsed_ms}ms: {summary_str}")

            return FinalExecutionResult(
                success=pipeline_success,
                total_iterations=len(history),
                final_test_result=final_test,
                final_coding_result=final_coding,
                final_reflection_result=final_reflection,
                iteration_history=history,
                total_execution_time_ms=elapsed_ms,
                summary=summary_str,
            )

        except Exception as e:
            logger.error(f"Top-level pipeline execution error in OrchestratorService: {e}", exc_info=True)
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            final_test = history[-1].test_result if history else None
            final_coding = history[-1].coding_result if history else None
            final_reflection = history[-1].reflection_result if history else None

            return FinalExecutionResult(
                success=False,
                total_iterations=len(history),
                final_test_result=final_test,
                final_coding_result=final_coding,
                final_reflection_result=final_reflection,
                iteration_history=history,
                total_execution_time_ms=elapsed_ms,
                summary=f"Pipeline terminated due to unexpected execution error: {str(e)}",
            )


# Global singleton instance
orchestrator_service = OrchestratorService()
