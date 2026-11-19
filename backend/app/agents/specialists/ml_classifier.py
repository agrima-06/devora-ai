"""Specialist Node: ML Bug Classification Node.
Performs deterministic, fast ML-based traceback diagnosis prior to LLM bug investigation.
"""
import time
from typing import Any, Dict
from app.agents.state import DevoraWorkflowState
from app.core.logging import get_logger
from app.ml.service import BugClassifierService

logger = get_logger("ml_classifier_node")


async def ml_classifier_node(state: DevoraWorkflowState) -> Dict[str, Any]:
    """LangGraph node function executing classical ML bug classification."""
    start_time = time.time()
    service = BugClassifierService.get_instance()

    task_desc = state.get("task_description", "")
    traceback = state.get("error_traceback") or ""

    # Predict canonical bug category and confidence probabilities
    prediction = service.predict(
        error_message="",
        traceback=traceback,
        task_description=task_desc,
    )

    duration_ms = int((time.time() - start_time) * 1000)

    log_entry = {
        "agent": "ml_classifier",
        "action": "classified_error_fingerprint",
        "predicted_category": prediction.predicted_category,
        "confidence": prediction.confidence,
        "is_low_confidence": prediction.is_low_confidence,
        "model_version": prediction.model_version,
        "duration_ms": duration_ms,
    }

    history = list(state.get("agent_execution_history", []))
    history.append(log_entry)

    logger.info(
        "ml_classification_completed",
        category=prediction.predicted_category,
        confidence=prediction.confidence,
        is_low_confidence=prediction.is_low_confidence,
        version=prediction.model_version,
    )

    return {
        "current_agent": "ml_classifier",
        "ml_bug_prediction": prediction.model_dump(),
        "agent_execution_history": history,
    }
