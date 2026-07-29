"""Prompt builder for the Planner Agent.

Encapsulates all prompt engineering, system instructions, and structural context
formatting required to prompt the LLM for architectural planning.
"""

import json
from typing import Dict, Tuple
from app.schemas.repository import ProjectSummary


PLANNER_SYSTEM_INSTRUCTION = """You are an experienced Principal Software Architect.
Your task is to analyze a natural language feature request alongside a repository's project summary and produce a comprehensive, structured implementation plan.

Core Responsibilities:
1. Pure Reasoning & Planning: You must NOT generate source code. Your role is strictly strategy, component design, risk assessment, and execution sequencing.
2. Context Awareness: Carefully review the provided project architecture, programming languages, web frameworks, database systems, ORMs, entry points, key directories, and config files.
3. Logical Component Mapping: Identify high-level affected components (e.g. "API", "Database", "Authentication", "Frontend", "Configuration", "AI", "Deployment").
4. Concrete File Identification: List specific existing files that must be modified and new files that must be created relative to the repository workspace root.
5. Explicit Dependencies & Changes: Detail any required new package dependencies, database schema/migration changes, and environment variables.
6. Ordered Execution Steps: Provide unambiguous, step-by-step implementation instructions in logical order.
7. Risk & Assumption Assessment: Detail technical risks, breaking changes, edge cases, and explicit assumptions made.
8. Complexity & Scope Estimation: Assign a realistic complexity ("Low", "Medium", or "High") and estimate total files modified/created.
9. Architectural Reasoning: Provide clear justification for your design choices.

The generated response MUST strictly adhere to the ImplementationPlan JSON schema.
"""


def build_planner_prompt(
    user_request: str,
    project_summary: ProjectSummary,
) -> Tuple[str, str]:
    """Construct system instructions and structured prompt for the Planner Agent.

    Args:
        user_request: Natural language feature request or change instruction.
        project_summary: Cached ProjectSummary schema containing repository technical context.

    Returns:
        Tuple[str, str]: (system_instruction, user_prompt)
    """
    # Serialize entry points and observations cleanly
    entry_points_data = [ep.model_dump() for ep in project_summary.entry_points]

    user_prompt = f"""=== FEATURE REQUEST ===
{user_request}

=== REPOSITORY TECHNICAL CONTEXT ===
Project Name: {project_summary.project_name}
Description: {project_summary.description}
Architecture: {project_summary.architecture or 'Standard Modular Application'}
Languages: {', '.join(project_summary.languages) if project_summary.languages else 'None detected'}
Frameworks: {', '.join(project_summary.frameworks) if project_summary.frameworks else 'None detected'}
Package Manager: {project_summary.package_manager or 'None'}
Database: {project_summary.database or 'None'}
ORM: {project_summary.orm or 'None'}
Authentication: {project_summary.authentication or 'None'}
AI Stack: {', '.join(project_summary.ai_stack) if project_summary.ai_stack else 'None'}
Testing Frameworks: {', '.join(project_summary.testing_frameworks) if project_summary.testing_frameworks else 'None'}
Deployment: {project_summary.deployment or 'None'}

Key Functional Directories:
{json.dumps(project_summary.important_directories, indent=2)}

Key Configuration & Manifest Files:
{json.dumps(project_summary.important_files, indent=2)}

Identified Application Entry Points:
{json.dumps(entry_points_data, indent=2)}

Architectural Observations:
{json.dumps(project_summary.observations, indent=2)}

=== INSTRUCTION ===
Analyze the feature request in the context of this repository. Generate a structured ImplementationPlan that details:
1. Executive goal and summary
2. Affected high-level components (e.g. Authentication, Database, API, Frontend, Configuration, etc.)
3. Affected existing files and new files to create
4. Required package dependencies, database changes, and environment variable updates
5. Ordered step-by-step implementation plan
6. Identified technical risks and explicit assumptions
7. Complexity rating (Low, Medium, or High) and estimated file count
8. Technical architectural reasoning

Provide your output strictly in JSON matching the specified schema.
"""
    return PLANNER_SYSTEM_INSTRUCTION, user_prompt
