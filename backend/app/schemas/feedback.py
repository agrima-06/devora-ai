"""Feedback schemas."""
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class FeedbackCreate(BaseModel):
    rating: str = Field(..., pattern=r"^(ACCEPTED|REJECTED|NEEDS_CHANGES|INCORRECT_SOLUTION|INCOMPLETE_SOLUTION)$")
    comments: Optional[str] = None
    solution_accepted: bool = False


class FeedbackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    user_id: uuid.UUID
    rating: str
    comments: Optional[str] = None
    solution_accepted: bool
    created_at: datetime
