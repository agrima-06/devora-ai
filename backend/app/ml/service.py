"""Runtime prediction service for fast, reproducible bug classification."""
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import joblib
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.ml.preprocessor import BugCategory, TracebackPreprocessor

logger = get_logger("ml_prediction_service")

ARTIFACTS_DIR = Path(__file__).parent / "artifacts"


class ProbabilityItem(BaseModel):
    category: str
    probability: float


class PredictionResult(BaseModel):
    """Normalized output contract of the ML Bug Classifier."""
    predicted_category: str = Field(..., description="Canonical bug category (one of 8)")
    confidence: float = Field(..., description="Prediction confidence score between 0.0 and 1.0")
    top_probabilities: List[ProbabilityItem] = Field(default_factory=list, description="Ranked category probabilities")
    is_low_confidence: bool = Field(default=False, description="Flagged true if confidence is below threshold (< 0.60)")
    warning: Optional[str] = Field(default=None, description="Diagnostic warning for ambiguous or low-confidence inputs")
    model_version: str = Field(..., description="Version of the model artifact used for inference")
    input_hash: str = Field(..., description="SHA-256 hash of the cleaned input text")
    cleaned_input_preview: str = Field(default="", description="Sanitized input snippet")
    inference_time_ms: float = Field(default=0.0, description="Latency of feature extraction and inference in milliseconds")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class BugClassifierService:
    """Service providing sub-millisecond bug categorization and confidence scoring."""

    _instance: Optional["BugClassifierService"] = None

    def __init__(self, artifacts_dir: Optional[Path] = None):
        self.artifacts_dir = artifacts_dir or ARTIFACTS_DIR
        self.preprocessor = TracebackPreprocessor()
        self._model = None
        self._vectorizer = None
        self._metadata: Dict[str, Any] = {}
        self._active_version: str = "v1.0.0"
        self._load_active_model()

    @classmethod
    def get_instance(cls) -> "BugClassifierService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_active_model(self) -> bool:
        """Load and cache the active model artifact into memory."""
        active_pointer = self.artifacts_dir / "active_model.json"
        version = "v1.0.0"
        if active_pointer.exists():
            try:
                with open(active_pointer, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    version = data.get("active_version", "v1.0.0")
            except Exception as e:
                logger.warning("failed_to_read_active_pointer", error=str(e))

        version_dir = self.artifacts_dir / version
        model_file = version_dir / "model.joblib"
        vec_file = version_dir / "vectorizer.joblib"
        meta_file = version_dir / "metadata.json"

        if not (model_file.exists() and vec_file.exists()):
            logger.warning("model_artifacts_missing", version=version)
            self._model = None
            self._vectorizer = None
            return False

        try:
            self._model = joblib.load(model_file)
            self._vectorizer = joblib.load(vec_file)
            if meta_file.exists():
                with open(meta_file, "r", encoding="utf-8") as f:
                    self._metadata = json.load(f)
            self._active_version = version
            logger.info("ml_model_loaded_successfully", version=version)
            return True
        except Exception as e:
            logger.error("failed_to_load_ml_artifacts", error=str(e), version=version)
            self._model = None
            self._vectorizer = None
            return False

    def reload(self) -> bool:
        """Force reload the active model artifact from disk."""
        return self._load_active_model()

    def get_status(self) -> Dict[str, Any]:
        """Return the operational health and metadata of the active model."""
        is_ready = self._model is not None and self._vectorizer is not None
        return {
            "status": "ready" if is_ready else "degraded",
            "active_version": self._active_version,
            "algorithm": self._metadata.get("algorithm", "LogisticRegression"),
            "is_promoted": self._metadata.get("is_promoted", False),
            "sample_counts": self._metadata.get("sample_counts", {}),
            "created_at": self._metadata.get("created_at"),
            "model_sha256": self._metadata.get("model_sha256"),
        }

    def get_metrics(self) -> Dict[str, Any]:
        """Return evaluation metrics of the active model."""
        metrics_file = self.artifacts_dir / self._active_version / "metrics.json"
        if metrics_file.exists():
            try:
                with open(metrics_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning("failed_to_read_metrics", error=str(e))
        return {
            "accuracy": 0.0,
            "macro_f1": 0.0,
            "weighted_f1": 0.0,
            "per_class": {},
            "confusion_matrix": [],
        }

    def list_versions(self) -> List[Dict[str, Any]]:
        """List all available model artifact versions."""
        versions = []
        if not self.artifacts_dir.exists():
            return versions

        for p in self.artifacts_dir.iterdir():
            if p.is_dir() and (p / "metadata.json").exists():
                try:
                    with open(p / "metadata.json", "r", encoding="utf-8") as f:
                        meta = json.load(f)
                        meta["is_active"] = (p.name == self._active_version)
                        versions.append(meta)
                except Exception:
                    pass
        return sorted(versions, key=lambda x: x.get("created_at", ""), reverse=True)

    def _fallback_rule_based_classify(self, cleaned_text: str) -> Tuple[str, float]:
        """Deterministic heuristic fallback if ML model is unavailable."""
        normalized = self.preprocessor.normalize_category(cleaned_text)
        return normalized, 0.50

    def predict(
        self,
        error_message: str,
        traceback: Optional[str] = None,
        task_description: Optional[str] = None,
    ) -> PredictionResult:
        """Classify an error message and traceback into one of the 8 canonical categories."""
        start_time = time.perf_counter()

        # Combine text inputs
        combined_raw = f"{task_description or ''}\n{error_message or ''}\n{traceback or ''}".strip()
        cleaned_text = self.preprocessor.preprocess(
            error_message=f"{task_description or ''} {error_message or ''}",
            traceback=traceback,
        )

        input_hash = hashlib.sha256(cleaned_text.encode("utf-8")).hexdigest()
        preview = cleaned_text[:120] + ("..." if len(cleaned_text) > 120 else "")

        # Fallback if model not loaded or empty text
        if self._model is None or self._vectorizer is None or not cleaned_text:
            cat, conf = self._fallback_rule_based_classify(cleaned_text or combined_raw)
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return PredictionResult(
                predicted_category=cat,
                confidence=conf,
                top_probabilities=[ProbabilityItem(category=cat, probability=conf)],
                is_low_confidence=True,
                warning="Fallback heuristic classifier applied: ML model unavailable or input empty.",
                model_version=f"{self._active_version}-fallback",
                input_hash=input_hash,
                cleaned_input_preview=preview,
                inference_time_ms=round(duration_ms, 2),
            )

        # ML Feature extraction and probability inference
        vec = self._vectorizer.transform([cleaned_text])
        probabilities = self._model.predict_proba(vec)[0]
        classes = self._model.classes_

        # Pair class with probability and sort descending
        paired = sorted(
            [ProbabilityItem(category=str(c), probability=round(float(p), 4)) for c, p in zip(classes, probabilities)],
            key=lambda x: x.probability,
            reverse=True,
        )

        top_item = paired[0]
        predicted_category = top_item.category
        confidence = top_item.probability
        second_item = paired[1] if len(paired) > 1 else None
        margin = (confidence - second_item.probability) if second_item else confidence

        # In an 8-class distribution (uniform prior = 0.125), confidence < 0.30 or small margin (< 0.10) indicates ambiguity
        is_low_confidence = confidence < 0.30 or margin < 0.10

        warning = None
        if is_low_confidence:
            warning = (
                f"Moderate confidence ({confidence * 100:.1f}%). Possible ambiguity with "
                f"{second_item.category} ({second_item.probability * 100:.1f}%)."
                if second_item else "Low confidence prediction."
            )

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        return PredictionResult(
            predicted_category=predicted_category,
            confidence=confidence,
            top_probabilities=paired[:4],
            is_low_confidence=is_low_confidence,
            warning=warning,
            model_version=self._active_version,
            input_hash=input_hash,
            cleaned_input_preview=preview,
            inference_time_ms=round(duration_ms, 2),
        )
