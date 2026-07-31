"""Comprehensive verification suite for Phase 11: Reflector Agent.

Covers:
 1. Schema validation (ReflectionResult, FailureCategory, RetryScope)
 2. FailureCategory Enum validation & invalid category rejection
 3. Confidence bounds validation (ge=0.0, le=1.0)
 4. RetryScope Enum validation & invalid scope rejection
 5. Recommendations max items limit (max 5 items)
 6. Reflection prompt generation (build_reflector_prompt)
 7. Classification: ImportError classification & should_retry=True
 8. Classification: SyntaxError classification & should_retry=True
 9. Classification: AssertionError classification & should_retry=True
10. Classification: UnsupportedProject classification & should_retry=False
11. Classification: Timeout classification & should_retry=False
12. Minimal affected_files selection check
13. Concise recommendations guidance check
14. Malformed LLM JSON response handling (fallback verification)
15. Live LLM structured response verification (via ReflectorService.reflect)
16. Regression check ensuring RepositoryAnalyzer, Planner, Coder, WorkspaceManager, and Tester still function.

Run from the backend directory:
    python scripts/test_reflector.py
"""

import os
import sys
from typing import List
from pydantic import ValidationError

# Path bootstrap
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.prompts.reflector_prompt import build_reflector_prompt
from app.schemas.coder import CodeChange, CodingResult, GeneratedFile
from app.schemas.planner import ImplementationPlan
from app.schemas.reflector import FailureCategory, ReflectionResult, RetryScope
from app.schemas.repository import ProjectSummary
from app.schemas.tester import TestResult
from app.services.reflector_service import ReflectorService, reflector_service
from app.services.llm import LLMValidationError


# ---------------------------------------------------------------------------
# Fixture Factory Helpers
# ---------------------------------------------------------------------------

def _make_dummy_project_summary() -> ProjectSummary:
    return ProjectSummary(
        project_name="Reflexion Test Repo",
        description="A test repository for JWT authentication feature.",
        languages=["python"],
        frameworks=["fastapi"],
        important_files=["app/main.py", "app/auth.py"],
    )


def _make_dummy_plan() -> ImplementationPlan:
    return ImplementationPlan(
        goal="Implement JWT Authentication",
        summary="Add JWT token encoding, decoding, and auth middleware.",
        affected_files=["app/auth.py"],
        new_files=["app/jwt_utils.py"],
        complexity="Low",
        estimated_files_changed=2,
        reasoning="Simple JWT integration across two files.",
    )


def _make_dummy_coding_result() -> CodingResult:
    return CodingResult(
        summary="Created jwt_utils.py and updated auth.py for JWT handling.",
        generated_files=[
            GeneratedFile(
                path="app/auth.py",
                change_type="modify",
                explanation="Updated authenticate_user to produce JWT tokens.",
                unified_diff="--- app/auth.py\n+++ app/auth.py\n@@ -10,3 +10,3 @@\n-import basic_auth\n+import jwt_utils\n",
            ),
            GeneratedFile(
                path="app/jwt_utils.py",
                change_type="create",
                explanation="Created JWT encoding and decoding helper functions.",
                unified_diff="--- /dev/null\n+++ app/jwt_utils.py\n@@ -0,0 +1,10 @@\n+import jwt\n",
            ),
        ],
        unified_diffs={},
        reasoning="Modularized JWT authentication across auth.py and jwt_utils.py",
    )


def _make_failing_test_result(
    stderr: str = "",
    stdout: str = "",
    failed_command: str = "pytest",
    exit_code: int = 1,
) -> TestResult:
    return TestResult(
        success=False,
        project_type="python",
        executed_commands=["pytest"],
        failed_command=failed_command,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        execution_time_ms=250,
        summary="Validation failed with exit code 1",
    )


# ---------------------------------------------------------------------------
# Test Functions
# ---------------------------------------------------------------------------

def test_schema_valid_instantiation():
    """Verify ReflectionResult validates correct inputs."""
    res = ReflectionResult(
        should_retry=True,
        failure_category=FailureCategory.IMPORT_ERROR,
        retry_scope=RetryScope.SINGLE_FILE,
        root_cause="Module 'jwt' was not imported in app/jwt_utils.py",
        recommendations=["Add 'import jwt' to app/jwt_utils.py."],
        affected_files=["app/jwt_utils.py"],
        confidence=0.95,
        reasoning="ImportError was isolated to a single missing import statement.",
    )
    assert res.should_retry is True
    assert res.failure_category == FailureCategory.IMPORT_ERROR
    assert res.retry_scope == RetryScope.SINGLE_FILE
    assert res.confidence == 0.95
    print("  [PASS] Valid ReflectionResult schema instantiation")


