"""API endpoints for the Planner Agent.

Exposes POST /api/v1/repositories/{repository_id}/plan endpoint to generate
structured architectural implementation plans for registered repositories.
"""

import logging
import uuid
from fastapi import APIRouter, Depends, status
from sqlmodel import Session

from app.database import get_session
from app.schemas.planner import ImplementationPlan, PlannerRequest
from app.services.planner_service import planner_service

logger = logging.getLogger("reflexion.api.planner")

router = APIRouter()


@router.post(
    "/{repository_id}/plan",
    response_model=ImplementationPlan,
    status_code=status.HTTP_200_OK,
    summary="Generate architectural implementation plan",
    description=(
        "Consumes a natural language feature request and the repository's cached ProjectSummary "
        "to generate a structured, non-code ImplementationPlan."
    ),
)
def plan_repository_change(
    repository_id: uuid.UUID,
    payload: PlannerRequest,
    session: Session = Depends(get_session),
) -> ImplementationPlan:
    """Generate a structured implementation plan for a requested feature.

    Args:
        repository_id: Database UUID of the repository.
        payload: PlannerRequest containing natural language feature request string.
        session: Active database session dependency.

    Returns:
        ImplementationPlan: Structured architectural plan.
    """
    logger.info(f"Received planning request for repository_id: '{repository_id}'")
    return planner_service.plan_change(
        repository_id=repository_id,
        user_request=payload.request,
        session=session,
    )
