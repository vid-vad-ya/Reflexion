"""Prompt template builder for the Reflector Agent (Phase 11).

Constructs structured prompts for analyzing implementation failures and producing
ReflectionResult response payloads.
"""

from typing import Tuple

from app.schemas.coder import CodingResult
from app.schemas.planner import ImplementationPlan
from app.schemas.repository import ProjectSummary
from app.schemas.tester import TestResult


SYSTEM_INSTRUCTION = """You are a Principal Staff Software Engineer performing failure analysis on a failed code implementation.

Your sole responsibility is to analyze why a generated implementation failed during validation (testing/building), isolate the root cause, determine if a retry attempt is worthwhile, identify the minimal set of affected files requiring regeneration, and provide concise, actionable recommendations for the next coding attempt.

STRICT CONSTRAINTS:
1. DO NOT generate code.
2. DO NOT rewrite files.
3. DO NOT suggest unrelated improvements or code style refactorings.
4. NEVER speculate. If the root cause cannot be determined confidently, set:
   - failure_category = "Unknown"
   - should_retry = false
   - retry_scope = "full_regeneration"
   and clearly explain why in root_cause and reasoning.

FAILURE CATEGORY RULES:
You MUST classify the failure into exactly ONE of the following standardized categories:
- "ImportError": Missing module imports, invalid import statements, or unresolvable module paths.
- "SyntaxError": Invalid syntax, unclosed brackets, indentation errors, or unparseable code structure.
- "TypeError": Mismatched data types, invalid method signatures, or wrong parameter counts.
- "AssertionError": Explicit test assertion failure (e.g. assert actual == expected failed).
- "BuildFailure": Compilation failure, transpilation failure, or bundler build errors (e.g. npm build, mvn compile).
- "TestFailure": General unit test failure not specifically covered by ImportError/SyntaxError/TypeError/AssertionError.
- "MissingDependency": External package/library missing from environment or manifest (e.g. requirements.txt, package.json).
- "Timeout": Command execution exceeded execution timeout.
- "UnsupportedProject": Project framework or language is not supported by the test runner.
- "EnvironmentError": Subprocess executable not found, broken OS environment, or missing system binaries.
- "Unknown": Root cause cannot be determined or failure is unrecoverable without human intervention.

RETRY DECISION RULES (should_retry):
- true: If the failure is a fixable code or configuration bug (e.g. ImportError, SyntaxError, TypeError, AssertionError, missing local import, wrong parameter, incorrect API call).
- false: If the failure is unrecoverable (e.g. UnsupportedProject, EnvironmentError, unresolvable system dependency, corrupted workspace, environment timeout, or Unknown cause).

RETRY SCOPE RULES (retry_scope):
- "single_file": Only one specific file contains the error and needs regeneration.
- "multiple_files": A small, specific subset of generated/modified files caused the failure and need regeneration.
- "full_regeneration": The entire implementation plan or multiple component boundaries failed, or root cause is unknown.

AFFECTED FILES RULES:
- Identify ONLY the smallest possible subset of relative file paths directly responsible for the failure.
- Never include unrelated files that compiled cleanly or were untouched.

RECOMMENDATIONS RULES:
- Return a list of MAXIMUM 5 concise, actionable instructions.
- Examples of good recommendations:
  * "Rename remaining imports."
  * "Update API call signature to match user model."
  * "Fix incorrect function signature in auth service."
  * "Correct endpoint path in router."
  * "Resolve failing assertion by initializing default dict."
- AVOID vague recommendations like "Fix the code", "Improve implementation", or "Debugging required".

CONFIDENCE RULES:
- Return a float strictly between 0.0 and 1.0 representing your degree of certainty in the analysis.

You MUST return valid JSON matching the ReflectionResult schema exactly.
"""


def build_reflector_prompt(
    project_summary: ProjectSummary,
    implementation_plan: ImplementationPlan,
    coding_result: CodingResult,
    test_result: TestResult,
) -> Tuple[str, str]:
    """Build the system instruction and user prompt for the Reflector Agent.

    Args:
        project_summary: Project metadata (languages, frameworks, dependencies).
        implementation_plan: Architectural plan that was executed.
        coding_result: Generated code files, explanations, and diffs.
        test_result: Subprocess execution output (exit code, stdout, stderr, failed command).

    Returns:
        Tuple[str, str]: (system_instruction, user_prompt)
    """
    # 1. Format Project Summary context
    summary_parts = [
        f"Project Name: {project_summary.project_name}",
        f"Description: {project_summary.description}",
    ]
    if project_summary.languages:
        summary_parts.append(f"Languages: {', '.join(project_summary.languages)}")
    if project_summary.frameworks:
        summary_parts.append(f"Frameworks: {', '.join(project_summary.frameworks)}")
    if project_summary.technologies:
        tech_names = [t.name for t in project_summary.technologies[:15]]
        summary_parts.append(f"Technologies: {', '.join(tech_names)}")
    if project_summary.important_files:
        summary_parts.append(f"Key Files: {', '.join(project_summary.important_files[:10])}")
    project_context = "\n".join(summary_parts)

    # 2. Format Implementation Plan context
    plan_context = f"Goal: {implementation_plan.goal}\nSummary: {implementation_plan.summary}"
    if implementation_plan.affected_files:
        plan_context += f"\nPlanned Affected Files: {', '.join(implementation_plan.affected_files)}"
    if implementation_plan.new_files:
        plan_context += f"\nPlanned New Files: {', '.join(implementation_plan.new_files)}"

    # 3. Format Coding Result context
    coding_files_summary = []
    for gen_file in coding_result.generated_files:
        diff_snippet = ""
        if gen_file.unified_diff:
            # Include up to 20 lines of diff for context
            diff_lines = gen_file.unified_diff.splitlines()[:20]
            diff_snippet = "\n    Diff preview:\n" + "\n".join(f"      {line}" for line in diff_lines)

        coding_files_summary.append(
            f"- Path: {gen_file.path} ({gen_file.change_type.upper()})\n"
            f"  Explanation: {gen_file.explanation}{diff_snippet}"
        )
    coding_context = f"Coding Summary: {coding_result.summary}\nFiles Modified/Created:\n" + "\n".join(
        coding_files_summary
    )

    # 4. Format Test Result context
    test_context = (
        f"Project Type: {test_result.project_type}\n"
        f"Success: {test_result.success}\n"
        f"Exit Code: {test_result.exit_code}\n"
        f"Failed Command: {test_result.failed_command or 'None'}\n"
        f"Executed Commands: {', '.join(test_result.executed_commands)}\n"
        f"Summary: {test_result.summary}\n\n"
        f"STDOUT Output:\n{test_result.stdout[:2000] if test_result.stdout else '[Empty]'}\n\n"
        f"STDERR Output:\n{test_result.stderr[:2000] if test_result.stderr else '[Empty]'}"
    )

    # Assemble complete user prompt
    user_prompt = f"""Please analyze the following implementation failure and produce structured reflection guidance.

=== 1. PROJECT SUMMARY ===
{project_context}

=== 2. IMPLEMENTATION PLAN ===
{plan_context}

=== 3. GENERATED CODING RESULT ===
{coding_context}

=== 4. TEST VALIDATION RESULT ===
{test_context}

Analyze the failure above, isolate the exact root cause, determine failure_category, should_retry, retry_scope, affected_files, recommendations, confidence, and reasoning. Return JSON matching ReflectionResult.
"""

    return SYSTEM_INSTRUCTION, user_prompt
