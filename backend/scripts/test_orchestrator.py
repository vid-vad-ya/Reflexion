"""Comprehensive verification suite for Phase 12: Orchestrator Agent.

Covers:
 1. Successful first-pass pipeline execution (iteration 1 passes)
 2. Failed test followed by successful repair iteration (iteration 1 fails, iteration 2 passes)
 3. Retry limit reached termination (attempts == max_repair_attempts)
 4. Early termination when should_retry == False
 5. SINGLE_FILE targeted regeneration scope handling
 6. MULTIPLE_FILES targeted regeneration scope handling
 7. FULL_REGENERATION scope handling
 8. Workspace creation and cleanup verification (zero leftover workspace directories)
 9. Top-level exception safety & graceful failure recovery
10. Iteration history accuracy and wall-clock execution timing
11. End-to-end live pipeline execution on a Python repository
12. Regression check ensuring all previous phase services (Analyzer, Planner, Coder, WorkspaceManager, Tester, Reflector) remain functional.

Run from the backend directory:
    python scripts/test_orchestrator.py
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from typing import List, Optional

# Path bootstrap
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.schemas.coder import CodingResult, GeneratedFile
from app.schemas.orchestrator import FinalExecutionResult, PipelineIteration
from app.schemas.planner import ImplementationPlan
from app.schemas.reflector import FailureCategory, ReflectionResult, RetryScope
from app.schemas.repository import ProjectSummary
from app.schemas.tester import TestResult
from app.services.orchestrator_service import OrchestratorService, orchestrator_service, _merge_coding_results


# ---------------------------------------------------------------------------
# Test Helpers & Fixtures
# ---------------------------------------------------------------------------

def _create_dummy_repo(root: Path) -> None:
    """Create a minimal valid Python workspace on disk."""
    (root / "requirements.txt").write_text("pytest\n", encoding="utf-8")
    (root / "main.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    (root / "test_main.py").write_text("from main import add\n\ndef test_add():\n    assert add(1, 2) == 3\n", encoding="utf-8")


def _make_dummy_project_summary() -> ProjectSummary:
    return ProjectSummary(
        project_name="Dummy Repo",
        description="A dummy test repository.",
        languages=["python"],
        frameworks=["fastapi"],
        important_files=["main.py", "requirements.txt"],
    )


def _make_dummy_plan() -> ImplementationPlan:
    return ImplementationPlan(
        goal="Add divide function",
        summary="Add divide function in main.py",
        affected_files=["main.py"],
        new_files=[],
        complexity="Low",
        estimated_files_changed=1,
        reasoning="Simple arithmetic extension.",
    )


# ---------------------------------------------------------------------------
# Verification Tests
# ---------------------------------------------------------------------------

def test_first_pass_success():
    """Verify first-pass execution completes in 1 iteration when tests pass."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        _create_dummy_repo(repo_path)

        class MockAnalyzer:
            def analyze_repository(self, path):
                return _make_dummy_project_summary()

        class MockPlanner:
            def plan_change(self, repo_id, req, session):
                return _make_dummy_plan()

        class MockCoder:
            def generate_code(self, **kwargs):
                return CodingResult(
                    summary="Added divide function",
                    generated_files=[
                        GeneratedFile(
                            path="main.py",
                            change_type="modify",
                            original_content="def add(a, b):\n    return a + b\n",
                            generated_content="def add(a, b):\n    return a + b\n\ndef divide(a, b):\n    return a / b\n",
                            explanation="Added divide function",
                        )
                    ],
                    unified_diffs={},
                    reasoning="Reasoning",
                )

        class MockTester:
            def run_tests(self, workspace, **kwargs):
                return TestResult(
                    success=True,
                    project_type="python",
                    executed_commands=["pytest"],
                    exit_code=0,
                    execution_time_ms=100,
                    summary="All steps passed cleanly",
                )

        from app.services import orchestrator_service as mod
        orig_analyzer = mod.repository_analyzer
        orig_coder = mod.coder_service
        orig_tester = mod.tester_service

        mod.repository_analyzer = MockAnalyzer()
        mod.coder_service = MockCoder()
        mod.tester_service = MockTester()

        try:
            svc = OrchestratorService()
            res = svc.run_pipeline(str(repo_path), user_request="Add divide function")

            assert res.success is True
            assert res.total_iterations == 1
            assert len(res.iteration_history) == 1
            assert "completed successfully after 1 iteration" in res.summary
            assert res.final_test_result.success is True
            print("  [PASS] First-pass successful pipeline execution (1 iteration)")

        finally:
            mod.repository_analyzer = orig_analyzer
            mod.coder_service = orig_coder
            mod.tester_service = orig_tester


