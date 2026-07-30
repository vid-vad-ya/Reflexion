"""TesterService – Workspace Validation and Test Execution for Reflexion.

Orchestrates Phase 10 test execution:
1. Detects the project type from workspace sentinel files.
2. Builds an ordered list of ValidationStep objects.
3. Executes each ValidationStep sequentially inside the workspace.
4. Captures stdout, stderr, exit code, and elapsed time per step.
5. Returns a deterministic, LLM-free TestResult.

Key design constraints:
- No LLM calls.  All output is deterministic.
- Never writes to workspace files.
- Never installs packages or downloads anything.
- Always returns a TestResult — exceptions are caught and reflected in the result.
- Executes only inside the workspace created by WorkspaceManager.
"""

import json
import logging
import os
import platform
import shutil
import subprocess
import time
from pathlib import Path
from typing import List, Optional, Tuple, Union

from app.schemas.tester import TestResult, ValidationStep

logger = logging.getLogger("reflexion.services.tester")

# ---------------------------------------------------------------------------
# Module-level configuration
# ---------------------------------------------------------------------------

DEFAULT_TIMEOUT_SECONDS: int = 120    # Per-step wall-clock cap
MAX_OUTPUT_CHARS: int = 50_000        # Truncate very long stdout/stderr

# Sentinel files used to detect project type (checked in declaration order)
_PYTHON_SENTINELS = [
    "pyproject.toml",
    "setup.py",
    "requirements.txt",
    "pytest.ini",
    "setup.cfg",
]
_NODE_SENTINELS = ["package.json"]
_MAVEN_SENTINELS = ["pom.xml"]
_GRADLE_SENTINELS = ["build.gradle", "gradlew"]


# ---------------------------------------------------------------------------
# TesterService
# ---------------------------------------------------------------------------

