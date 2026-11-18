"""Approval schemas."""
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class ApprovalActionRequest(BaseModel):
    action: str = Field(..., pattern=r"^(APPROVE|REJECT|REQUEST_CHANGES)$")
    notes: Optional[str] = None
    publish_pr: bool = False


class ApprovalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    requested_by: uuid.UUID
    reviewed_by: Optional[uuid.UUID] = None
    status: str
    notes: Optional[str] = None
    responded_at: Optional[datetime] = None
    created_at: datetime
