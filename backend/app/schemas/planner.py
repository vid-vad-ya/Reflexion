"""Shared Pydantic Schemas for the Planner Agent.

Defines ImplementationPlan and API payload models used by PlannerService,
FastAPI endpoints, and downstream execution agents.
"""

from typing import List, Literal
from pydantic import BaseModel, Field


class ImplementationPlan(BaseModel):
    """Structured architectural implementation plan produced by the Planner Agent.

    Contains detailed breakdown of affected components, files, dependencies, database
    and environment changes, step-by-step implementation order, risks, assumptions,
    complexity rating, file count estimate, and architectural reasoning.
    """

    goal: str = Field(..., description="High-level objective of the requested feature or codebase change")
    summary: str = Field(..., description="Executive summary of the architectural strategy")
    affected_components: List[str] = Field(
        default_factory=list,
        description="High-level logical components affected (e.g. ['API', 'Database', 'Authentication', 'Frontend'])",
    )
    affected_files: List[str] = Field(
        default_factory=list,
        description="Existing files that will need to be modified",
    )
    new_files: List[str] = Field(
        default_factory=list,
        description="New files that need to be created",
    )
    dependencies: List[str] = Field(
        default_factory=list,
        description="New packages, libraries, or external dependencies required",
    )
    database_changes: List[str] = Field(
        default_factory=list,
        description="Database schema, table, migration, or ORM model changes required",
    )
    environment_changes: List[str] = Field(
        default_factory=list,
        description="Environment variables, configuration, or infrastructure changes required",
    )
    implementation_steps: List[str] = Field(
        default_factory=list,
        description="Ordered step-by-step instructions for implementing the change",
    )
    risks: List[str] = Field(
        default_factory=list,
        description="Potential risks, edge cases, breaking changes, or trade-offs",
    )
    assumptions: List[str] = Field(
        default_factory=list,
        description="Explicit assumptions made while producing the implementation plan",
    )
    complexity: Literal["Low", "Medium", "High"] = Field(
        ...,
        description="Estimated implementation complexity: Low, Medium, or High",
    )
    estimated_files_changed: int = Field(
        ...,
        description="Total estimated number of files created or modified",
    )
    reasoning: str = Field(
        ...,
        description="Architectural reasoning and design decisions behind this strategy",
    )


class PlannerRequest(BaseModel):
    """API request payload for generating an implementation plan."""

    request: str = Field(
        ...,
        min_length=1,
        description="Natural language feature request or architectural change",
    )
