"""API endpoints for repository workspace management."""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.services.git_service import (
    git_service,
    GitServiceError,
    InvalidRepositoryURLError,
    RepositoryNotFoundError,
    GitAuthenticationError,
    CloneFailureError,
    WorkspaceCreationError,
)

logger = logging.getLogger("reflexion.api.repositories")

router = APIRouter()


class RepositoryCloneRequest(BaseModel):
    repository_url: str = Field(..., description="Git clone URL (HTTPS or SSH)")
    repository_name: str = Field(..., description="Name of the repository")
    owner: Optional[str] = Field(None, description="Repository owner or organization name")
    access_token: Optional[str] = Field(None, description="Optional GitHub access token for private repositories")


class RepositoryCloneResponse(BaseModel):
    status: str = Field("success", description="Status of the operation")
    workspace: str = Field(..., description="Local workspace filesystem path")
    default_branch: str = Field(..., description="Active default branch name")
    already_exists: bool = Field(..., description="True if workspace existed prior to clone request")


@router.post("/clone", response_model=RepositoryCloneResponse, status_code=status.HTTP_200_OK)
def clone_repository(payload: RepositoryCloneRequest):
    """Clone a Git repository into the local workspace directory.
    
    If the repository already exists locally, returns existing workspace path
    without recloning.
    """
    try:
        result = git_service.clone_repository(
            repository_url=payload.repository_url,
            repository_name=payload.repository_name,
            owner=payload.owner,
            access_token=payload.access_token,
        )
        return RepositoryCloneResponse(**result)
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
        logger.error(f"Unexpected error during repository clone endpoint: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred during repository clone.")
