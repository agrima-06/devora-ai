"""Unit tests for ML DatasetManager and corpus partitioning."""
import tempfile
from pathlib import Path
import pytest
from app.ml.data.dataset import DatasetManager, SEED_DATA
from app.ml.preprocessor import BugCategory


def test_dataset_manager_initializes_seed():
    with tempfile.TemporaryDirectory() as tmp_dir:
        manager = DatasetManager(data_path=Path(tmp_dir))
        items = manager.load_dataset()
        assert len(items) == len(SEED_DATA)
        assert len(items) >= 160


def test_dataset_manager_balanced_distribution():
    with tempfile.TemporaryDirectory() as tmp_dir:
        manager = DatasetManager(data_path=Path(tmp_dir))
        dist = manager.get_class_distribution()
        assert len(dist) == 8
        for cat, count in dist.items():
            assert count >= 20, f"Category {cat} has only {count} samples"


def test_dataset_manager_duplicate_rejection():
    with tempfile.TemporaryDirectory() as tmp_dir:
        manager = DatasetManager(data_path=Path(tmp_dir))
        # Adding existing seed sample must return False
        first = SEED_DATA[0]
        added = manager.add_sample(
            category=first["category"],
            error_message=first["error_message"],
            traceback=first["traceback"],
        )
        assert added is False


def test_dataset_manager_add_valid_sample():
    with tempfile.TemporaryDirectory() as tmp_dir:
        manager = DatasetManager(data_path=Path(tmp_dir))
        initial_count = len(manager.load_dataset())
        added = manager.add_sample(
            category=BugCategory.SYNTAX_ERROR.value,
            error_message="SyntaxError: test unique syntax sample 999",
            traceback='File "/workspace/app/unique_test.py", line 1\n def test(:',
            context="test sample context",
        )
        assert added is True
        assert len(manager.load_dataset()) == initial_count + 1
