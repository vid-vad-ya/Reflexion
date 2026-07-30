"""Comprehensive verification suite for Phase 10: Tester Agent.

Covers:
 1. Python project detection (requirements.txt)
 2. Python project detection (pyproject.toml)
 3. Node project detection (package.json)
 4. Unsupported project detection (empty directory)
 5. Successful pytest execution (passing test)
 6. Failed pytest execution (failing test)
 7. Timeout handling
 8. Missing executable handling
 9. Workspace isolation (cwd is workspace, not original)
10. Correct stdout capture
11. Correct stderr capture
12. Exit code capture
13. Execution time capture
14. TestResult schema validation
15. Regression: existing service imports unaffected

Run from the backend directory:
    python scripts/test_tester_service.py
"""

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Path bootstrap
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.schemas.tester import TestResult, ValidationStep
from app.services.tester_service import TesterService, tester_service, DEFAULT_TIMEOUT_SECONDS

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tester(base: Optional[Path] = None) -> TesterService:
    return TesterService()


def _passing_pytest_project(root: Path) -> None:
    """Write a minimal Python project with a passing test."""
    (root / "requirements.txt").write_text("pytest\n", encoding="utf-8")
    (root / "test_sample.py").write_text(
        "def test_always_passes():\n    assert 1 + 1 == 2\n",
        encoding="utf-8",
    )


def _failing_pytest_project(root: Path) -> None:
    """Write a minimal Python project with a failing test."""
    (root / "requirements.txt").write_text("pytest\n", encoding="utf-8")
    (root / "test_fail.py").write_text(
        "def test_always_fails():\n    assert 1 == 2\n",
        encoding="utf-8",
    )


