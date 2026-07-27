"""Shared Pydantic Schemas for Repository Analysis.

All repository analysis schemas (ProjectSummary, TechnologyDetection, EntryPoint, DirectoryNode)
are defined here to maintain clean separation between service logic and data contracts.
Downstream agents (Planner, Coder, Reflector) and API routers consume these models directly.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class DirectoryNode(BaseModel):
    """Represents a node in the directory tree structure."""

    name: str = Field(..., description="Basename of the directory or file")
    path: str = Field(..., description="Relative path from workspace root")
    is_dir: bool = Field(..., description="True if node is a directory, False if file")
    children: Optional[List["DirectoryNode"]] = Field(None, description="Child nodes if directory")
    file_count: Optional[int] = Field(None, description="Total files contained directly/recursively")


DirectoryNode.model_rebuild()


class TechnologyDetection(BaseModel):
    """Extensible representation of a detected technology, language, or framework."""

    name: str = Field(..., description="Technology name (e.g. FastAPI, Python, PostgreSQL)")
    category: str = Field(
        ...,
        description="Category (e.g. Language, Framework, Database, ORM, Authentication, AI, Testing, Deployment, Package Manager, CI/CD)",
    )
    detected_from: List[str] = Field(
        default_factory=list,
        description="Evidence files or heuristics used for detection (e.g. ['requirements.txt', 'Dockerfile'])",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence level of detection between 0.0 and 1.0",
    )


class EntryPoint(BaseModel):
    """Extensible representation of an application entry point."""

    path: str = Field(..., description="Relative file path to entry point file (e.g. main.py, src/index.ts)")
    description: Optional[str] = Field(None, description="Description or role of entry point")
    detected_from: Optional[str] = Field(None, description="Detection evidence (e.g. 'Heuristic', 'package.json main')")


class HeuristicAnalysisResult(BaseModel):
    """Intermediate container storing Stage 1 deterministic analysis results before LLM processing."""

    directory_tree: DirectoryNode = Field(..., description="Clean directory tree representation")
    important_directories: List[str] = Field(default_factory=list, description="Key directories identified in workspace")
    important_files: List[str] = Field(default_factory=list, description="Important config/manifest files detected")
    collected_file_contents: Dict[str, str] = Field(
        default_factory=dict,
        description="Truncated contents of important files used for heuristic matching",
    )
    languages: List[str] = Field(default_factory=list, description="Detected programming languages")
    frameworks: List[str] = Field(default_factory=list, description="Detected web/app frameworks")
    package_manager: Optional[str] = Field(None, description="Primary package manager detected")
    database: Optional[str] = Field(None, description="Primary database detected")
    orm: Optional[str] = Field(None, description="Primary ORM/ODM detected")
    authentication: Optional[str] = Field(None, description="Primary authentication mechanism or library")
    ai_stack: List[str] = Field(default_factory=list, description="Detected AI / ML libraries")
    testing_frameworks: List[str] = Field(default_factory=list, description="Detected testing frameworks")
    deployment: Optional[str] = Field(None, description="Detected deployment / containerization setup")
    entry_points: List[EntryPoint] = Field(default_factory=list, description="Detected entry point files")
    technologies: List[TechnologyDetection] = Field(default_factory=list, description="List of all detected technologies")


class LLMProjectSummaryResponse(BaseModel):
    """Flat Pydantic model for Gemini structured JSON generation.

    Uses str with empty-string defaults instead of Optional[str] to avoid
    Gemini API schema incompatibilities with nullable fields (anyOf null type).
    Consumers must treat empty string as None equivalent.
    """

    project_name: str = Field(default="", description="High-level project name")
    description: str = Field(default="", description="Concise overview of project purpose and functionality")
    architecture: str = Field(default="", description="High-level architectural pattern (empty string if unknown)")
    observations: List[str] = Field(default_factory=list, description="Key high-level architectural insights")
    languages: List[str] = Field(default_factory=list)
    frameworks: List[str] = Field(default_factory=list)
    package_manager: str = Field(default="", description="Primary package manager or empty string if none")
    database: str = Field(default="", description="Primary database or empty string if none")
    orm: str = Field(default="", description="ORM used or empty string if none")
    authentication: str = Field(default="", description="Authentication mechanism or empty string if none")
    ai_stack: List[str] = Field(default_factory=list)
    testing_frameworks: List[str] = Field(default_factory=list)
    deployment: str = Field(default="", description="Deployment technology or empty string if none")
    important_directories: List[str] = Field(default_factory=list)
    important_files: List[str] = Field(default_factory=list)


class ProjectSummary(BaseModel):
    """Structured summary of a repository produced by RepositoryAnalyzer.

    This model serves as the primary technical context consumed by downstream
    agents (Planner, Coder, Tester, Reflector).
    """

    project_name: str = Field(..., description="High-level project name or directory name")
    description: str = Field(..., description="Concise overview of project purpose and functionality")
    languages: List[str] = Field(default_factory=list, description="Programming languages used in repository")
    frameworks: List[str] = Field(default_factory=list, description="Frameworks used (e.g. FastAPI, Next.js, React)")
    package_manager: Optional[str] = Field(None, description="Primary package manager (e.g. pip, npm, poetry, yarn)")
    database: Optional[str] = Field(None, description="Database used (e.g. PostgreSQL, SQLite, MongoDB)")
    orm: Optional[str] = Field(None, description="ORM used (e.g. SQLAlchemy, SQLModel, Prisma)")
    authentication: Optional[str] = Field(None, description="Authentication mechanisms detected")
    ai_stack: List[str] = Field(default_factory=list, description="AI/ML stack components detected")
    testing_frameworks: List[str] = Field(default_factory=list, description="Testing tools and frameworks")
    deployment: Optional[str] = Field(None, description="Deployment and containerization technology")
    architecture: Optional[str] = Field(None, description="High-level architectural pattern (e.g. Monorepo, Microservice, REST API)")
    important_directories: List[str] = Field(default_factory=list, description="Key functional directories")
    important_files: List[str] = Field(default_factory=list, description="Key configuration and manifest files")
    entry_points: List[EntryPoint] = Field(default_factory=list, description="Identified entry points into application execution")
    technologies: List[TechnologyDetection] = Field(default_factory=list, description="Extensible list of all detected technologies")
    observations: List[str] = Field(default_factory=list, description="Key high-level architectural insights and observations")
