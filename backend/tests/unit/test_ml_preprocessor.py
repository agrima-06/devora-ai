"""Unit tests for ML Traceback Preprocessor and category normalizer."""
import pytest
from app.ml.preprocessor import BugCategory, TracebackPreprocessor, LEGACY_CATEGORY_MAPPINGS


def test_preprocessor_masks_hex_addresses():
    preprocessor = TracebackPreprocessor()
    raw = "Object at 0x7ffee1234abcd was deallocated unexpectedly."
    cleaned = preprocessor.clean_text(raw)
    assert "<HEX_ADDR>" in cleaned
    assert "0x7ffee1234abcd" not in cleaned


def test_preprocessor_masks_file_paths_and_lines():
    preprocessor = TracebackPreprocessor()
    raw = 'File "/var/deploy/app/services/calculator.py", line 42, in compute'
    cleaned = preprocessor.clean_text(raw)
    assert "<FILE_PATH>/calculator.py" in cleaned
    assert "line <LINE_NUM>" in cleaned


def test_preprocessor_preserves_exception_names():
    preprocessor = TracebackPreprocessor()
    raw = "Traceback: ZeroDivisionError: division by zero"
    cleaned = preprocessor.clean_text(raw)
    assert "ZeroDivisionError" in cleaned
    assert "division by zero" in cleaned

    extracted = preprocessor.extract_exception_names(raw)
    assert "ZeroDivisionError" in extracted


def test_category_normalization():
    # Canonical passthrough
    for cat in BugCategory:
        assert TracebackPreprocessor.normalize_category(cat.value) == cat.value

    # Aliases
    assert TracebackPreprocessor.normalize_category("syntax") == BugCategory.SYNTAX_ERROR.value
    assert TracebackPreprocessor.normalize_category("SyntaxError") == BugCategory.SYNTAX_ERROR.value
    assert TracebackPreprocessor.normalize_category("ModuleNotFoundError") == BugCategory.IMPORT_DEPENDENCY_ERROR.value
    assert TracebackPreprocessor.normalize_category("nonetype") == BugCategory.ATTRIBUTE_NULL_REFERENCE_ERROR.value
    assert TracebackPreprocessor.normalize_category("keyerror") == BugCategory.INDEX_KEY_ERROR.value
    assert TracebackPreprocessor.normalize_category("zerodivisionerror") == BugCategory.RUNTIME_LOGIC_ERROR.value
    assert TracebackPreprocessor.normalize_category("operationalerror") == BugCategory.DATABASE_NETWORK_ERROR.value
    assert TracebackPreprocessor.normalize_category("unauthorized") == BugCategory.PERMISSION_SECURITY_ERROR.value


def test_preprocessor_combined_error_and_traceback():
    preprocessor = TracebackPreprocessor()
    error_msg = "KeyError: 'user_id'"
    tb = 'File "/workspace/app/auth.py", line 18\n  return d["user_id"]'
    combined = preprocessor.preprocess(error_msg, tb)
    assert "KeyError" in combined
    assert "<FILE_PATH>/auth.py" in combined
    assert "line <LINE_NUM>" in combined
