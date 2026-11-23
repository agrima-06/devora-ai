"""API Router for Phase 10 Stage 10.2: Blast Radius and Change Impact Analysis Engine."""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.impact import ImpactAnalysisRequest, ImpactAnalysisResponse
from app.services.impact_analysis_service import ImpactAnalysisService

router = APIRouter(prefix="/repositories/{repository_id}/impact-analysis", tags=["Blast Radius & Impact Analysis"])


@router.post(
    "",
    response_model=ImpactAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Compute blast radius and change impact for files and symbols",
)
async def analyze_change_impact(
    repository_id: uuid.UUID,
    payload: ImpactAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ImpactAnalysisResponse:
    """Perform reverse dependency graph traversal from target files or symbols,

    computing deterministic impact severity, explainable dependency paths,
    confidence ratings, and recommended test suites.
    """
    service = ImpactAnalysisService()
    return await service.analyze_impact(
        repository_id=repository_id,
        request=payload,
        user_id=current_user.id,
        db=db,
    )
