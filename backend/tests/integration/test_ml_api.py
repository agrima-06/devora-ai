"""Integration tests for Machine Learning Bug Classification REST APIs."""
import pytest
from httpx import AsyncClient
from app.models.user import User


@pytest.mark.asyncio
async def test_ml_api_classify_and_status(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
):
    """Test classifying a traceback and querying model status and metrics."""
    # 1. Classify an error
    classify_payload = {
        "error_message": "ZeroDivisionError: division by zero",
        "traceback": 'Traceback (most recent call last):\n  File "app/metrics.py", line 40\n    return val / count\nZeroDivisionError: division by zero',
        "task_description": "Fix zero division bug in analytics",
    }

    res = await client.post(
        "/api/v1/ml/classify",
        json=classify_payload,
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["predicted_category"] == "runtime_logic_error"
    assert data["confidence"] > 0.0
    assert "top_probabilities" in data
    assert len(data["top_probabilities"]) > 0
    assert data["inference_time_ms"] >= 0.0
    assert "input_hash" in data

    # 2. Query model status
    status_res = await client.get("/api/v1/ml/model/status", headers=auth_headers)
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["status"] == "ready"
    assert "active_version" in status_data
    assert status_data["algorithm"] == "LogisticRegression"

    # 3. Query model evaluation metrics
    metrics_res = await client.get("/api/v1/ml/model/metrics", headers=auth_headers)
    assert metrics_res.status_code == 200
    metrics_data = metrics_res.json()
    assert "accuracy" in metrics_data
    assert "weighted_f1" in metrics_data
    assert "confusion_matrix" in metrics_data
    assert len(metrics_data["classes"]) == 8

    # 4. List model versions
    versions_res = await client.get("/api/v1/ml/model/versions", headers=auth_headers)
    assert versions_res.status_code == 200
    versions_data = versions_res.json()
    assert len(versions_data) >= 1
    assert any(v["is_active"] for v in versions_data)

    # 5. Fetch recent predictions history
    preds_res = await client.get("/api/v1/ml/predictions", headers=auth_headers)
    assert preds_res.status_code == 200
    preds_data = preds_res.json()
    assert preds_data["total"] >= 1
    assert len(preds_data["items"]) >= 1
    assert preds_data["items"][0]["predicted_category"] == "runtime_logic_error"


@pytest.mark.asyncio
async def test_ml_api_train_and_promotion(
    client: AsyncClient,
    test_user: User,
    auth_headers: dict,
):
    """Test triggering controlled model retraining and promotion via API."""
    train_payload = {
        "version": "v1.2.0-test",
        "min_weighted_f1": 0.80,
        "min_class_precision": 0.70,
        "c_param": 5.0,
        "max_iter": 500,
    }

    train_res = await client.post(
        "/api/v1/ml/model/train",
        json=train_payload,
        headers=auth_headers,
    )
    assert train_res.status_code == 200
    train_data = train_res.json()
    assert train_data["version"] == "v1.2.0-test"
    assert train_data["is_promoted"] is True
    assert train_data["weighted_f1"] >= 0.80
    assert "confusion_matrix" in train_data
