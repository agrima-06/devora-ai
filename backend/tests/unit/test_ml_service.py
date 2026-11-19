"""Unit tests for BugClassifierService inference, latency, and ambiguity calibration."""
import pytest
from app.ml.preprocessor import BugCategory
from app.ml.service import BugClassifierService


def test_service_predict_accuracy():
    service = BugClassifierService.get_instance()

    # 1. Syntax Error
    res_syntax = service.predict(
        error_message="SyntaxError: invalid syntax",
        traceback='  File "main.py", line 12\n    def test(\n             ^',
    )
    assert res_syntax.predicted_category == BugCategory.SYNTAX_ERROR.value
    assert res_syntax.confidence > 0.15
    assert res_syntax.inference_time_ms < 50.0  # Ultra-fast

    # 2. Dependency Error
    res_import = service.predict(
        error_message="ModuleNotFoundError: No module named 'fastapi'",
        traceback='Traceback:\n File "app.py", line 1\n import fastapi',
    )
    assert res_import.predicted_category == BugCategory.IMPORT_DEPENDENCY_ERROR.value

    # 3. Type Error
    res_type = service.predict(
        error_message="TypeError: unsupported operand type(s) for +: 'int' and 'str'",
        traceback='File "billing.py", line 45\n total = price + tax',
    )
    assert res_type.predicted_category == BugCategory.TYPE_ERROR.value

    # 4. Null Dereference
    res_null = service.predict(
        error_message="AttributeError: 'NoneType' object has no attribute 'id'",
        traceback='File "repo.py", line 8\n return project.id',
    )
    assert res_null.predicted_category == BugCategory.ATTRIBUTE_NULL_REFERENCE_ERROR.value

    # 5. Key Error
    res_key = service.predict(
        error_message="KeyError: 'user_id'",
        traceback='File "auth.py", line 22\n return payload["user_id"]',
    )
    assert res_key.predicted_category == BugCategory.INDEX_KEY_ERROR.value

    # 6. Runtime Logic
    res_logic = service.predict(
        error_message="ZeroDivisionError: division by zero",
        traceback='File "calc.py", line 14\n return x / 0',
    )
    assert res_logic.predicted_category == BugCategory.RUNTIME_LOGIC_ERROR.value

    # 7. Database / Network
    res_db = service.predict(
        error_message="asyncpg.exceptions.CannotConnectNowError: connection refused",
        traceback='File "db.py", line 55\n await asyncpg.connect("postgresql://localhost:5432")',
    )
    assert res_db.predicted_category == BugCategory.DATABASE_NETWORK_ERROR.value

    # 8. Permission / Security
    res_perm = service.predict(
        error_message="PermissionError: [Errno 13] Permission denied: '/var/log/app.log'",
        traceback='File "log.py", line 3\n open("/var/log/app.log", "w")',
    )
    assert res_perm.predicted_category == BugCategory.PERMISSION_SECURITY_ERROR.value


def test_service_ambiguity_warning():
    service = BugClassifierService.get_instance()
    # Ambiguous or minimal single word input
    res = service.predict(error_message="error")
    assert len(res.top_probabilities) > 1
    # Check that warning is populated if low confidence
    if res.is_low_confidence:
        assert res.warning is not None


def test_service_input_hash_deterministic():
    service = BugClassifierService.get_instance()
    msg = "KeyError: 'session'"
    tb = 'File "test.py", line 10\n d["session"]'
    res1 = service.predict(msg, tb)
    res2 = service.predict(msg, tb)
    assert res1.input_hash == res2.input_hash