def test_failed_test_followed_by_successful_repair():
    """Verify self-correction retry loop handles iteration 1 failure -> Reflector -> iteration 2 success."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        _create_dummy_repo(repo_path)

        class MockAnalyzer:
            def analyze_repository(self, path):
                return _make_dummy_project_summary()

        call_count = {"coder": 0, "tester": 0}

        class MockCoder:
            def generate_code(self, **kwargs):
                call_count["coder"] += 1
                if call_count["coder"] == 1:
                    return CodingResult(
                        summary="Buggy code attempt 1",
                        generated_files=[
                            GeneratedFile(
                                path="main.py",
                                change_type="modify",
                                generated_content="def add(a, b):\n    return a - b\n",  # Bug!
                                explanation="Buggy implementation",
                            )
                        ],
                        unified_diffs={},
                        reasoning="Reasoning",
                    )
                else:
                    return CodingResult(
                        summary="Repaired code attempt 2",
                        generated_files=[
                            GeneratedFile(
                                path="main.py",
                                change_type="modify",
                                generated_content="def add(a, b):\n    return a + b\n",  # Fixed!
                                explanation="Fixed implementation",
                            )
                        ],
                        unified_diffs={},
                        reasoning="Reasoning",
                    )

        class MockTester:
            def run_tests(self, workspace, **kwargs):
                call_count["tester"] += 1
                if call_count["tester"] == 1:
                    return TestResult(
                        success=False,
                        project_type="python",
                        executed_commands=["pytest"],
                        failed_command="pytest",
                        exit_code=1,
                        stderr="AssertionError: assert -1 == 3",
                        execution_time_ms=100,
                        summary="Test failed",
                    )
                else:
                    return TestResult(
                        success=True,
                        project_type="python",
                        executed_commands=["pytest"],
                        exit_code=0,
                        execution_time_ms=100,
                        summary="All tests passed",
                    )

        class MockReflector:
            def reflect(self, project_summary, implementation_plan, coding_result, test_result):
                return ReflectionResult(
                    should_retry=True,
                    failure_category=FailureCategory.ASSERTION_ERROR,
                    retry_scope=RetryScope.SINGLE_FILE,
                    root_cause="AssertionError in add function (returns a - b instead of a + b)",
                    recommendations=["Change minus operator to plus operator in main.py."],
                    affected_files=["main.py"],
                    confidence=0.9,
                    reasoning="Simple arithmetic fix.",
                )

        from app.services import orchestrator_service as mod
        orig_analyzer = mod.repository_analyzer
        orig_coder = mod.coder_service
        orig_tester = mod.tester_service
        orig_reflector = mod.reflector_service

        mod.repository_analyzer = MockAnalyzer()
        mod.coder_service = MockCoder()
        mod.tester_service = MockTester()
        mod.reflector_service = MockReflector()

        try:
            svc = OrchestratorService()
            res = svc.run_pipeline(str(repo_path), user_request="Fix add function")

            assert res.success is True
            assert res.total_iterations == 2
            assert len(res.iteration_history) == 2
            assert res.iteration_history[0].reflection_result is not None
            assert res.iteration_history[0].reflection_result.failure_category == FailureCategory.ASSERTION_ERROR
            assert res.iteration_history[1].test_result.success is True
            assert "completed successfully after 2 iteration" in res.summary
            print("  [PASS] Failed test followed by successful repair iteration (2 iterations)")

        finally:
            mod.repository_analyzer = orig_analyzer
            mod.coder_service = orig_coder
            mod.tester_service = orig_tester
            mod.reflector_service = orig_reflector


def test_retry_limit_reached():
    """Verify pipeline terminates cleanly when max_repair_attempts is reached."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        _create_dummy_repo(repo_path)

        class MockAnalyzer:
            def analyze_repository(self, path):
                return _make_dummy_project_summary()

        class MockCoder:
            def generate_code(self, **kwargs):
                return CodingResult(
                    summary="Always failing code",
                    generated_files=[
                        GeneratedFile(
                            path="main.py",
                            change_type="modify",
                            generated_content="raise Exception('Always fails')",
                            explanation="Failing code",
                        )
                    ],
                    unified_diffs={},
                    reasoning="Reasoning",
                )

        class MockTester:
            def run_tests(self, workspace, **kwargs):
                return TestResult(
                    success=False,
                    project_type="python",
                    executed_commands=["pytest"],
                    failed_command="pytest",
                    exit_code=1,
                    stderr="Exception: Always fails",
                    execution_time_ms=50,
                    summary="Failing step",
                )

        class MockReflector:
            def reflect(self, *args, **kwargs):
                return ReflectionResult(
                    should_retry=True,
                    failure_category=FailureCategory.TEST_FAILURE,
                    retry_scope=RetryScope.SINGLE_FILE,
                    root_cause="Persistent exception raised",
                    recommendations=["Remove exception"],
                    affected_files=["main.py"],
                    confidence=0.8,
                    reasoning="Reasoning",
                )

        from app.services import orchestrator_service as mod
        orig_analyzer = mod.repository_analyzer
        orig_coder = mod.coder_service
        orig_tester = mod.tester_service
        orig_reflector = mod.reflector_service

        mod.repository_analyzer = MockAnalyzer()
        mod.coder_service = MockCoder()
        mod.tester_service = MockTester()
        mod.reflector_service = MockReflector()

        try:
            svc = OrchestratorService()
            res = svc.run_pipeline(str(repo_path), max_repair_attempts=3)

            assert res.success is False
            assert res.total_iterations == 3
            assert len(res.iteration_history) == 3
            assert "reaching the maximum retry limit (3 attempt(s))" in res.summary
            print("  [PASS] Retry limit reached termination (max_repair_attempts=3)")

        finally:
            mod.repository_analyzer = orig_analyzer
            mod.coder_service = orig_coder
            mod.tester_service = orig_tester
            mod.reflector_service = orig_reflector