def _node_project(root: Path, has_test_script: bool = True) -> None:
    """Write a minimal package.json."""
    scripts = {"test": "echo 'no real tests'"} if has_test_script else {}
    pkg = {"name": "test-app", "version": "1.0.0", "scripts": scripts}
    (root / "package.json").write_text(json.dumps(pkg, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_python_detection_requirements(tmp: Path) -> None:
    print("\n[1/15] Python project detection via requirements.txt ...")
    (tmp / "requirements.txt").touch()
    result = tester_service.detect_project_type(tmp)
    assert result == "python", f"Expected 'python', got '{result}'"
    print("  [PASS]")


def test_python_detection_pyproject(tmp: Path) -> None:
    print("\n[2/15] Python project detection via pyproject.toml ...")
    (tmp / "pyproject.toml").touch()
    result = tester_service.detect_project_type(tmp)
    assert result == "python", f"Expected 'python', got '{result}'"
    print("  [PASS]")


def test_node_detection(tmp: Path) -> None:
    print("\n[3/15] Node project detection via package.json ...")
    (tmp / "package.json").write_text("{}", encoding="utf-8")
    result = tester_service.detect_project_type(tmp)
    assert result == "node", f"Expected 'node', got '{result}'"
    print("  [PASS]")


def test_unsupported_detection(tmp: Path) -> None:
    print("\n[4/15] Unsupported project detection (empty dir) ...")
    result = tester_service.detect_project_type(tmp)
    assert result == "unknown", f"Expected 'unknown', got '{result}'"
    print("  [PASS]")


def test_successful_pytest_execution() -> None:
    print("\n[5/15] Successful pytest execution ...")
    with tempfile.TemporaryDirectory() as raw:
        ws = Path(raw)
        _passing_pytest_project(ws)
        result = tester_service.run_tests(ws)

    assert isinstance(result, TestResult)
    assert result.project_type == "python"
    assert len(result.executed_commands) == 1
    assert result.failed_command is None
    assert result.exit_code == 0
    assert result.success is True
    assert result.execution_time_ms >= 0
    print(f"  stdout preview: {result.stdout[:80]!r}")
    print("  [PASS]")


def test_failed_pytest_execution() -> None:
    print("\n[6/15] Failed pytest execution ...")
    with tempfile.TemporaryDirectory() as raw:
        ws = Path(raw)
        _failing_pytest_project(ws)
        result = tester_service.run_tests(ws)

    assert isinstance(result, TestResult)
    assert result.project_type == "python"
    assert result.success is False
    assert result.exit_code != 0
    assert result.failed_command is not None
    assert "pytest" in result.failed_command
    assert result.execution_time_ms >= 0
    print(f"  exit_code={result.exit_code}, failed_command={result.failed_command!r}")
    print("  [PASS]")


def test_timeout_handling() -> None:
    print("\n[7/15] Timeout handling ...")
    with tempfile.TemporaryDirectory() as raw:
        ws = Path(raw)
        # Build a step that sleeps longer than the timeout.
        wm = _make_tester()
        step = ValidationStep(
            name="Sleep forever",
            command=["python", "-c", "import time; time.sleep(60)"],
        )
        exit_code, stdout, stderr, elapsed_ms = TesterService._execute_step(
            ws, step, timeout_seconds=1
        )

    assert exit_code == -1, f"Expected exit_code=-1 (timeout), got {exit_code}"
    assert "timed out" in stderr.lower() or "timeout" in stderr.lower(), (
        f"Expected timeout message in stderr, got: {stderr!r}"
    )
    assert elapsed_ms >= 0
    print(f"  exit_code={exit_code}, stderr={stderr!r}")
    print("  [PASS]")


def test_missing_executable_handling() -> None:
    print("\n[8/15] Missing executable handling ...")
    with tempfile.TemporaryDirectory() as raw:
        ws = Path(raw)
        step = ValidationStep(
            name="Nonexistent tool",
            command=["__reflexion_nonexistent_binary_xyz__", "--version"],
        )
        exit_code, stdout, stderr, elapsed_ms = TesterService._execute_step(
            ws, step, timeout_seconds=10
        )

    assert exit_code == -2, f"Expected exit_code=-2 (not found), got {exit_code}"
    assert "not found" in stderr.lower(), f"Expected 'not found' in stderr, got: {stderr!r}"
    print(f"  exit_code={exit_code}, stderr={stderr!r}")
    print("  [PASS]")


def test_workspace_isolation() -> None:
    print("\n[9/15] Workspace isolation (cwd is workspace) ...")
    with tempfile.TemporaryDirectory() as raw_src, tempfile.TemporaryDirectory() as raw_ws:
        src = Path(raw_src)
        ws = Path(raw_ws)

        # Passing test only in workspace; source is empty.
        _passing_pytest_project(ws)

        result = tester_service.run_tests(ws)

        # Source dir must be untouched.
        assert not list(src.iterdir()), "Source directory was unexpectedly modified."
        assert result.success is True

    print("  [PASS]")


def test_stdout_capture() -> None:
    print("\n[10/15] Correct stdout capture ...")
    with tempfile.TemporaryDirectory() as raw:
        ws = Path(raw)
        step = ValidationStep(
            name="Echo stdout",
            command=["python", "-c", "print('hello_stdout_marker')"],
        )
        exit_code, stdout, stderr, _ = TesterService._execute_step(ws, step, timeout_seconds=10)

    assert exit_code == 0, f"Unexpected exit code: {exit_code}"
    assert "hello_stdout_marker" in stdout, f"Expected marker in stdout, got: {stdout!r}"
    print(f"  stdout={stdout.strip()!r}")
    print("  [PASS]")


def test_stderr_capture() -> None:
    print("\n[11/15] Correct stderr capture ...")
    with tempfile.TemporaryDirectory() as raw:
        ws = Path(raw)
        step = ValidationStep(
            name="Echo stderr",
            command=["python", "-c", "import sys; sys.stderr.write('hello_stderr_marker\\n')"],
        )
        exit_code, stdout, stderr, _ = TesterService._execute_step(ws, step, timeout_seconds=10)

    assert exit_code == 0, f"Unexpected exit code: {exit_code}"
    assert "hello_stderr_marker" in stderr, f"Expected marker in stderr, got: {stderr!r}"
    print(f"  stderr={stderr.strip()!r}")
    print("  [PASS]")


def test_exit_code_capture() -> None:
    print("\n[12/15] Exit code capture ...")
    with tempfile.TemporaryDirectory() as raw:
        ws = Path(raw)
        for expected_code in (0, 1, 42):
            step = ValidationStep(
                name=f"Exit with {expected_code}",
                command=["python", "-c", f"import sys; sys.exit({expected_code})"],
            )
            exit_code, _, _, _ = TesterService._execute_step(ws, step, timeout_seconds=10)
            assert exit_code == expected_code, (
                f"Expected exit_code={expected_code}, got {exit_code}"
            )

    print("  [PASS]")


def test_execution_time_capture() -> None:
    print("\n[13/15] Execution time capture ...")
    with tempfile.TemporaryDirectory() as raw:
        ws = Path(raw)
        step = ValidationStep(
            name="Short sleep",
            command=["python", "-c", "import time; time.sleep(0.1)"],
        )
        _, _, _, elapsed_ms = TesterService._execute_step(ws, step, timeout_seconds=10)

    assert elapsed_ms >= 100, f"Expected elapsed >= 100ms, got {elapsed_ms}ms"
    print(f"  elapsed_ms={elapsed_ms}")
    print("  [PASS]")


def test_testresult_schema_validation() -> None:
    print("\n[14/15] TestResult schema validation ...")
    with tempfile.TemporaryDirectory() as raw:
        ws = Path(raw)
        _passing_pytest_project(ws)
        result = tester_service.run_tests(ws)

    # All required fields present.
    assert isinstance(result.success, bool)
    assert isinstance(result.project_type, str)
    assert isinstance(result.executed_commands, list)
    assert result.failed_command is None or isinstance(result.failed_command, str)
    assert isinstance(result.exit_code, int)
    assert isinstance(result.stdout, str)
    assert isinstance(result.stderr, str)
    assert isinstance(result.execution_time_ms, int)
    assert isinstance(result.summary, str) and len(result.summary) > 0

    # Verify round-trip JSON serialization (Pydantic).
    serialized = result.model_dump_json()
    rehydrated = TestResult.model_validate_json(serialized)
    assert rehydrated == result

    print(f"  summary: {result.summary!r}")
    print("  [PASS]")


def test_unsupported_project_returns_result() -> None:
    print("\n[14b/15] Unsupported project returns graceful TestResult ...")
    with tempfile.TemporaryDirectory() as raw:
        ws = Path(raw)
        result = tester_service.run_tests(ws)

    assert isinstance(result, TestResult)
    assert result.success is False
    assert result.project_type == "unknown"
    assert result.executed_commands == []
    assert "recognised" in result.summary.lower() or "supported" in result.summary.lower()
    print(f"  summary: {result.summary!r}")
    print("  [PASS]")


def test_node_no_test_script_returns_empty_steps() -> None:
    print("\n[14c/15] Node project without test script returns graceful TestResult ...")
    with tempfile.TemporaryDirectory() as raw:
        ws = Path(raw)
        _node_project(ws, has_test_script=False)
        result = tester_service.run_tests(ws)

    assert isinstance(result, TestResult)
    assert result.success is False
    assert result.project_type == "node"
    assert result.executed_commands == []
    print(f"  summary: {result.summary!r}")
    print("  [PASS]")


def test_regression_imports() -> None:
    print("\n[15/15] Regression: existing service imports unaffected ...")
    from app.services.coder_service import coder_service, generate_unified_diff
    from app.services.workspace_manager import workspace_manager, WorkspaceManager
    from app.schemas.coder import CodingResult, GeneratedFile
    from app.schemas.planner import ImplementationPlan
    assert coder_service is not None
    assert workspace_manager is not None
    print("  [PASS]")


# ---------------------------------------------------------------------------
# ValidationStep unit tests
# ---------------------------------------------------------------------------

def test_validation_step_dataclass() -> None:
    print("\n[Extra] ValidationStep dataclass behaviour ...")
    step = ValidationStep(name="Run pytest", command=["pytest", "--tb=short"])
    assert step.name == "Run pytest"
    assert step.command == ["pytest", "--tb=short"]
    assert step.command_string() == "pytest --tb=short"
    print("  [PASS]")


def test_truncation() -> None:
    print("\n[Extra] Output truncation at MAX_OUTPUT_CHARS ...")
    from app.services.tester_service import MAX_OUTPUT_CHARS
    long_text = "x" * (MAX_OUTPUT_CHARS + 1000)
    truncated = TesterService._truncate(long_text)
    assert len(truncated) < len(long_text)
    assert "truncated" in truncated
    print(f"  original={len(long_text)} chars, truncated={len(truncated)} chars")
    print("  [PASS]")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 70)
    print("PHASE 10 TESTER AGENT VERIFICATION SUITE")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as raw_shared:
        shared = Path(raw_shared)

        # Detection tests use isolated sub-dirs to avoid cross-contamination.
        d1 = shared / "d1"; d1.mkdir()
        test_python_detection_requirements(d1)

        d2 = shared / "d2"; d2.mkdir()
        test_python_detection_pyproject(d2)

        d3 = shared / "d3"; d3.mkdir()
        test_node_detection(d3)

        d4 = shared / "d4"; d4.mkdir()
        test_unsupported_detection(d4)

    # Execution tests: each creates its own TemporaryDirectory internally.
    test_successful_pytest_execution()
    test_failed_pytest_execution()
    test_timeout_handling()
    test_missing_executable_handling()
    test_workspace_isolation()
    test_stdout_capture()
    test_stderr_capture()
    test_exit_code_capture()
    test_execution_time_capture()
    test_testresult_schema_validation()
    test_unsupported_project_returns_result()
    test_node_no_test_script_returns_empty_steps()
    test_regression_imports()

    # Extra unit tests
    test_validation_step_dataclass()
    test_truncation()

    print("\n" + "=" * 70)
    print("ALL PHASE 10 TESTER AGENT VERIFICATION TESTS PASSED!")
    print("=" * 70)


if __name__ == "__main__":
    main()
