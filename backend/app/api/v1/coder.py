"""API endpoints for the Coder Agent.

Exposes POST /api/v1/repositories/{repository_id}/code endpoint to generate
implementation code and unified diffs based on an ImplementationPlan.
"""

import logging
import uuid
from fastapi import APIRouter, Depends, status
from sqlmodel import Session

from app.database import get_session
from app.schemas.coder import CoderRequest, CodingResult
from app.services.coder_service import coder_service

logger = logging.getLogger("reflexion.api.coder")

router = APIRouter()


@router.post(
    "/{repository_id}/code",
    response_model=CodingResult,
    status_code=status.HTTP_200_OK,
    summary="Generate implementation code changes and unified diffs",
    description=(
        "Consumes an ImplementationPlan and targeted workspace files to generate "
        "production-ready code changes and standard unified diffs without modifying local files."
    ),
)
def generate_repository_code(
    repository_id: uuid.UUID,
    payload: CoderRequest,
    session: Session = Depends(get_session),
) -> CodingResult:
    """Generate implementation code changes and unified diffs for a repository.

    Args:
        repository_id: Database UUID of the repository.
        payload: CoderRequest containing optional ImplementationPlan and user prompt override.
        session: Active database session dependency.

    Returns:
        CodingResult: Structured response with generated files, explanations, reasoning, and diffs.
    """
    logger.info(f"Received code generation request for repository_id: '{repository_id}'")
    return coder_service.generate_code(
        repository_id=repository_id,
        session=session,
        implementation_plan=payload.implementation_plan,
        user_prompt_override=payload.user_prompt_override,
    )