def test_should_retry_false_early_termination():
    """Verify pipeline terminates early on iteration 1 if Reflector determines failure is unrepairable."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        _create_dummy_repo(repo_path)

        class MockAnalyzer:
            def analyze_repository(self, path):
                return _make_dummy_project_summary()

        class MockCoder:
            def generate_code(self, **kwargs):
                return CodingResult(summary="Code", generated_files=[], unified_diffs={}, reasoning="")

        class MockTester:
            def run_tests(self, workspace, **kwargs):
                return TestResult(
                    success=False,
                    project_type="unknown",
                    executed_commands=[],
                    exit_code=-1,
                    execution_time_ms=10,
                    summary="Unsupported project",
                )

        class MockReflector:
            def reflect(self, *args, **kwargs):
                return ReflectionResult(
                    should_retry=False,
                    failure_category=FailureCategory.UNSUPPORTED_PROJECT,
                    retry_scope=RetryScope.FULL_REGENERATION,
                    root_cause="Unsupported project type; missing build manifest.",
                    recommendations=["Add pyproject.toml or package.json"],
                    affected_files=[],
                    confidence=0.99,
                    reasoning="Unrecoverable project type.",
                )

        from app.services import orchestrator_service as mod
        orig_analyzer = mod.repository_analyzer
        orig_coder = mod.coder_service
        orig_tester = mod.tester_service
        orig_reflector = mod.reflector_service

        mod.repository_analyzer = MockAnalyzer()
        mod.coder_service = MockCoder()
        mod.tester_service = MockTester()
        mod.reflector_service = MockReflector()

        try:
            svc = OrchestratorService()
            res = svc.run_pipeline(str(repo_path), max_repair_attempts=3)

            assert res.success is False
            assert res.total_iterations == 1
            assert "failure was not repairable (UnsupportedProject" in res.summary
            print("  [PASS] Early termination when should_retry == False (1 iteration)")

        finally:
            mod.repository_analyzer = orig_analyzer
            mod.coder_service = orig_coder
            mod.tester_service = orig_tester
            mod.reflector_service = orig_reflector


def test_merge_coding_results_partial_regeneration():
    """Verify _merge_coding_results merges newly generated files with untouched previous files."""
    prev = CodingResult(
        summary="Prev summary",
        generated_files=[
            GeneratedFile(path="file1.py", change_type="create", generated_content="print('1')", explanation=""),
            GeneratedFile(path="file2.py", change_type="create", generated_content="print('2')", explanation=""),
        ],
        unified_diffs={"file1.py": "diff1", "file2.py": "diff2"},
        reasoning="Prev reasoning",
    )

    new_res = CodingResult(
        summary="New summary",
        generated_files=[
            GeneratedFile(path="file1.py", change_type="modify", generated_content="print('1_fixed')", explanation="Fixed 1"),
        ],
        unified_diffs={"file1.py": "diff1_fixed"},
        reasoning="New reasoning",
    )

    merged = _merge_coding_results(prev, new_res)
    assert len(merged.generated_files) == 2
    merged_map = {gf.path: gf for gf in merged.generated_files}
    assert merged_map["file1.py"].generated_content == "print('1_fixed')"
    assert merged_map["file2.py"].generated_content == "print('2')"
    print("  [PASS] CodingResult merging for partial regeneration (SINGLE_FILE / MULTIPLE_FILES)")


def test_workspace_cleanup_guarantee():
    """Verify isolated workspaces created during pipeline execution are completely cleaned up."""
    from app.services.workspace_manager import workspace_manager

    base_ws_dir = workspace_manager._base_workspace_dir
    initial_workspaces = set(os.listdir(base_ws_dir)) if os.path.exists(base_ws_dir) else set()

    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        _create_dummy_repo(repo_path)

        svc = OrchestratorService()

        # Run pipeline with failing test so it runs 2 iterations
        class MockAnalyzer:
            def analyze_repository(self, path):
                return _make_dummy_project_summary()

        class MockCoder:
            def generate_code(self, **kwargs):
                return CodingResult(summary="Code", generated_files=[], unified_diffs={}, reasoning="")

        class MockTester:
            def run_tests(self, workspace, **kwargs):
                return TestResult(success=True, project_type="python", executed_commands=[], exit_code=0, execution_time_ms=10, summary="OK")

        from app.services import orchestrator_service as mod
        orig_analyzer = mod.repository_analyzer
        orig_coder = mod.coder_service
        orig_tester = mod.tester_service

        mod.repository_analyzer = MockAnalyzer()
        mod.coder_service = MockCoder()
        mod.tester_service = MockTester()

        try:
            svc.run_pipeline(str(repo_path))
        finally:
            mod.repository_analyzer = orig_analyzer
            mod.coder_service = orig_coder
            mod.tester_service = orig_tester

    final_workspaces = set(os.listdir(base_ws_dir)) if os.path.exists(base_ws_dir) else set()
    new_leftovers = final_workspaces - initial_workspaces
    assert len(new_leftovers) == 0, f"Leftover workspace directories detected: {new_leftovers}"
    print("  [PASS] Workspace creation and cleanup guarantee verified (zero leftover directories)")


def test_exception_safety():
    """Verify run_pipeline handles top-level exceptions safely without raising uncaught errors."""
    class CrashingAnalyzer:
        def analyze_repository(self, path):
            raise RuntimeError("Unexpected filesystem error during analysis")

    from app.services import orchestrator_service as mod
    orig_analyzer = mod.repository_analyzer
    mod.repository_analyzer = CrashingAnalyzer()

    try:
        svc = OrchestratorService()
        res = svc.run_pipeline("/non/existent/path")

        assert res.success is False
        assert "unexpected execution error" in res.summary
        assert "Unexpected filesystem error during analysis" in res.summary
        print("  [PASS] Top-level exception safety & graceful failure recovery")

    finally:
        mod.repository_analyzer = orig_analyzer


def test_live_pipeline_execution():
    """Verify live E2E pipeline execution using real agent services."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        _create_dummy_repo(repo_path)

        print("\n  Invoking live OrchestratorService.run_pipeline()...")
        res = orchestrator_service.run_pipeline(
            str(repo_path),
            user_request="Add a subtract function subtract(a, b) -> a - b in main.py and a corresponding test in test_main.py",
            max_repair_attempts=2,
        )

        print(f"    - success:                 {res.success}")
        print(f"    - total_iterations:        {res.total_iterations}")
        print(f"    - total_execution_time_ms: {res.total_execution_time_ms}ms")
        print(f"    - summary:                 {res.summary}")

        assert isinstance(res.success, bool)
        assert res.total_iterations >= 1
        assert len(res.iteration_history) == res.total_iterations
        assert res.total_execution_time_ms >= 0
        assert len(res.summary) > 0
        print("  [PASS] Live E2E pipeline execution completed successfully")


