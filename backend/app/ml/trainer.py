"""Model training, hyperparameter evaluation, and serialization pipeline for Bug Classification."""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, f1_score, precision_score, recall_score, accuracy_score
from sklearn.model_selection import train_test_split

from app.core.logging import get_logger
from app.ml.data.dataset import DatasetManager
from app.ml.preprocessor import BugCategory, TracebackPreprocessor

logger = get_logger("ml_trainer")

ARTIFACTS_DIR = Path(__file__).parent / "artifacts"


class ModelTrainingResult:
    """Encapsulates the complete metrics, artifacts, and gate outcome of a training run."""

    def __init__(
        self,
        version: str,
        is_promoted: bool,
        promotion_reason: str,
        accuracy: float,
        macro_f1: float,
        weighted_f1: float,
        per_class_metrics: Dict[str, Dict[str, float]],
        confusion_matrix: List[List[int]],
        classes: List[str],
        train_samples: int,
        val_samples: int,
        test_samples: int,
        model_sha256: str,
        vectorizer_sha256: str,
        artifact_path: str,
    ):
        self.version = version
        self.is_promoted = is_promoted
        self.promotion_reason = promotion_reason
        self.accuracy = accuracy
        self.macro_f1 = macro_f1
        self.weighted_f1 = weighted_f1
        self.per_class_metrics = per_class_metrics
        self.confusion_matrix = confusion_matrix
        self.classes = classes
        self.train_samples = train_samples
        self.val_samples = val_samples
        self.test_samples = test_samples
        self.model_sha256 = model_sha256
        self.vectorizer_sha256 = vectorizer_sha256
        self.artifact_path = artifact_path

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "is_promoted": self.is_promoted,
            "promotion_reason": self.promotion_reason,
            "accuracy": round(self.accuracy, 4),
            "macro_f1": round(self.macro_f1, 4),
            "weighted_f1": round(self.weighted_f1, 4),
            "per_class_metrics": self.per_class_metrics,
            "confusion_matrix": self.confusion_matrix,
            "classes": self.classes,
            "sample_counts": {
                "train": self.train_samples,
                "val": self.val_samples,
                "test": self.test_samples,
                "total": self.train_samples + self.val_samples + self.test_samples,
            },
            "model_sha256": self.model_sha256,
            "vectorizer_sha256": self.vectorizer_sha256,
            "artifact_path": self.artifact_path,
        }


