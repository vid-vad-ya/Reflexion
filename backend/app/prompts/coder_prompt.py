"""Coder Agent Prompt Construction Module.

Formats context (ProjectSummary, ImplementationPlan, source file contents) into structured
prompts for the LLM to generate production-ready code changes incrementally per file
and produce lightweight final summaries.
"""

import json
from typing import Dict, List, Optional, Tuple

from app.schemas.planner import ImplementationPlan
from app.schemas.repository import ProjectSummary


CODER_SYSTEM_INSTRUCTION = """You are a Senior Staff Software Engineer and expert Systems Architect.
Your task is to implement exact, production-ready code changes based strictly on an architectural ImplementationPlan.

Guidelines & Requirements:
1. PRESERVE CODING STYLE: Follow existing patterns, conventions, typing, naming, and architectural idioms present in the repository context.
2. TARGETED CHANGES: Modify only the files required by the ImplementationPlan. Do not perform extraneous refactoring or change unrelated code.
3. COMPLETE FILE CONTENTS: For created or modified files, provide the complete, functional, non-truncated content for generated_content. Do NOT use placeholder comments like '// ... rest of code stays same ...' or 'TODO'.
4. DETAILED EXPLANATION: Provide a clear, technical explanation for every modified, created, or deleted file detailing what was changed and why.
5. STRICT JSON OUTPUT: Return your response strictly matching the requested JSON schema.
"""

SINGLE_FILE_CODER_SYSTEM_INSTRUCTION = """You are a Senior Staff Software Engineer and expert Systems Architect.
Your task is to implement exact, production-ready code changes for a SINGLE TARGET FILE based strictly on an architectural ImplementationPlan.

Guidelines & Requirements:
1. PRESERVE CODING STYLE: Follow existing patterns, conventions, typing, naming, and architectural idioms present in the repository context.
2. TARGETED FILE ONLY: Focus exclusively on generating code for the specified target file path.
3. COMPLETE FILE CONTENTS: For created or modified files, provide the complete, functional, non-truncated content for generated_content. Do NOT use placeholder comments like '// ... rest of code stays same ...' or 'TODO'.
4. DETAILED EXPLANATION: Provide a clear, technical explanation of what was changed or created in this file and why.
5. STRICT JSON OUTPUT: Return your response strictly matching the requested JSON schema.
"""

CODER_SUMMARY_SYSTEM_INSTRUCTION = """You are a Senior Staff Software Engineer and Technical Writer.
Your task is to generate a cohesive executive summary and architectural reasoning for code changes that have been implemented across targeted repository files.
"""


def build_single_file_coder_prompt(
    project_summary: ProjectSummary,
    implementation_plan: ImplementationPlan,
    file_path: str,
    original_content: Optional[str] = None,
    is_new_file: bool = False,
    user_prompt_override: Optional[str] = None,
) -> Tuple[str, str]:
    """Construct system instruction and user prompt for generating code for a single file.

    Args:
        project_summary: High-level repository structure and technology context.
        implementation_plan: Plan detailing goal, summary, and implementation steps.
        file_path: Relative path of the target file to generate.
        original_content: Original string content of the target file (if existing).
        is_new_file: True if file is being created, False if modified/deleted.
        user_prompt_override: Optional additional natural language instructions.

    Returns:
        Tuple[str, str]: (system_instruction, user_prompt)
    """
    summary_overview = {
        "project_name": project_summary.project_name,
        "description": project_summary.description,
        "languages": project_summary.languages,
        "frameworks": project_summary.frameworks,
        "architecture": project_summary.architecture,
    }
    formatted_summary = json.dumps(summary_overview, indent=2)

    plan_overview = {
        "goal": implementation_plan.goal,
        "summary": implementation_plan.summary,
        "implementation_steps": implementation_plan.implementation_steps,
    }
    formatted_plan = json.dumps(plan_overview, indent=2)

    file_status = "NEW FILE to be created" if is_new_file else "EXISTING FILE to be modified or deleted"

    content_block = ""
    if not is_new_file and original_content is not None:
        content_block = f"### Current Original Content for '{file_path}':\n```\n{original_content}\n```\n\n"
    elif is_new_file:
        content_block = f"### File Status: '{file_status}' is a NEW file (empty initial content).\n\n"

    override_section = ""
    if user_prompt_override and user_prompt_override.strip():
        override_section = f"### Additional Instructions:\n{user_prompt_override.strip()}\n\n"

    user_prompt = f"""### Target Repository Context:
{formatted_summary}

### Implementation Goal & Plan:
{formatted_plan}

### Target File:
File Path: `{file_path}`
Status: {file_status}

{content_block}{override_section}### Instructions:
Generate complete code strictly for `{file_path}` to fulfill the implementation plan.
Return a valid JSON object matching the requested schema with:
- `change_type`: 'create', 'modify', or 'delete'.
- `generated_content`: complete, non-truncated file string (or null if delete).
- `explanation`: clear technical explanation of what changed in this file and why.
"""

    return SINGLE_FILE_CODER_SYSTEM_INSTRUCTION, user_prompt


