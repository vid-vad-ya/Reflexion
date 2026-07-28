"""API endpoints for repository workspace management and repository analysis."""

import logging
import os
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.database import get_session
from app.models import Repository
from app.schemas.repository import ProjectSummary
from app.services.git_service import (
    git_service,
    GitServiceError,
    InvalidRepositoryURLError,
    RepositoryNotFoundError,
    GitAuthenticationError,
    CloneFailureError,
    WorkspaceCreationError,
)
from app.services.repository_analyzer import (
    repository_analyzer,
    RepositoryAnalysisError,
    WorkspaceNotFoundError,
    ProjectDetectionError,
)

logger = logging.getLogger("reflexion.api.repositories")

router = APIRouter()


class RepositoryCloneRequest(BaseModel):
    repository_url: str = Field(..., description="Git clone URL (HTTPS or SSH)")
    repository_name: str = Field(..., description="Name of the repository")
    owner: Optional[str] = Field(None, description="Repository owner or organization name")
    owner_id: uuid.UUID = Field(..., description="UUID of the authenticated User who owns this repository")
    github_repo_id: Optional[int] = Field(
        None,
        description="Numeric GitHub repository ID. If omitted, a stable synthetic ID is derived from full_name.",
    )
    is_private: bool = Field(False, description="Whether the repository is private on GitHub")
    access_token: Optional[str] = Field(None, description="Optional GitHub access token for private repositories")


class RepositoryCloneResponse(BaseModel):
    status: str = Field("success", description="Status of the operation")
    repository_id: uuid.UUID = Field(..., description="Database UUID of the Repository record")
    workspace: str = Field(..., description="Local workspace filesystem path")
    default_branch: str = Field(..., description="Active default branch name")
    already_exists: bool = Field(..., description="True if workspace existed prior to clone request")


class RepositoryAnalyzeRequest(BaseModel):
    repository_id: uuid.UUID = Field(..., description="Database UUID identifier of the repository")
    force_refresh: bool = Field(False, description="If True, re-runs analysis bypassing cached ProjectSummary")


