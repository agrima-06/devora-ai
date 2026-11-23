"""Unit tests for FlakyTestDetector: stability scoring, failure classification,
repeat execution bounds, fingerprint generation, and sensitive data sanitization.
"""
from dataclasses import asdict
from pathlib import Path
import pytest

from app.services.flaky_detector import (
    FlakyDetectionReport,
    FlakyTestDetector,
    SingleExecutionRecord,
)
from app.services.test_discovery_service import NormalizedTestResult


@pytest.fixture
def detector():
    return FlakyTestDetector()


# ---------------------------------------------------------------------------
# 1. Eligibility Checks
# ---------------------------------------------------------------------------


def test_passed_test_not_eligible(detector: FlakyTestDetector):
    norm = NormalizedTestResult(
        framework="pytest",
        command="pytest",
        exit_code=0,
        passed=True,
        total_tests=5,
        passed_tests=5,
        failed_tests=0,
        skipped_tests=0,
        duration_seconds=1.0,
        raw_stdout="",
        raw_stderr="",
    )
    eligible, reason = detector.is_eligible_for_flaky_detection(norm)
    assert eligible is False
    assert "passed successfully" in reason


def test_runner_unavailable_not_eligible(detector: FlakyTestDetector):
    norm = NormalizedTestResult(
        framework="maven test",
        command="mvn test",
        exit_code=127,
        passed=False,
        total_tests=0,
        passed_tests=0,
        failed_tests=0,
        skipped_tests=0,
        duration_seconds=0.01,
        raw_stdout="",
        raw_stderr="mvn: command not found",
        execution_status="UNAVAILABLE",
        failure_classification="RUNNER_UNAVAILABLE",
    )
    eligible, reason = detector.is_eligible_for_flaky_detection(norm)
    assert eligible is False
    assert "runner is unavailable" in reason


def test_missing_dependency_not_eligible(detector: FlakyTestDetector):
    norm = NormalizedTestResult(
        framework="pytest",
        command="pytest",
        exit_code=1,
        passed=False,
        total_tests=1,
        passed_tests=0,
        failed_tests=1,
        skipped_tests=0,
        duration_seconds=0.1,
        raw_stdout="",
        raw_stderr="ModuleNotFoundError: No module named 'requests'",
        failure_classification="MISSING_DEPENDENCY",
    )
    eligible, reason = detector.is_eligible_for_flaky_detection(norm)
    assert eligible is False
    assert "missing project dependency" in reason


def test_assertion_failure_is_eligible(detector: FlakyTestDetector):
    norm = NormalizedTestResult(
        framework="pytest",
        command="pytest tests/test_auth.py",
        exit_code=1,
        passed=False,
        total_tests=3,
        passed_tests=2,
        failed_tests=1,
        skipped_tests=0,
        duration_seconds=0.5,
        raw_stdout="",
        raw_stderr="",
        failure_classification="ASSERTION_FAILURE",
        failure_details=["FAILED tests/test_auth.py::test_login"],
    )
    eligible, reason = detector.is_eligible_for_flaky_detection(norm)
    assert eligible is True
    assert "Eligible" in reason


# ---------------------------------------------------------------------------
# 2. Stability Scoring & Classification Rules
# ---------------------------------------------------------------------------


def test_scoring_all_runs_pass(detector: FlakyTestDetector):
    runs = [
        SingleExecutionRecord(run_index=1, exit_code=0, passed=True, duration_seconds=0.2),
        SingleExecutionRecord(run_index=2, exit_code=0, passed=True, duration_seconds=0.2),
        SingleExecutionRecord(run_index=3, exit_code=0, passed=True, duration_seconds=0.2),
    ]
    score, classification = detector.calculate_stability(runs)
    assert score == 100.0
    assert classification == "STABLE_PASS"


def test_scoring_all_runs_fail(detector: FlakyTestDetector):
    runs = [
        SingleExecutionRecord(run_index=1, exit_code=1, passed=False, duration_seconds=0.2),
        SingleExecutionRecord(run_index=2, exit_code=1, passed=False, duration_seconds=0.2),
        SingleExecutionRecord(run_index=3, exit_code=1, passed=False, duration_seconds=0.2),
    ]
    score, classification = detector.calculate_stability(runs)
    assert score == 0.0
    assert classification == "CONSISTENT_FAILURE"