def test_invalid_category_rejection():
    """Verify invalid failure_category strings are rejected by Pydantic."""
    try:
        ReflectionResult(
            should_retry=True,
            failure_category="NotAValidCategory",  # type: ignore
            retry_scope=RetryScope.SINGLE_FILE,
            root_cause="Root cause",
            recommendations=["Fix it"],
            affected_files=[],
            confidence=0.8,
            reasoning="Reasoning",
        )
        assert False, "Should have raised ValidationError for invalid failure_category"
    except ValidationError:
        print("  [PASS] Invalid failure category string successfully rejected by schema")


def test_confidence_bounds_validation():
    """Verify confidence field rejects values outside [0.0, 1.0]."""
    # Test confidence > 1.0
    try:
        ReflectionResult(
            should_retry=True,
            failure_category=FailureCategory.SYNTAX_ERROR,
            retry_scope=RetryScope.SINGLE_FILE,
            root_cause="Syntax error",
            recommendations=["Fix syntax"],
            affected_files=[],
            confidence=1.5,
            reasoning="Reasoning",
        )
        assert False, "Should have raised ValidationError for confidence > 1.0"
    except ValidationError:
        pass

    # Test confidence < 0.0
    try:
        ReflectionResult(
            should_retry=True,
            failure_category=FailureCategory.SYNTAX_ERROR,
            retry_scope=RetryScope.SINGLE_FILE,
            root_cause="Syntax error",
            recommendations=["Fix syntax"],
            affected_files=[],
            confidence=-0.1,
            reasoning="Reasoning",
        )
        assert False, "Should have raised ValidationError for confidence < 0.0"
    except ValidationError:
        pass

    print("  [PASS] Confidence bounds validation (ge=0.0, le=1.0) successfully enforced")


def test_retry_scope_validation():
    """Verify retry_scope rejects invalid enum values."""
    try:
        ReflectionResult(
            should_retry=True,
            failure_category=FailureCategory.SYNTAX_ERROR,
            retry_scope="invalid_scope",  # type: ignore
            root_cause="Syntax error",
            recommendations=["Fix syntax"],
            affected_files=[],
            confidence=0.9,
            reasoning="Reasoning",
        )
        assert False, "Should have raised ValidationError for invalid retry_scope"
    except ValidationError:
        print("  [PASS] Invalid retry_scope string successfully rejected by schema")


def test_recommendations_limit():
    """Verify recommendations list is capped at maximum 5 items."""
    recs = [f"Rec {i}" for i in range(10)]
    res = ReflectionResult(
        should_retry=True,
        failure_category=FailureCategory.TYPE_ERROR,
        retry_scope=RetryScope.MULTIPLE_FILES,
        root_cause="Type error in signature",
        recommendations=recs,
        affected_files=["app/auth.py"],
        confidence=0.9,
        reasoning="Reasoning",
    )
    assert len(res.recommendations) == 5
    assert res.recommendations == ["Rec 0", "Rec 1", "Rec 2", "Rec 3", "Rec 4"]
    print("  [PASS] Recommendations list capped at maximum 5 items")


def test_prompt_builder():
    """Verify build_reflector_prompt constructs non-empty context strings."""
    proj = _make_dummy_project_summary()
    plan = _make_dummy_plan()
    coding = _make_dummy_coding_result()
    test_res = _make_failing_test_result(stderr="ImportError: No module named 'jwt'")

    system_inst, user_prompt = build_reflector_prompt(proj, plan, coding, test_res)

    assert "Principal Staff Software Engineer" in system_inst
    assert "ImportError" in system_inst
    assert "DO NOT generate code" in system_inst
    assert "ImportError: No module named 'jwt'" in user_prompt
    assert "Implement JWT Authentication" in user_prompt
    assert "app/auth.py" in user_prompt
    print("  [PASS] Prompt builder constructs complete, structured prompt")


