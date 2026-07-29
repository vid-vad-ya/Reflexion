"""PlannerService – Reasoning and Strategy Agent for Reflexion.

Orchestrates the generation of structured ImplementationPlan objects for feature requests.
Consumes repository technical context (ProjectSummary) and invokes LLMService for structured reasoning.
"""

import logging
import uuid
from typing import Optional

from fastapi import HTTPException, status
from sqlmodel import Session

from app.models import Repository
from app.prompts.planner_prompt import build_planner_prompt
from app.schemas.planner import ImplementationPlan
from app.schemas.repository import ProjectSummary
from app.services.llm import llm_service, LLMError, LLMValidationError

logger = logging.getLogger("reflexion.services.planner")


class PlannerService:
    """Service responsible for generating architectural implementation plans.
    
    Orchestrates:
    1. Repository & ProjectSummary retrieval and validation from DB.
    2. Prompt construction via `build_planner_prompt`.
    3. Structured JSON generation via `llm_service.generate_json()`.
    """

    def plan_change(
        self,
        repository_id: uuid.UUID,
        user_request: str,
        session: Session,
    ) -> ImplementationPlan:
        """Generate a structured ImplementationPlan for a user request against a repository.

        Args:
            repository_id: Database UUID of the target repository.
            user_request: Natural language feature request or change instruction.
            session: Active SQLModel DB Session.

        Returns:
            ImplementationPlan: Validated structured plan object.

        Raises:
            HTTPException 404: If repository record is not found in database.
            HTTPException 400: If repository has not been analyzed yet (project_summary is missing).
            HTTPException 500: If LLM call or plan generation fails unexpectedly.
        """
        logger.info(f"Initiating implementation plan generation for repository_id='{repository_id}'")

        # 1. Load Repository from database
        repo = session.get(Repository, repository_id)

        # 2. Verify Repository exists
        if not repo:
            logger.warning(f"Repository with ID '{repository_id}' not found in database.")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Repository with ID '{repository_id}' not found.",
            )

        # 3. Verify Repository.project_summary exists
        if not repo.project_summary:
            logger.warning(
                f"Repository '{repository_id}' ({repo.full_name}) lacks project_summary. Analysis required first."
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Repository workspace has not been analyzed yet. Please run POST /api/v1/repositories/analyze first.",
            )

        # Parse project_summary JSON into Pydantic model
        try:
            project_summary = ProjectSummary.model_validate(repo.project_summary)
        except Exception as ve:
            logger.error(f"Failed to parse cached project_summary JSON for repository '{repository_id}': {ve}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Invalid project_summary structure stored in database: {str(ve)}",
            )

        # 4. Build prompt via dedicated prompt module
        logger.info(f"Building planner prompt for repo '{repo.full_name}' with request: '{user_request[:80]}...'")
        system_instruction, user_prompt = build_planner_prompt(
            user_request=user_request,
            project_summary=project_summary,
        )

        # 5. Call LLMService.generate_json()
        logger.info(f"Invoking LLMService.generate_json for repository '{repo.full_name}'")
        try:
            plan = llm_service.generate_json(
                prompt=user_prompt,
                response_schema=ImplementationPlan,
                system_instruction=system_instruction,
                temperature=0.2,
            )
            logger.info(
                f"Successfully generated ImplementationPlan for repository '{repository_id}' "
                f"[Goal: '{plan.goal}', Complexity: {plan.complexity}, Files changed: {plan.estimated_files_changed}]"
            )
            return plan

        except (LLMValidationError, LLMError) as le:
            logger.error(f"LLM service failure during plan generation for repository '{repository_id}': {le}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"LLM planner agent failed to generate structured plan: {str(le)}",
            )
        except Exception as e:
            logger.error(f"Unexpected error during plan generation for repository '{repository_id}': {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An unexpected error occurred while generating the implementation plan: {str(e)}",
            )


# Global singleton instance
planner_service = PlannerService()