class BugClassifierTrainer:
    """Trains, evaluates, and packages versioned ML classification models."""

    def __init__(
        self,
        dataset_manager: Optional[DatasetManager] = None,
        preprocessor: Optional[TracebackPreprocessor] = None,
        artifacts_dir: Optional[Path] = None,
    ):
        self.dataset_manager = dataset_manager or DatasetManager()
        self.preprocessor = preprocessor or TracebackPreprocessor()
        self.artifacts_dir = artifacts_dir or ARTIFACTS_DIR
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def _compute_sha256(self, file_path: Path) -> str:
        """Calculate SHA-256 checksum of an artifact file."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    def train_and_evaluate(
        self,
        version: str = "v1.0.0",
        random_state: int = 42,
        min_weighted_f1: float = 0.85,
        min_class_precision: float = 0.70,
        c_param: float = 1.0,
        max_iter: int = 1000,
    ) -> ModelTrainingResult:
        """Execute full training, evaluation against test split, and promotion gating."""
        # 1. Load dataset
        raw_items = self.dataset_manager.load_dataset()
        if len(raw_items) < 16:
            raise ValueError(f"Insufficient training data: {len(raw_items)} samples found")

        # 2. Preprocess features and labels
        texts: List[str] = []
        labels: List[str] = []
        for item in raw_items:
            cleaned = self.preprocessor.preprocess(
                error_message=item.get("error_message", ""),
                traceback=item.get("traceback", ""),
            )
            texts.append(cleaned)
            labels.append(item["category"])

        # 3. Stratified split: 70% Train, 15% Val, 15% Test
        X_train_val, X_test, y_train_val, y_test = train_test_split(
            texts, labels, test_size=0.15, random_state=random_state, stratify=labels
        )
        # 0.1765 of 85% is ~15% overall
        X_train, X_val, y_train, y_val = train_test_split(
            X_train_val, y_train_val, test_size=0.1765, random_state=random_state, stratify=y_train_val
        )

        logger.info(
            "dataset_split_completed",
            train=len(X_train),
            val=len(X_val),
            test=len(X_test),
        )

        # 4. Fit TF-IDF Vectorizer
        vectorizer = TfidfVectorizer(
            ngram_range=(1, 3),
            max_features=5000,
            sublinear_tf=True,
            token_pattern=r"(?u)\b\w+\b|<[A-Z_]+>",
        )
        X_train_vec = vectorizer.fit_transform(X_train)
        X_test_vec = vectorizer.transform(X_test)

        # 5. Fit Logistic Regression classifier
        canonical_classes = BugCategory.list_all()
        model = LogisticRegression(
            C=c_param,
            max_iter=max_iter,
            solver="lbfgs",
            random_state=random_state,
        )
        model.fit(X_train_vec, y_train)

        # 6. Evaluate on holdout test partition
        y_pred = model.predict(X_test_vec)

        # Metrics
        accuracy = float(accuracy_score(y_test, y_pred))
        macro_f1 = float(f1_score(y_test, y_pred, average="macro", zero_division=0))
        weighted_f1 = float(f1_score(y_test, y_pred, average="weighted", zero_division=0))

        report_dict = classification_report(
            y_test, y_pred, labels=canonical_classes, output_dict=True, zero_division=0
        )

        per_class_metrics: Dict[str, Dict[str, float]] = {}
        min_precision_found = 1.0
        for cls_name in canonical_classes:
            cls_stat = report_dict.get(cls_name, {})
            p = float(cls_stat.get("precision", 0.0))
            r = float(cls_stat.get("recall", 0.0))
            f1 = float(cls_stat.get("f1-score", 0.0))
            supp = int(cls_stat.get("support", 0))
            per_class_metrics[cls_name] = {
                "precision": round(p, 4),
                "recall": round(r, 4),
                "f1": round(f1, 4),
                "support": supp,
            }
            if supp > 0 and p < min_precision_found:
                min_precision_found = p

        cm = confusion_matrix(y_test, y_pred, labels=canonical_classes).tolist()

        # 7. Promotion Gate Validation
        gate_passed = True
        gate_reasons = []

        if weighted_f1 < min_weighted_f1:
            gate_passed = False
            gate_reasons.append(
                f"Weighted F1 {weighted_f1:.4f} below threshold {min_weighted_f1}"
            )

        if min_precision_found < min_class_precision:
            gate_passed = False
            gate_reasons.append(
                f"Minimum category precision {min_precision_found:.4f} below threshold {min_class_precision}"
            )

        if gate_passed:
            promotion_reason = (
                f"Passed all promotion gates: Weighted F1={weighted_f1:.4f} >= {min_weighted_f1}, "
                f"Min Precision={min_precision_found:.4f} >= {min_class_precision}"
            )
        else:
            promotion_reason = f"Rejected: {'; '.join(gate_reasons)}"

        # 8. Save versioned artifacts
        version_dir = self.artifacts_dir / version
        version_dir.mkdir(parents=True, exist_ok=True)

        model_path = version_dir / "model.joblib"
        vec_path = version_dir / "vectorizer.joblib"
        metadata_path = version_dir / "metadata.json"
        metrics_path = version_dir / "metrics.json"

        joblib.dump(model, model_path)
        joblib.dump(vectorizer, vec_path)

        model_sha256 = self._compute_sha256(model_path)
        vec_sha256 = self._compute_sha256(vec_path)

        metadata = {
            "version": version,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "algorithm": "LogisticRegression",
            "hyperparameters": {
                "C": c_param,
                "max_iter": max_iter,
                "solver": "lbfgs",
                "ngram_range": [1, 3],
                "max_features": 5000,
            },
            "is_promoted": gate_passed,
            "promotion_reason": promotion_reason,
            "model_sha256": model_sha256,
            "vectorizer_sha256": vec_sha256,
            "sample_counts": {
                "train": len(X_train),
                "val": len(X_val),
                "test": len(X_test),
                "total": len(raw_items),
            },
            "classes": canonical_classes,
        }

        metrics_data = {
            "accuracy": round(accuracy, 4),
            "macro_f1": round(macro_f1, 4),
            "weighted_f1": round(weighted_f1, 4),
            "per_class": per_class_metrics,
            "confusion_matrix": cm,
            "classes": canonical_classes,
        }

        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        with open(metrics_path, "w", encoding="utf-8") as f:
            json.dump(metrics_data, f, indent=2)

        # Write pointer to active model if promoted
        if gate_passed:
            active_pointer = self.artifacts_dir / "active_model.json"
            with open(active_pointer, "w", encoding="utf-8") as f:
                json.dump({"active_version": version, "promoted_at": metadata["created_at"]}, f, indent=2)

        logger.info(
            "model_training_completed",
            version=version,
            promoted=gate_passed,
            accuracy=accuracy,
            weighted_f1=weighted_f1,
        )

        return ModelTrainingResult(
            version=version,
            is_promoted=gate_passed,
            promotion_reason=promotion_reason,
            accuracy=accuracy,
            macro_f1=macro_f1,
            weighted_f1=weighted_f1,
            per_class_metrics=per_class_metrics,
            confusion_matrix=cm,
            classes=canonical_classes,
            train_samples=len(X_train),
            val_samples=len(X_val),
            test_samples=len(X_test),
            model_sha256=model_sha256,
            vectorizer_sha256=vec_sha256,
            artifact_path=str(version_dir),
        )
