"""Schemas for the Reflector Agent (Phase 11).

Defines:
- FailureCategory: Enums for standardized failure categories.
- RetryScope: Enums for scope of code regeneration required.
- ReflectionResult: Public Pydantic response model returned by ReflectorService.
"""

from enum import Enum
from typing import List
from typing_extensions import Annotated

from pydantic import BaseModel, Field, field_validator


class FailureCategory(str, Enum):
    """Standardized failure classification categories."""

    IMPORT_ERROR = "ImportError"
    SYNTAX_ERROR = "SyntaxError"
    TYPE_ERROR = "TypeError"
    ASSERTION_ERROR = "AssertionError"
    BUILD_FAILURE = "BuildFailure"
    TEST_FAILURE = "TestFailure"
    MISSING_DEPENDENCY = "MissingDependency"
    TIMEOUT = "Timeout"
    UNSUPPORTED_PROJECT = "UnsupportedProject"
    ENVIRONMENT_ERROR = "EnvironmentError"
    UNKNOWN = "Unknown"


class RetryScope(str, Enum):
    """Scope of regeneration suggested for the next coding attempt."""

    SINGLE_FILE = "single_file"
    MULTIPLE_FILES = "multiple_files"
    FULL_REGENERATION = "full_regeneration"


class ReflectionResult(BaseModel):
    """Structured outcome produced by ReflectorService after analyzing a failed execution.

    The Reflector Agent strictly analyzes failure causes and recommends targeted repairs.
    It never generates code, modifies files, or executes commands.
    """

    should_retry: bool = Field(
        ...,
        description=(
            "True if the failure appears repairable (e.g. ImportError, SyntaxError, AssertionError). "
            "False if unrecoverable (e.g. UnsupportedProject, environment timeout, corrupted workspace)."
        ),
    )
    failure_category: FailureCategory = Field(
        ...,
        description="Exactly one standardized category describing the root cause of failure.",
    )
    retry_scope: RetryScope = Field(
        ...,
        description="Suggested scope of files to regenerate in the next coding attempt.",
    )
    root_cause: str = Field(
        ...,
        description="Detailed technical explanation pinpointing why the implementation failed.",
    )
    recommendations: List[str] = Field(
        default_factory=list,
        description="Concise, actionable repair recommendations for the next coding attempt (maximum 5).",
    )
    affected_files: List[str] = Field(
        default_factory=list,
        description="Minimal list of relative file paths that caused the failure and require modification.",
    )
    confidence: Annotated[
        float,
        Field(
            ...,
            ge=0.0,
            le=1.0,
            description="Confidence score between 0.0 and 1.0 reflecting certainty of analysis.",
        ),
    ]
    reasoning: str = Field(
        ...,
        description="Engineering rationale justifying the category, retry decision, and scope.",
    )

    @field_validator("recommendations")
    @classmethod
    def limit_recommendations(cls, v: List[str]) -> List[str]:
        """Ensure recommendations list contains at most 5 items."""
        if len(v) > 5:
            return v[:5]
        return v