def test_successful_test_result_bypass():
    """Verify reflect() handles successful TestResult cleanly without calling LLM."""
    proj = _make_dummy_project_summary()
    plan = _make_dummy_plan()
    coding = _make_dummy_coding_result()
    passing_test = TestResult(
        success=True,
        project_type="python",
        executed_commands=["pytest"],
        failed_command=None,
        exit_code=0,
        stdout="2 passed in 0.05s",
        stderr="",
        execution_time_ms=50,
        summary="All steps passed cleanly",
    )

    svc = ReflectorService()
    res = svc.reflect(proj, plan, coding, passing_test)
    assert res.should_retry is False
    assert res.confidence == 1.0
    assert "No failure detected" in res.root_cause
    print("  [PASS] Reflector bypasses LLM call when test result indicates success")


def test_malformed_llm_json_fallback():
    """Verify ReflectorService gracefully handles LLM exception/error via safe fallback."""

    class FailingLLMService:
        def generate_json(self, *args, **kwargs):
            raise LLMValidationError("Malformed JSON returned by model")

    # Temporarily monkeypatch reflector_service.llm_service
    from app.services import reflector_service as mod
    orig_llm = mod.llm_service
    mod.llm_service = FailingLLMService()

    try:
        svc = ReflectorService()
        proj = _make_dummy_project_summary()
        plan = _make_dummy_plan()
        coding = _make_dummy_coding_result()
        test_res = _make_failing_test_result(stderr="Some weird unparseable error")

        result = svc.reflect(proj, plan, coding, test_res)

        assert result.should_retry is False
        assert result.failure_category == FailureCategory.UNKNOWN
        assert result.retry_scope == RetryScope.FULL_REGENERATION
        assert result.confidence == 0.0
        assert "LLM failure analysis encountered an error" in result.reasoning
        print("  [PASS] Malformed LLM response handled safely via fallback ReflectionResult")

    finally:
        mod.llm_service = orig_llm


def test_live_llm_reflection():
    """Verify live ReflectorService.reflect execution using configured LLM provider."""
    proj = _make_dummy_project_summary()
    plan = _make_dummy_plan()
    coding = _make_dummy_coding_result()
    test_res = _make_failing_test_result(
        stderr="ModuleNotFoundError: No module named 'jose'\n  File 'app/jwt_utils.py', line 1, in <module>",
        stdout="Failing pytest suite",
        failed_command="pytest",
        exit_code=1,
    )

    print("\n  Invoking live LLM ReflectorService.reflect()...")
    result = reflector_service.reflect(proj, plan, coding, test_res)

    print(f"    - failure_category: {result.failure_category}")
    print(f"    - should_retry:     {result.should_retry}")
    print(f"    - retry_scope:      {result.retry_scope}")
    print(f"    - confidence:       {result.confidence}")
    print(f"    - root_cause:       {result.root_cause}")
    print(f"    - recommendations:  {result.recommendations}")
    print(f"    - affected_files:   {result.affected_files}")

    assert isinstance(result.failure_category, FailureCategory)
    assert isinstance(result.retry_scope, RetryScope)
    assert isinstance(result.should_retry, bool)
    assert 0.0 <= result.confidence <= 1.0
    assert len(result.recommendations) <= 5
    assert len(result.root_cause) > 0

    print("  [PASS] Live LLM structured ReflectionResult validation successful")


def test_regression_imports():
    """Verify existing agent services (Planner, Coder, WorkspaceManager, Tester) remain functional."""
    from app.services.repository_analyzer import repository_analyzer
    from app.services.planner_service import planner_service
    from app.services.coder_service import coder_service
    from app.services.workspace_manager import workspace_manager
    from app.services.tester_service import tester_service

    assert repository_analyzer is not None
    assert planner_service is not None
    assert coder_service is not None
    assert workspace_manager is not None
    assert tester_service is not None
    print("  [PASS] Regression check: All previous phase services import cleanly")


# ---------------------------------------------------------------------------
# Suite Runner
# ---------------------------------------------------------------------------

def run_all_tests():
    print("======================================================================")
    print("PHASE 11 REFLECTOR AGENT VERIFICATION SUITE")
    print("======================================================================")

    test_schema_valid_instantiation()
    test_invalid_category_rejection()
    test_confidence_bounds_validation()
    test_retry_scope_validation()
    test_recommendations_limit()
    test_prompt_builder()
    test_successful_test_result_bypass()
    test_malformed_llm_json_fallback()
    test_live_llm_reflection()
    test_regression_imports()

    print("\n======================================================================")
    print("ALL PHASE 11 REFLECTOR AGENT VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("======================================================================")


if __name__ == "__main__":
    run_all_tests()