def test_scoring_mixed_runs_flaky(detector: FlakyTestDetector):
    # 2 passes, 1 failure = 66.7% stability
    runs = [
        SingleExecutionRecord(run_index=1, exit_code=1, passed=False, duration_seconds=0.2),
        SingleExecutionRecord(run_index=2, exit_code=0, passed=True, duration_seconds=0.2),
        SingleExecutionRecord(run_index=3, exit_code=0, passed=True, duration_seconds=0.2),
    ]
    score, classification = detector.calculate_stability(runs)
    assert score == 66.7
    assert classification == "FLAKY"


def test_scoring_infrastructure_failures_inconclusive(detector: FlakyTestDetector):
    runs = [
        SingleExecutionRecord(run_index=1, exit_code=127, passed=False, duration_seconds=0.01, is_infra_error=True),
        SingleExecutionRecord(run_index=2, exit_code=127, passed=False, duration_seconds=0.01, is_infra_error=True),
    ]
    score, classification = detector.calculate_stability(runs)
    assert classification == "INCONCLUSIVE"


def test_scoring_timeouts_inconclusive(detector: FlakyTestDetector):
    runs = [
        SingleExecutionRecord(run_index=1, exit_code=-1, passed=False, duration_seconds=60.0, is_timeout=True),
        SingleExecutionRecord(run_index=2, exit_code=-1, passed=False, duration_seconds=60.0, is_timeout=True),
    ]
    score, classification = detector.calculate_stability(runs)
    assert classification == "INCONCLUSIVE"


def test_scoring_zero_runs_unverified(detector: FlakyTestDetector):
    score, classification = detector.calculate_stability([])
    assert score == 0.0
    assert classification == "UNVERIFIED"


# ---------------------------------------------------------------------------
# 3. Test Identifier Extraction
# ---------------------------------------------------------------------------


def test_extract_identifier_pytest(detector: FlakyTestDetector):
    ident, t_file = detector.extract_test_identifier(
        test_command="pytest -v tests/test_auth.py",
        failure_details=["FAILED tests/test_auth.py::test_jwt_signature - AssertionError"],
    )
    assert ident == "tests/test_auth.py::test_jwt_signature"
    assert t_file == "tests/test_auth.py"


def test_extract_identifier_unittest(detector: FlakyTestDetector):
    ident, t_file = detector.extract_test_identifier(
        test_command="python -m unittest tests/test_math.py",
        failure_details=["FAIL: test_divide_zero (tests.test_math.TestMath)"],
    )
    assert ident == "tests.test_math.TestMath.test_divide_zero"
    assert t_file == "tests.test_math.TestMath"


def test_extract_identifier_jest(detector: FlakyTestDetector):
    ident, t_file = detector.extract_test_identifier(
        test_command="npx jest src/Button.test.tsx",
        failure_details=["FAIL src/Button.test.tsx"],
    )
    assert ident == "src/Button.test.tsx"
    assert t_file == "src/Button.test.tsx"


def test_extract_identifier_go_test(detector: FlakyTestDetector):
    ident, _ = detector.extract_test_identifier(
        test_command="go test -v ./pkg/auth/...",
        failure_details=["--- FAIL: TestSessionExpiry (0.01s)"],
        selected_files=["pkg/auth/auth_test.go"],
    )
    assert ident == "TestSessionExpiry"


def test_extract_identifier_cargo_test(detector: FlakyTestDetector):
    ident, _ = detector.extract_test_identifier(
        test_command="cargo test",
        failure_details=["test tests::test_hash_collision ... FAILED"],
        selected_files=["tests/test_hash.rs"],
    )
    assert ident == "tests::test_hash_collision"


# ---------------------------------------------------------------------------
# 4. Credential Sanitization
# ---------------------------------------------------------------------------
from tests.fixtures.synthetic_credentials import (
    get_synthetic_google_api_key,
    get_synthetic_github_pat,
    get_synthetic_bearer_token,
)


def test_sanitize_record_history(detector: FlakyTestDetector):
    history = [
        {"run_index": 1, "error_preview": f"Failed with token {get_synthetic_github_pat()}"},
        {"run_index": 2, "error_preview": f"Failed with key {get_synthetic_google_api_key()}"},
        {"run_index": 3, "error_preview": f"Authorization: {get_synthetic_bearer_token()}"},
    ]
    cleaned = detector._sanitize_record_history(history)
    for c in cleaned:
        assert "ghp_" not in c["error_preview"]
        assert "AIza" not in c["error_preview"]
        assert "eyJ" not in c["error_preview"]
        assert "[REDACTED]" in c["error_preview"]