def build_coder_summary_prompt(
    goal: str,
    plan_summary: str,
    file_explanations: List[Dict[str, str]],
) -> Tuple[str, str]:
    """Construct system instruction and user prompt for final code change summarization.

    Args:
        goal: The original implementation plan goal.
        plan_summary: The original plan summary.
        file_explanations: List of dicts containing 'path', 'change_type', and 'explanation'.

    Returns:
        Tuple[str, str]: (system_instruction, user_prompt)
    """
    explanations_text = []
    for item in file_explanations:
        explanations_text.append(
            f"- [{item.get('change_type', 'modify').upper()}] `{item.get('path')}`: {item.get('explanation')}"
        )
    formatted_explanations = "\n".join(explanations_text)

    user_prompt = f"""### Implementation Goal:
{goal}

### Plan Summary:
{plan_summary}

### Implemented File Changes & Explanations:
{formatted_explanations}

### Instructions:
Based strictly on the implementation goal and the per-file explanations above:
1. Provide a high-level `summary` (2-4 sentences) summarizing all implemented changes.
2. Provide concise technical `reasoning` explaining how these file changes fulfill the architectural goal.

Return a valid JSON object matching the requested schema.
"""
    return CODER_SUMMARY_SYSTEM_INSTRUCTION, user_prompt


def build_coder_prompt(
    project_summary: ProjectSummary,
    implementation_plan: ImplementationPlan,
    source_files: Dict[str, str],
    user_prompt_override: Optional[str] = None,
) -> Tuple[str, str]:
    """Construct system instruction and user prompt for multi-file generation (retained for backward compatibility).

    Args:
        project_summary: Repository structure and technology context.
        implementation_plan: Architectural plan detailing goal, steps, and affected files.
        source_files: Dictionary mapping relative file paths to their exact string content.
        user_prompt_override: Optional additional natural language instructions.

    Returns:
        Tuple[str, str]: (system_instruction, user_prompt)
    """
    summary_dict = project_summary.model_dump()
    formatted_summary = json.dumps(summary_dict, indent=2)

    plan_dict = implementation_plan.model_dump()
    formatted_plan = json.dumps(plan_dict, indent=2)

    if source_files:
        formatted_files_list = []
        for path, content in source_files.items():
            formatted_files_list.append(
                f"--- BEGIN FILE: {path} ---\n{content}\n--- END FILE: {path} ---"
            )
        formatted_source_files = "\n\n".join(formatted_files_list)
    else:
        formatted_source_files = "(No existing source files were loaded or required for reading.)"

    override_section = ""
    if user_prompt_override and user_prompt_override.strip():
        override_section = f"\n### Additional User Instructions:\n{user_prompt_override.strip()}\n"

    user_prompt = f"""### Target Repository Context (Project Summary):
{formatted_summary}

### Architectural Implementation Plan:
{formatted_plan}
{override_section}
### Relevant Source Files Content:
{formatted_source_files}

### Instructions:
Based strictly on the Implementation Plan and repository context provided above, generate the complete implementation code changes.
Return the result as a valid JSON object matching the requested schema.
"""

    return CODER_SYSTEM_INSTRUCTION, user_prompt
