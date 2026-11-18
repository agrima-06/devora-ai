"""Report schemas."""
import uuid
from datetime import datetime
from typing import Any, Dict
from pydantic import BaseModel, ConfigDict, Field


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    title: str
    summary: str
    root_cause_analysis: str
    test_summary: Dict[str, Any] = Field(default_factory=dict)
    markdown_content: str
    created_at: datetime