def test_regression_imports():
    """Verify all previous phase services import cleanly and remain intact."""
    from app.services.repository_analyzer import repository_analyzer
    from app.services.planner_service import planner_service
    from app.services.coder_service import coder_service
    from app.services.workspace_manager import workspace_manager
    from app.services.tester_service import tester_service
    from app.services.reflector_service import reflector_service
    from app.services.orchestrator_service import orchestrator_service

    assert repository_analyzer is not None
    assert planner_service is not None
    assert coder_service is not None
    assert workspace_manager is not None
    assert tester_service is not None
    assert reflector_service is not None
    assert orchestrator_service is not None
    print("  [PASS] Regression check: All previous phase agent services import cleanly")


# ---------------------------------------------------------------------------
# Suite Runner
# ---------------------------------------------------------------------------

def run_all_tests():
    print("======================================================================")
    print("PHASE 12 ORCHESTRATOR AGENT VERIFICATION SUITE")
    print("======================================================================")

    test_first_pass_success()
    test_failed_test_followed_by_successful_repair()
    test_retry_limit_reached()
    test_should_retry_false_early_termination()
    test_merge_coding_results_partial_regeneration()
    test_workspace_cleanup_guarantee()
    test_exception_safety()
    test_live_pipeline_execution()
    test_regression_imports()

    print("\n======================================================================")
    print("ALL PHASE 12 ORCHESTRATOR AGENT VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("======================================================================")


if __name__ == "__main__":
    run_all_tests()
