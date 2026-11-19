"""Unit tests for BugClassifierTrainer model training, evaluation, and serialization."""
import tempfile
from pathlib import Path
import pytest
from app.ml.data.dataset import DatasetManager
from app.ml.trainer import BugClassifierTrainer


def test_trainer_train_evaluate_and_promote():
    with tempfile.TemporaryDirectory() as tmp_artifacts:
        with tempfile.TemporaryDirectory() as tmp_data:
            dataset_mgr = DatasetManager(data_path=Path(tmp_data))
            trainer = BugClassifierTrainer(
                dataset_manager=dataset_mgr,
                artifacts_dir=Path(tmp_artifacts),
            )

            result = trainer.train_and_evaluate(
                version="v1.0.0-test",
                min_weighted_f1=0.80,
                min_class_precision=0.70,
                c_param=5.0,
            )

            assert result.version == "v1.0.0-test"
            assert result.is_promoted is True
            assert result.weighted_f1 >= 0.80
            assert result.accuracy >= 0.80
            assert len(result.classes) == 8
            assert len(result.confusion_matrix) == 8
            assert len(result.confusion_matrix[0]) == 8

            # Verify saved files
            version_dir = Path(tmp_artifacts) / "v1.0.0-test"
            assert (version_dir / "model.joblib").exists()
            assert (version_dir / "vectorizer.joblib").exists()
            assert (version_dir / "metadata.json").exists()
            assert (version_dir / "metrics.json").exists()
            assert len(result.model_sha256) == 64
            assert len(result.vectorizer_sha256) == 64


def test_trainer_promotion_gate_rejection():
    with tempfile.TemporaryDirectory() as tmp_artifacts:
        with tempfile.TemporaryDirectory() as tmp_data:
            dataset_mgr = DatasetManager(data_path=Path(tmp_data))
            trainer = BugClassifierTrainer(
                dataset_manager=dataset_mgr,
                artifacts_dir=Path(tmp_artifacts),
            )

            # Require unrealistic 100% precision with min threshold 1.01 to force gate rejection
            result = trainer.train_and_evaluate(
                version="v1.0.0-fail",
                min_weighted_f1=1.01,
                min_class_precision=1.01,
            )

            assert result.is_promoted is False
            assert "below threshold" in result.promotion_reason
