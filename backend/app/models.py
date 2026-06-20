"""
models.py – SQLModel ORM definitions for the Reflexion application.

Four core entities are defined here:
    User        – A GitHub-authenticated user account.
    Repository  – A GitHub repository registered for agent processing.
    Task        – A high-level instruction submitted against a repository.
    Attempt     – A single agent execution cycle for a Task (1 task : N attempts).

Design notes:
    • All primary keys are UUIDs (generated server-side via uuid4).
    • created_at / updated_at are server-default UTC timestamps.
    • updated_at is automatically refreshed via SQLAlchemy's onupdate hook.
    • Foreign keys use the "user.id" / "repository.id" / "task.id" notation,
      matching the lowercase table names SQLModel generates automatically.
    • sa_column_kwargs exposes raw SQLAlchemy Column options (index, nullable,
      server_default) that are not directly expressible in SQLModel's Field().
    • Relationships are declared as Optional so that partial hydration works
      without eager-loading every related object.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from sqlalchemy import BigInteger, Column, DateTime, Index, String, func, text
from sqlmodel import Field, Relationship, SQLModel


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class TaskStatus(str, Enum):
    """Lifecycle states of a Task."""
    PENDING   = "pending"
    RUNNING   = "running"
    SUCCEEDED = "succeeded"
    FAILED    = "failed"
    CANCELLED = "cancelled"


class AttemptStatus(str, Enum):
    """Outcome of a single agent execution Attempt."""
    RUNNING   = "running"
    SUCCEEDED = "succeeded"
    FAILED    = "failed"


# ---------------------------------------------------------------------------
# Shared timestamp mixin (not a SQLModel table itself)
# ---------------------------------------------------------------------------

class TimestampMixin(SQLModel):
    """
    Provides created_at and updated_at columns backed by server-side
    PostgreSQL defaults so the application never needs to set them manually.

    IMPORTANT: We use sa_type and sa_column_kwargs instead of sa_column=Column(...)
    because sa_column=Column(...) evaluates to a single Column instance when the
    mixin class is defined. That instance gets reused across all tables inheriting
    from the mixin, which causes SQLAlchemy's ArgumentError.
    
    Using sa_type and sa_column_kwargs acts as a recipe, so SQLModel constructs
    a unique, fresh Column instance for each table class.
    """
    created_at: Optional[datetime] = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={
            "server_default": func.now(),
            "nullable": False,
        },
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        sa_column_kwargs={
            "server_default": func.now(),
            "onupdate": func.now(),
            "nullable": False,
        },
    )


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class User(TimestampMixin, table=True):
    """
    Represents a GitHub-authenticated user.

    Indexes:
        • github_id  – unique look-up during OAuth callback.
        • email      – unique enforcement + common query field.
    """

    __tablename__ = "user"

    # PK
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=False,          # PK already has a B-tree index
        nullable=False,
    )

    # Identity
    github_id: int = Field(
        sa_column=Column(
            "github_id",
            BigInteger,
            nullable=False,
            unique=True,
            index=True,
        )
    )
    username: str = Field(
        sa_column=Column(String(255), nullable=False, unique=True, index=True)
    )
    email: Optional[str] = Field(
        default=None,
        sa_column=Column(String(320), nullable=True, unique=True, index=True),
    )
    avatar_url: Optional[str] = Field(default=None, max_length=2048)

    # GitHub OAuth tokens (store encrypted in production)
    github_access_token: Optional[str] = Field(default=None, max_length=512)

    # Relationships
    repositories: List["Repository"] = Relationship(back_populates="owner")
    tasks: List["Task"] = Relationship(back_populates="user")


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------

class Repository(TimestampMixin, table=True):
    """
    A GitHub repository that a user has linked for agent processing.

    Indexes:
        • (owner_id, full_name)  – composite; most queries filter by owner
          and repo name together.
        • full_name              – standalone index for cross-user look-ups.
    """

    __tablename__ = "repository"

    __table_args__ = (
        Index("ix_repository_owner_full_name", "owner_id", "full_name"),
    )

    # PK
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        nullable=False,
    )

    # FK → User
    owner_id: uuid.UUID = Field(
        foreign_key="user.id",
        nullable=False,
        index=True,
    )

    # GitHub metadata
    github_repo_id: int = Field(
        sa_column=Column(
            "github_repo_id",
            BigInteger,
            nullable=False,
            unique=True,
            index=True,
        )
    )
    full_name: str = Field(
        sa_column=Column(String(512), nullable=False, index=True)
    )                                           # e.g. "octocat/Hello-World"
    clone_url: str  = Field(max_length=2048)
    default_branch: str = Field(default="main", max_length=255)
    is_private: bool = Field(default=False)

    # Relationships
    owner: Optional[User] = Relationship(back_populates="repositories")
    tasks: List["Task"] = Relationship(back_populates="repository")


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

class Task(TimestampMixin, table=True):
    """
    A high-level natural-language instruction submitted by a user against a
    specific repository.  One Task can spawn multiple Attempts (retries).

    Indexes:
        • (user_id, status)       – dashboard queries filter by owner + status.
        • (repository_id, status) – repo-scoped task lists.
        • status                  – admin / worker queue polling.
    """

    __tablename__ = "task"

    __table_args__ = (
        Index("ix_task_user_status",       "user_id",       "status"),
        Index("ix_task_repository_status", "repository_id", "status"),
    )

    # PK
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        nullable=False,
    )

    # FKs
    user_id: uuid.UUID = Field(
        foreign_key="user.id",
        nullable=False,
        index=True,
    )
    repository_id: uuid.UUID = Field(
        foreign_key="repository.id",
        nullable=False,
        index=True,
    )

    # Task description
    title: str = Field(max_length=512)
    description: str = Field(default="")       # full natural-language prompt

    # Lifecycle
    status: TaskStatus = Field(
        default=TaskStatus.PENDING,
        sa_column=Column(
            String(32),
            nullable=False,
            index=True,
            server_default=text("'pending'"),
        ),
    )
    max_attempts: int = Field(default=3)
    target_branch: Optional[str] = Field(default=None, max_length=255)

    # Output – filled in after the agent succeeds
    pull_request_url: Optional[str]    = Field(default=None, max_length=2048)
    pull_request_number: Optional[int] = Field(default=None)

    # Relationships
    user:       Optional[User]       = Relationship(back_populates="tasks")
    repository: Optional[Repository] = Relationship(back_populates="tasks")
    attempts:   List["Attempt"]      = Relationship(back_populates="task")


# ---------------------------------------------------------------------------
# Attempt
# ---------------------------------------------------------------------------

class Attempt(TimestampMixin, table=True):
    """
    A single end-to-end agent execution cycle for a Task.

    One Task may have many Attempts (up to Task.max_attempts) when the agent
    fails and retries.  Each Attempt captures the full lifecycle output for
    observability and debugging.

    Indexes:
        • (task_id, attempt_number)  – unique constraint + ordered look-up.
        • (task_id, status)          – filter running / failed attempts.
    """

    __tablename__ = "attempt"

    __table_args__ = (
        Index("ix_attempt_task_number", "task_id", "attempt_number", unique=True),
        Index("ix_attempt_task_status", "task_id", "status"),
    )

    # PK
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        nullable=False,
    )

    # FK → Task
    task_id: uuid.UUID = Field(
        foreign_key="task.id",
        nullable=False,
        index=True,
    )

    # Sequence within the parent task (1-based)
    attempt_number: int = Field(default=1, ge=1)

    # Lifecycle
    status: AttemptStatus = Field(
        default=AttemptStatus.RUNNING,
        sa_column=Column(
            String(32),
            nullable=False,
            index=True,
            server_default=text("'running'"),
        ),
    )

    # Branch created for this attempt
    branch_name: Optional[str] = Field(default=None, max_length=255)

    # LangGraph / agent output (stored as JSON text for portability)
    plan_json:        Optional[str] = Field(default=None)   # agent plan
    patch_diff:       Optional[str] = Field(default=None)   # unified diff
    build_log:        Optional[str] = Field(default=None)   # build output
    test_log:         Optional[str] = Field(default=None)   # test output
    reflection_notes: Optional[str] = Field(default=None)   # LLM reflection

    # Error capture
    error_message: Optional[str] = Field(default=None, max_length=4096)

    # Relationship
    task: Optional[Task] = Relationship(back_populates="attempts")
