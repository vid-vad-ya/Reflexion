"""ReflectorService – Failure Analysis and Repair Guidance Agent for Reflexion (Phase 11).

Analyzes validation failures (TestResult) alongside coding changes (CodingResult),
implementation plans (ImplementationPlan), and repository context (ProjectSummary).

Generates structured ReflectionResult payloads containing root cause analysis,
failure categorization, retry decisions, scope of repair, affected files, and actionable recommendations.

Strictly stateless: Does NOT execute commands, modify files, write code, run tests, or manage retry loops.
"""

import logging
from typing import Optional

from app.prompts.reflector_prompt import build_reflector_prompt
from app.schemas.coder import CodingResult
from app.schemas.planner import ImplementationPlan
from app.schemas.reflector import FailureCategory, ReflectionResult, RetryScope
from app.schemas.repository import ProjectSummary
from app.schemas.tester import TestResult
from app.services.llm import LLMError, LLMValidationError, llm_service

logger = logging.getLogger("reflexion.services.reflector")


class ReflectorService:
    """Service responsible for reasoning over implementation failures and producing repair guidance.

    Orchestrates:
    1. Prompt construction via `build_reflector_prompt`.
    2. Failure reasoning and classification via `llm_service.generate_json()`.
    3. Safe fallback handling if LLM response or validation fails.
    """

    def reflect(
        self,
        project_summary: ProjectSummary,
        implementation_plan: ImplementationPlan,
        coding_result: CodingResult,
        test_result: TestResult,
    ) -> ReflectionResult:
        """Analyze a failed implementation and return structured repair guidance.

        Args:
            project_summary: Technical context and dependencies of target repository.
            implementation_plan: Architectural plan used during code generation.
            coding_result: Generated code files, explanations, and diffs.
            test_result: Outcome of test/build validation step.

        Returns:
            ReflectionResult: Validated Pydantic response containing failure analysis.
        """
        logger.info("Initiating failure analysis in ReflectorService")

        # Shortcut for successful test results (no failure to analyze)
        if test_result.success:
            logger.info("TestResult indicates success. Returning positive ReflectionResult.")
            return ReflectionResult(
                should_retry=False,
                failure_category=FailureCategory.UNKNOWN,
                retry_scope=RetryScope.SINGLE_FILE,
                root_cause="No failure detected. All validation steps completed successfully.",
                recommendations=["No repairs required; code passed all validation steps."],
                affected_files=[],
                confidence=1.0,
                reasoning="Validation succeeded cleanly with exit code 0.",
            )

        # Build system instruction and user prompt
        system_instruction, user_prompt = build_reflector_prompt(
            project_summary=project_summary,
            implementation_plan=implementation_plan,
            coding_result=coding_result,
            test_result=test_result,
        )

        # Invoke LLM for structured JSON analysis
        try:
            logger.info("Invoking LLMService.generate_json for failure reflection")
            result = llm_service.generate_json(
                prompt=user_prompt,
                response_schema=ReflectionResult,
                system_instruction=system_instruction,
                temperature=0.1,
            )
            logger.info(
                f"Reflection analysis complete: category={result.failure_category.value}, "
                f"should_retry={result.should_retry}, confidence={result.confidence}"
            )
            return result

        except (LLMError, LLMValidationError, Exception) as e:
            logger.error(f"Reflector LLM reasoning or schema validation failed: {e}")
            # Fallback safe ReflectionResult when LLM fails or produces unparseable output
            return ReflectionResult(
                should_retry=False,
                failure_category=FailureCategory.UNKNOWN,
                retry_scope=RetryScope.FULL_REGENERATION,
                root_cause=f"Failure analysis could not be completed confidently: {str(e)}",
                recommendations=["Inspect raw test output logs manually.", "Verify system environment and dependencies."],
                affected_files=[f.path for f in coding_result.generated_files],
                confidence=0.0,
                reasoning=f"LLM failure analysis encountered an error or invalid JSON: {str(e)}",
            )


# Singleton service instance
reflector_service = ReflectorService()
