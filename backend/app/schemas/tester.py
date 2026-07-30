"""Schemas for the Tester Agent (Phase 10).

Defines:
- ValidationStep: Internal dataclass representing one executable test/build step.
- TestResult: Public Pydantic response model returned by TesterService.
"""

from dataclasses import dataclass, field
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Internal: ValidationStep
# ---------------------------------------------------------------------------

@dataclass
class ValidationStep:
    """A single executable validation step run inside the workspace.

    ValidationStep is an internal dataclass — it is never serialized or
    returned through an API.  TesterService builds a list of these and
    executes them sequentially, stopping on the first failure.

    Keeping this as a dataclass (not a Pydantic model) preserves a clear
    boundary between internal pipeline abstractions and public API schemas.

    Attributes:
        name: Human-readable label shown in logs and the TestResult summary.
            Examples: "Run pytest", "Run npm test", "Run mvn test".
        command: argv list passed directly to subprocess.
            Examples: ["pytest", "--tb=short"], ["npm", "test"].
    """

    name: str
    command: List[str] = field(default_factory=list)

    def command_string(self) -> str:
        """Return the command as a single display string."""
        return " ".join(self.command)


# ---------------------------------------------------------------------------
# Public: TestResult
# ---------------------------------------------------------------------------

class TestResult(BaseModel):
    """Structured outcome produced by TesterService after running all validation steps.

    This schema is the sole output contract of the Tester Agent.  All fields
    are deterministically populated by the backend — no LLM is involved.
    """

    success: bool = Field(
        ...,
        description=(
            "True if every validation step completed with exit code 0. "
            "False if any step failed, timed out, or the project type is unsupported."
        ),
    )
    project_type: str = Field(
        ...,
        description=(
            "Detected project type: 'python', 'node', 'maven', 'gradle', or 'unknown'. "
            "Detection is based on sentinel files found at the workspace root."
        ),
    )
    executed_commands: List[str] = Field(
        default_factory=list,
        description="Ordered list of every command string that was actually invoked.",
    )
    failed_command: Optional[str] = Field(
        default=None,
        description=(
            "The command string of the first validation step that failed. "
            "None when success is True."
        ),
    )
    exit_code: int = Field(
        ...,
        description=(
            "Exit code of the last executed command. "
            "0 indicates success. "
            "Negative values are reserved for internal error states: "
            "-1 = timeout, -2 = executable not found, -3 = unexpected OS error."
        ),
    )
    stdout: str = Field(
        default="",
        description="Captured standard output from the last executed command (may be truncated).",
    )
    stderr: str = Field(
        default="",
        description="Captured standard error from the last executed command (may be truncated).",
    )
    execution_time_ms: int = Field(
        ...,
        description="Total wall-clock execution time in milliseconds across all steps.",
    )
    summary: str = Field(
        ...,
        description=(
            "Deterministic backend-generated human-readable summary of the test run. "
            "No LLM is used."
        ),
    )
