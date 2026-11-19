"""API routes for ML Bug Classification Engine, model telemetry, and controlled training."""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.ml.preprocessor import BugCategory
from app.ml.service import BugClassifierService, PredictionResult
from app.ml.trainer import BugClassifierTrainer
from app.models.ml_model_metadata import MLModelMetadata
from app.models.ml_prediction import MLPrediction
from app.models.user import User

router = APIRouter(prefix="/ml", tags=["Machine Learning"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ClassifyRequest(BaseModel):
    error_message: str = Field(default="", description="Error message or exception string")
    traceback: Optional[str] = Field(default="", description="Raw error stack trace")
    task_description: Optional[str] = Field(default="", description="Optional context or task title")
    task_id: Optional[uuid.UUID] = Field(default=None, description="Optional associated task ID")


class TrainModelRequest(BaseModel):
    version: Optional[str] = Field(default=None, description="Artifact version tag (e.g. v1.1.0)")
    min_weighted_f1: float = Field(default=0.85, ge=0.5, le=1.0)
    min_class_precision: float = Field(default=0.70, ge=0.4, le=1.0)
    c_param: float = Field(default=5.0, gt=0.0)
    max_iter: int = Field(default=1000, ge=100)


class PredictionHistoryItem(BaseModel):
    id: uuid.UUID
    task_id: Optional[uuid.UUID]
    predicted_category: str
    confidence: float
    is_low_confidence: bool
    model_version: str
    inference_time_ms: float
    verified_category: Optional[str]
    is_correct: Optional[bool]
    created_at: datetime


class PredictionHistoryResponse(BaseModel):
    items: List[PredictionHistoryItem]
    total: int
    page: int
    page_size: int
    correct_count: int
    incorrect_count: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/classify",
    response_model=PredictionResult,
    summary="Classify error traceback into canonical bug category",
)
async def classify_error(
    request: ClassifyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Classify an error message and traceback using the active Scikit-learn model."""
    service = BugClassifierService.get_instance()
    result = service.predict(
        error_message=request.error_message,
        traceback=request.traceback,
        task_description=request.task_description,
    )

    # Persist prediction record in PostgreSQL
    prediction_record = MLPrediction(
        task_id=request.task_id,
        input_hash=result.input_hash,
        error_sample_preview=result.cleaned_input_preview,
        predicted_category=result.predicted_category,
        confidence=result.confidence,
        top_probabilities=[p.model_dump() for p in result.top_probabilities],
        is_low_confidence=result.is_low_confidence,
        model_version=result.model_version,
        inference_time_ms=result.inference_time_ms,
    )
    db.add(prediction_record)
    await db.commit()

    return result


@router.get(
    "/model/status",
    summary="Get active model status and health",
)
async def get_model_status(
    current_user: User = Depends(get_current_user),
):
    """Retrieve runtime status, version, and architecture of the active ML model."""
    service = BugClassifierService.get_instance()
    return service.get_status()


@router.get(
    "/model/metrics",
    summary="Get active model evaluation metrics & confusion matrix",
)
async def get_model_metrics(
    current_user: User = Depends(get_current_user),
):
    """Retrieve full evaluation metrics (accuracy, F1, confusion matrix) of the active model."""
    service = BugClassifierService.get_instance()
    return service.get_metrics()


@router.get(
    "/model/versions",
    summary="List available model artifact versions",
)
async def list_model_versions(
    current_user: User = Depends(get_current_user),
):
    """List all trained model versions and their promotion states."""
    service = BugClassifierService.get_instance()
    return service.list_versions()


@router.post(
    "/model/train",
    summary="Trigger controlled model training and promotion gate",
)
async def train_model(
    request: TrainModelRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Execute training pipeline on curated dataset and evaluate promotion gates."""
    trainer = BugClassifierTrainer()

    # Determine version tag
    version = request.version
    if not version:
        existing_versions = BugClassifierService.get_instance().list_versions()
        version = f"v1.{len(existing_versions)}.0"

    result = trainer.train_and_evaluate(
        version=version,
        min_weighted_f1=request.min_weighted_f1,
        min_class_precision=request.min_class_precision,
        c_param=request.c_param,
        max_iter=request.max_iter,
    )

    # Persist model run in ml_models table
    db_model = MLModelMetadata(
        version=result.version,
        algorithm="LogisticRegression",
        is_active=result.is_promoted,
        accuracy=result.accuracy,
        macro_f1=result.macro_f1,
        weighted_f1=result.weighted_f1,
        metrics={
            "per_class": result.per_class_metrics,
            "confusion_matrix": result.confusion_matrix,
            "classes": result.classes,
        },
        training_sample_count=result.train_samples + result.val_samples + result.test_samples,
        model_sha256=result.model_sha256,
        vectorizer_sha256=result.vectorizer_sha256,
        promotion_reason=result.promotion_reason,
    )

    # If promoted, deactivate previous active models
    if result.is_promoted:
        deact_stmt = select(MLModelMetadata).where(MLModelMetadata.is_active == True)
        res = await db.execute(deact_stmt)
        for prev in res.scalars():
            prev.is_active = False

    db.add(db_model)
    await db.commit()

    # Reload in-memory service if promoted
    if result.is_promoted:
        BugClassifierService.get_instance().reload()

    return result.to_dict()


@router.get(
    "/predictions",
    response_model=PredictionHistoryResponse,
    summary="Get recent ML prediction history and verification telemetry",
)
async def get_predictions(
    task_id: Optional[uuid.UUID] = Query(None, description="Filter by task ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve historical predictions with telemetry on prediction accuracy."""
    stmt = select(MLPrediction)
    if task_id:
        stmt = stmt.where(MLPrediction.task_id == task_id)

    # Count totals
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    # Paginate
    stmt = stmt.order_by(MLPrediction.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    res = await db.execute(stmt)
    records = res.scalars().all()

    # Stats
    correct_stmt = select(func.count()).where(MLPrediction.is_correct == True)
    incorrect_stmt = select(func.count()).where(MLPrediction.is_correct == False)
    correct_count = (await db.execute(correct_stmt)).scalar() or 0
    incorrect_count = (await db.execute(incorrect_stmt)).scalar() or 0

    items = [
        PredictionHistoryItem(
            id=r.id,
            task_id=r.task_id,
            predicted_category=r.predicted_category,
            confidence=r.confidence,
            is_low_confidence=r.is_low_confidence,
            model_version=r.model_version,
            inference_time_ms=r.inference_time_ms,
            verified_category=r.verified_category,
            is_correct=r.is_correct,
            created_at=r.created_at,
        )
        for r in records
    ]

    return PredictionHistoryResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        correct_count=correct_count,
        incorrect_count=incorrect_count,
    )