@router.post("/clone", response_model=RepositoryCloneResponse, status_code=status.HTTP_200_OK)
def clone_repository(
    payload: RepositoryCloneRequest,
    session: Session = Depends(get_session),
):
    """Clone a Git repository into the local workspace directory and persist a Repository DB record.

    If the repository workspace already exists locally, the existing workspace is reused.
    In both cases, the Repository DB record is upserted (created on first clone, updated on re-clone)
    so that downstream services (RepositoryAnalyzer, Planner, Coder) can always look up by UUID.
    """
    # Derive full_name (e.g. "octocat/Hello-World")
    owner_slug = payload.owner or "standalone"
    full_name = f"{owner_slug}/{payload.repository_name}"

    import hashlib

    # Derive a stable synthetic github_repo_id when not provided.
    # Uses a deterministic SHA-256 digest of full_name to guarantee uniqueness per repo
    # and consistency across process restarts.
    if payload.github_repo_id is not None:
        effective_github_repo_id = payload.github_repo_id
    else:
        digest = hashlib.sha256(full_name.encode("utf-8")).hexdigest()
        effective_github_repo_id = int(digest, 16) % (10 ** 15)

    try:
        clone_result = git_service.clone_repository(
            repository_url=payload.repository_url,
            repository_name=payload.repository_name,
            owner=payload.owner,
            access_token=payload.access_token,
        )
    except InvalidRepositoryURLError as e:
        logger.warning(f"Invalid repository URL: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except GitAuthenticationError as e:
        logger.warning(f"Git authentication failed: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except RepositoryNotFoundError as e:
        logger.warning(f"Repository not found: {e}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (CloneFailureError, WorkspaceCreationError) as e:
        logger.error(f"Clone operation failed: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except GitServiceError as e:
        logger.error(f"Git service error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during repository clone: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during repository clone.",
        )

    workspace_path: str = clone_result["workspace"]
    default_branch: str = clone_result["default_branch"]
    already_exists: bool = clone_result["already_exists"]

    # -------------------------------------------------------------------------
    # Upsert Repository DB record
    # Look up by full_name first so that repeated clone calls do not create
    # duplicate rows. If found, update mutable fields. If not found, create.
    # -------------------------------------------------------------------------
    try:
        existing_repo = session.exec(
            select(Repository).where(Repository.full_name == full_name)
        ).first()

        if existing_repo:
            # Update fields that may have changed (e.g. new branch, new workspace path)
            existing_repo.local_path = workspace_path
            existing_repo.default_branch = default_branch
            existing_repo.clone_status = "completed"
            existing_repo.clone_url = payload.repository_url
            session.add(existing_repo)
            session.commit()
            session.refresh(existing_repo)
            repo_record = existing_repo
            logger.info(
                f"Updated existing Repository DB record '{repo_record.id}' for '{full_name}'."
            )
        else:
            repo_record = Repository(
                owner_id=payload.owner_id,
                github_repo_id=effective_github_repo_id,
                full_name=full_name,
                clone_url=payload.repository_url,
                default_branch=default_branch,
                is_private=payload.is_private,
                local_path=workspace_path,
                clone_status="completed",
            )
            session.add(repo_record)
            session.commit()
            session.refresh(repo_record)
            logger.info(
                f"Created new Repository DB record '{repo_record.id}' for '{full_name}'."
            )
    except Exception as e:
        logger.error(f"Failed to persist Repository record to DB for '{full_name}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Repository cloned successfully but failed to persist DB record: {str(e)}",
        )

    return RepositoryCloneResponse(
        status="success",
        repository_id=repo_record.id,
        workspace=workspace_path,
        default_branch=default_branch,
        already_exists=already_exists,
    )


@router.post("/analyze", response_model=ProjectSummary, status_code=status.HTTP_200_OK)
def analyze_repository(
    payload: RepositoryAnalyzeRequest,
    session: Session = Depends(get_session),
):
    """Analyze a registered repository workspace and return its structured ProjectSummary.

    Performs database look-up by repository_id to retrieve local workspace path.
    Results are persisted in the database. Calls return cached analysis unless
    force_refresh=True is set in the payload.
    """
    logger.info(f"Received repository analysis request for repository_id: '{payload.repository_id}'")

    repo = session.get(Repository, payload.repository_id)
    if not repo:
        logger.warning(f"Repository ID '{payload.repository_id}' not found in database.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository with ID '{payload.repository_id}' not found.",
        )

    if not repo.local_path or not os.path.exists(repo.local_path):
        logger.error(f"Local path for repository '{payload.repository_id}' does not exist: '{repo.local_path}'")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository workspace directory does not exist locally. Please clone the repository first.",
        )

    # Return cached summary if available and force_refresh not requested
    if repo.project_summary and not payload.force_refresh:
        logger.info(f"Returning cached ProjectSummary for repository '{payload.repository_id}'.")
        try:
            return ProjectSummary.model_validate(repo.project_summary)
        except Exception as ve:
            logger.warning(f"Failed to validate cached ProjectSummary JSON, re-analyzing: {ve}")

    try:
        summary = repository_analyzer.analyze_repository(repo.local_path)

        # Persist analysis results in DB
        repo.project_summary = summary.model_dump()
        session.add(repo)
        session.commit()
        session.refresh(repo)
        logger.info(f"Persisted ProjectSummary in DB for repository '{payload.repository_id}'.")

        return summary
    except WorkspaceNotFoundError as e:
        logger.warning(f"Workspace not found during analysis: {e}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ProjectDetectionError as e:
        logger.error(f"Project detection error during analysis: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RepositoryAnalysisError as e:
        logger.error(f"Repository analysis error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during repository analysis endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during repository analysis.",
        )