class TesterService:
    """Service that validates generated code changes by executing test/build commands.

    Usage::

        from app.services.tester_service import tester_service

        result: TestResult = tester_service.run_tests(workspace_path)
        if result.success:
            ...

    The service is completely stateless.  A module-level singleton ``tester_service``
    is provided for convenience, but it is safe to instantiate multiple times.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_tests(
        self,
        workspace: Union[str, Path],
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> TestResult:
        """Detect the project type and execute all validation steps.

        Args:
            workspace: Absolute path to the isolated workspace created by
                ``WorkspaceManager``.  The original repository is never touched.
            timeout_seconds: Per-step timeout.  Defaults to 120 s.

        Returns:
            TestResult: Fully populated result object.  Never raises.
        """
        ws = Path(workspace).resolve()
        overall_start = time.monotonic()

        logger.info(f"TesterService: starting test run in workspace '{ws}'")

        # --- 1. Detect project type ---
        project_type = self._detect_project_type(ws)
        logger.info(f"Detected project type: '{project_type}'")

        # --- 2. Handle unsupported projects ---
        if project_type == "unknown":
            elapsed = int((time.monotonic() - overall_start) * 1000)
            return TestResult(
                success=False,
                project_type=project_type,
                executed_commands=[],
                failed_command=None,
                exit_code=-1,
                stdout="",
                stderr="",
                execution_time_ms=elapsed,
                summary=(
                    "No recognised project type detected in workspace. "
                    "Supported types: python, node, maven, gradle."
                ),
            )

        # --- 3. Build validation steps ---
        steps = self._build_validation_steps(ws, project_type)
        if not steps:
            elapsed = int((time.monotonic() - overall_start) * 1000)
            return TestResult(
                success=False,
                project_type=project_type,
                executed_commands=[],
                failed_command=None,
                exit_code=-1,
                stdout="",
                stderr="",
                execution_time_ms=elapsed,
                summary=(
                    f"Project type '{project_type}' detected but no executable "
                    "validation steps could be built (missing test script or framework)."
                ),
            )

        # --- 4. Execute steps sequentially ---
        executed_commands: List[str] = []
        failed_command: Optional[str] = None
        last_exit_code = 0
        last_stdout = ""
        last_stderr = ""

        for step in steps:
            cmd_str = step.command_string()
            logger.info(f"Executing step '{step.name}': {cmd_str}")

            exit_code, stdout, stderr, elapsed_step_ms = self._execute_step(
                ws, step, timeout_seconds
            )
            executed_commands.append(cmd_str)
            last_exit_code = exit_code
            last_stdout = stdout
            last_stderr = stderr

            if exit_code != 0:
                failed_command = cmd_str
                logger.warning(
                    f"Step '{step.name}' failed with exit code {exit_code}."
                )
                break  # Stop-on-first-failure

        overall_elapsed = int((time.monotonic() - overall_start) * 1000)
        success = last_exit_code == 0

        summary = self._build_summary(
            project_type=project_type,
            steps=steps,
            executed_commands=executed_commands,
            success=success,
            failed_command=failed_command,
            exit_code=last_exit_code,
            elapsed_ms=overall_elapsed,
        )

        logger.info(
            f"Test run complete: success={success}, exit_code={last_exit_code}, "
            f"elapsed={overall_elapsed}ms"
        )

        return TestResult(
            success=success,
            project_type=project_type,
            executed_commands=executed_commands,
            failed_command=failed_command,
            exit_code=last_exit_code,
            stdout=self._truncate(last_stdout),
            stderr=self._truncate(last_stderr),
            execution_time_ms=overall_elapsed,
            summary=summary,
        )

    def detect_project_type(self, workspace: Union[str, Path]) -> str:
        """Public thin wrapper around _detect_project_type for testability.

        Args:
            workspace: Path to the workspace or any directory to inspect.

        Returns:
            str: One of 'python', 'node', 'maven', 'gradle', 'unknown'.
        """
        return self._detect_project_type(Path(workspace).resolve())

    # ------------------------------------------------------------------
    # Private: Detection
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_project_type(workspace: Path) -> str:
        """Inspect workspace root for well-known sentinel files.

        Returns the project type string for the first match found.
        """
        for sentinel in _PYTHON_SENTINELS:
            if (workspace / sentinel).exists():
                logger.debug(f"Python project detected via sentinel '{sentinel}'")
                return "python"

        for sentinel in _NODE_SENTINELS:
            if (workspace / sentinel).exists():
                logger.debug(f"Node project detected via sentinel '{sentinel}'")
                return "node"

        for sentinel in _MAVEN_SENTINELS:
            if (workspace / sentinel).exists():
                logger.debug(f"Maven project detected via sentinel '{sentinel}'")
                return "maven"

        for sentinel in _GRADLE_SENTINELS:
            if (workspace / sentinel).exists():
                logger.debug(f"Gradle project detected via sentinel '{sentinel}'")
                return "gradle"

        return "unknown"

    # ------------------------------------------------------------------
    # Private: Step building
    # ------------------------------------------------------------------

    @staticmethod
    def _build_validation_steps(workspace: Path, project_type: str) -> List[ValidationStep]:
        """Build an ordered list of ValidationStep objects for the detected project type.

        Only test/build commands relevant to Phase 10 are included.  The
        architecture intentionally supports more steps in future phases (e.g. Ruff,
        MyPy, custom commands) without changing TesterService.run_tests().

        Args:
            workspace: Workspace root (used to inspect config files).
            project_type: Result of _detect_project_type().

        Returns:
            List[ValidationStep]: Ordered steps to execute.  May be empty.
        """
        if project_type == "python":
            return TesterService._build_python_steps(workspace)
        elif project_type == "node":
            return TesterService._build_node_steps(workspace)
        elif project_type == "maven":
            return [
                ValidationStep(
                    name="Run Maven tests",
                    command=["mvn", "test", "-B"],
                )
            ]
        elif project_type == "gradle":
            gradlew = TesterService._gradle_executable(workspace)
            return [
                ValidationStep(
                    name="Run Gradle tests",
                    command=[gradlew, "test"],
                )
            ]
        return []

    @staticmethod
    def _build_python_steps(workspace: Path) -> List[ValidationStep]:
        """Return pytest step, preferring the binary over the module invocation."""
        # Prefer the pytest binary when it is available on PATH.
        if shutil.which("pytest") is not None:
            return [
                ValidationStep(
                    name="Run pytest",
                    command=["pytest", "--tb=short", "-q"],
                )
            ]
        # Fall back to running as a module (works when pytest is installed but
        # not on PATH, e.g. inside a venv without activation).
        return [
            ValidationStep(
                name="Run pytest (module fallback)",
                command=["python", "-m", "pytest", "--tb=short", "-q"],
            )
        ]

    @staticmethod
    def _build_node_steps(workspace: Path) -> List[ValidationStep]:
        """Return npm test step if package.json declares a test script."""
        pkg_json = workspace / "package.json"
        try:
            data = json.loads(pkg_json.read_text(encoding="utf-8"))
            scripts = data.get("scripts", {})
            if "test" not in scripts:
                logger.info(
                    "package.json found but no 'test' script defined; "
                    "returning empty step list."
                )
                return []
        except Exception as exc:
            logger.warning(f"Could not parse package.json: {exc}")
            return []

        return [
            ValidationStep(
                name="Run npm test",
                command=["npm", "test", "--", "--watchAll=false"],
            )
        ]

    @staticmethod
    def _gradle_executable(workspace: Path) -> str:
        """Return platform-appropriate Gradle wrapper executable name."""
        if platform.system() == "Windows":
            if (workspace / "gradlew.bat").exists():
                return "gradlew.bat"
        if (workspace / "gradlew").exists():
            return "./gradlew"
        return "gradle"  # Last resort: system Gradle

    # ------------------------------------------------------------------
    # Private: Execution
    # ------------------------------------------------------------------

    @staticmethod
    def _execute_step(
        workspace: Path,
        step: ValidationStep,
        timeout_seconds: int,
    ) -> Tuple[int, str, str, int]:
        """Run one ValidationStep inside the workspace using subprocess.

        Args:
            workspace: Working directory for the subprocess.
            step: The ValidationStep to execute.
            timeout_seconds: Hard wall-clock timeout in seconds.

        Returns:
            Tuple of (exit_code, stdout, stderr, elapsed_ms).
            Negative exit codes signal internal error states:
              -1 = timeout
              -2 = executable not found (FileNotFoundError)
              -3 = unexpected OS / subprocess exception
        """
        start = time.monotonic()
        cmd = step.command

        try:
            proc = subprocess.run(
                cmd,
                cwd=str(workspace),
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                # Prevent the subprocess from inheriting interactive terminal
                # settings that could cause hangs on Windows.
                stdin=subprocess.DEVNULL,
            )
            elapsed = int((time.monotonic() - start) * 1000)
            return proc.returncode, proc.stdout, proc.stderr, elapsed

        except subprocess.TimeoutExpired:
            elapsed = int((time.monotonic() - start) * 1000)
            msg = (
                f"Process timed out after {timeout_seconds}s: "
                f"{step.command_string()}"
            )
            logger.warning(msg)
            return -1, "", msg, elapsed

        except FileNotFoundError:
            elapsed = int((time.monotonic() - start) * 1000)
            msg = f"Executable not found: '{cmd[0]}'"
            logger.error(msg)
            return -2, "", msg, elapsed

        except Exception as exc:
            elapsed = int((time.monotonic() - start) * 1000)
            msg = f"Unexpected error running '{step.command_string()}': {exc}"
            logger.error(msg)
            return -3, "", msg, elapsed

    # ------------------------------------------------------------------
    # Private: Summary generation
    # ------------------------------------------------------------------

    @staticmethod
    def _build_summary(
        project_type: str,
        steps: List[ValidationStep],
        executed_commands: List[str],
        success: bool,
        failed_command: Optional[str],
        exit_code: int,
        elapsed_ms: int,
    ) -> str:
        """Produce a short deterministic human-readable summary.  No LLM."""
        total_steps = len(steps)
        executed = len(executed_commands)
        elapsed_s = elapsed_ms / 1000.0

        if success:
            return (
                f"All {executed} validation step(s) passed for "
                f"'{project_type}' project in {elapsed_s:.2f}s."
            )

        # Map special exit codes to readable reasons.
        if exit_code == -1:
            reason = f"timed out (limit: {DEFAULT_TIMEOUT_SECONDS}s)"
        elif exit_code == -2:
            reason = "executable not found"
        elif exit_code == -3:
            reason = "unexpected subprocess error"
        else:
            reason = f"exited with code {exit_code}"

        skipped = total_steps - executed
        skipped_note = f" ({skipped} step(s) skipped)" if skipped > 0 else ""
        return (
            f"Validation failed for '{project_type}' project: "
            f"command '{failed_command}' {reason} "
            f"after {elapsed_s:.2f}s{skipped_note}."
        )

    # ------------------------------------------------------------------
    # Private: Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _truncate(text: str, max_chars: int = MAX_OUTPUT_CHARS) -> str:
        """Truncate long output strings to avoid bloated TestResult objects."""
        if len(text) <= max_chars:
            return text
        ellipsis = f"\n... [output truncated at {max_chars} chars] ..."
        return text[:max_chars] + ellipsis


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

tester_service = TesterService()
