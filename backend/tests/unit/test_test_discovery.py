"""Unit tests for TestDiscoveryService: multi-language detection, framework discovery,
targeted test selection, output normalization, and sandbox safety.
"""
import pytest
from pathlib import Path

from app.core.exceptions import BadRequestException
from app.services.test_discovery_service import (
    DiscoveredSuite,
    NormalizedTestResult,
    TestDiscoveryService,
    TestExecutionPlan,
)


@pytest.fixture
def discovery_service():
    return TestDiscoveryService()


# ---------------------------------------------------------------------------
# 1. Language & Manifest Detection Tests
# ---------------------------------------------------------------------------


def test_detect_python_repository(tmp_path: Path, discovery_service: TestDiscoveryService):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'sample'\n", encoding="utf-8")
    (tmp_path / "main.py").write_text("print('hello')", encoding="utf-8")

    langs = discovery_service.detect_languages(tmp_path)
    assert "python" in langs
    pm = discovery_service.detect_package_manager(tmp_path, langs)
    assert pm == "pip"


def test_detect_javascript_repository(tmp_path: Path, discovery_service: TestDiscoveryService):
    (tmp_path / "package.json").write_text('{"name": "sample-js"}', encoding="utf-8")
    (tmp_path / "package-lock.json").write_text("{}", encoding="utf-8")
    (tmp_path / "index.js").write_text("console.log('hi');", encoding="utf-8")

    langs = discovery_service.detect_languages(tmp_path)
    assert "javascript" in langs
    assert "typescript" not in langs
    pm = discovery_service.detect_package_manager(tmp_path, langs)
    assert pm == "npm"


def test_detect_typescript_repository(tmp_path: Path, discovery_service: TestDiscoveryService):
    (tmp_path / "package.json").write_text('{"name": "sample-ts"}', encoding="utf-8")
    (tmp_path / "tsconfig.json").write_text('{"compilerOptions": {}}', encoding="utf-8")
    (tmp_path / "yarn.lock").write_text("", encoding="utf-8")

    langs = discovery_service.detect_languages(tmp_path)
    assert "typescript" in langs
    pm = discovery_service.detect_package_manager(tmp_path, langs)
    assert pm == "yarn"


def test_detect_go_repository(tmp_path: Path, discovery_service: TestDiscoveryService):
    (tmp_path / "go.mod").write_text("module example.com/app\n\ngo 1.22\n", encoding="utf-8")
    (tmp_path / "main.go").write_text("package main\n\nfunc main() {}", encoding="utf-8")

    langs = discovery_service.detect_languages(tmp_path)
    assert "go" in langs
    pm = discovery_service.detect_package_manager(tmp_path, langs)
    assert pm == "go modules"


def test_detect_rust_repository(tmp_path: Path, discovery_service: TestDiscoveryService):
    (tmp_path / "Cargo.toml").write_text('[package]\nname = "demo"\nversion = "0.1.0"\n', encoding="utf-8")
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.rs").write_text("fn main() {}", encoding="utf-8")

    langs = discovery_service.detect_languages(tmp_path)
    assert "rust" in langs
    pm = discovery_service.detect_package_manager(tmp_path, langs)
    assert pm == "cargo"


def test_detect_java_repository(tmp_path: Path, discovery_service: TestDiscoveryService):
    (tmp_path / "pom.xml").write_text("<project></project>", encoding="utf-8")
    src = tmp_path / "src" / "main" / "java"
    src.mkdir(parents=True)
    (src / "App.java").write_text("public class App {}", encoding="utf-8")

    langs = discovery_service.detect_languages(tmp_path)
    assert "java" in langs
    pm = discovery_service.detect_package_manager(tmp_path, langs)
    assert pm == "maven"


def test_detect_multi_language_repository(tmp_path: Path, discovery_service: TestDiscoveryService):
    # Monorepo with Python backend and TypeScript frontend
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'backend'\n", encoding="utf-8")
    (tmp_path / "package.json").write_text('{"name": "frontend"}', encoding="utf-8")
    (tmp_path / "tsconfig.json").write_text("{}", encoding="utf-8")

    langs = discovery_service.detect_languages(tmp_path)
    assert "python" in langs
    assert "typescript" in langs


# ---------------------------------------------------------------------------
# 2. Framework Detection Tests
# ---------------------------------------------------------------------------


def test_framework_detection_pytest(tmp_path: Path, discovery_service: TestDiscoveryService):
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    frameworks = discovery_service.detect_test_frameworks(tmp_path, ["python"])
    assert "pytest" in frameworks


def test_framework_detection_jest_vs_vitest(tmp_path: Path, discovery_service: TestDiscoveryService):
    # Vitest project
    (tmp_path / "package.json").write_text(
        '{"devDependencies": {"vitest": "^1.0.0"}, "scripts": {"test": "vitest run"}}',
        encoding="utf-8",
    )
    frameworks = discovery_service.detect_test_frameworks(tmp_path, ["typescript"])
    assert "vitest" in frameworks

    # Jest project
    (tmp_path / "package.json").write_text(
        '{"devDependencies": {"jest": "^29.0.0"}, "scripts": {"test": "jest"}}',
        encoding="utf-8",
    )
    frameworks = discovery_service.detect_test_frameworks(tmp_path, ["javascript"])
    assert "jest" in frameworks


def test_framework_detection_go_rust_java(tmp_path: Path, discovery_service: TestDiscoveryService):
    (tmp_path / "pom.xml").write_text("<project></project>", encoding="utf-8")
    assert "go test" in discovery_service.detect_test_frameworks(tmp_path, ["go"])
    assert "cargo test" in discovery_service.detect_test_frameworks(tmp_path, ["rust"])
    assert "maven test" in discovery_service.detect_test_frameworks(tmp_path, ["java"])


# ---------------------------------------------------------------------------
# 3. Test File Discovery & Directory Exclusions
# ---------------------------------------------------------------------------


def test_discover_test_files_with_exclusions(tmp_path: Path, discovery_service: TestDiscoveryService):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_auth.py").write_text("def test_ok(): pass", encoding="utf-8")
    (tests_dir / "test_api.py").write_text("def test_api(): pass", encoding="utf-8")

    # Files inside ignored directories MUST be excluded
    venv_dir = tmp_path / ".venv" / "lib" / "tests"
    venv_dir.mkdir(parents=True)
    (venv_dir / "test_internal.py").write_text("def test_int(): pass", encoding="utf-8")

    node_modules = tmp_path / "node_modules" / "pkg"
    node_modules.mkdir(parents=True)
    (node_modules / "pkg.test.js").write_text("test('x', () => {})", encoding="utf-8")

    files = discovery_service.discover_test_files(tmp_path, ["python", "javascript"])
    assert "tests/test_auth.py" in files
    assert "tests/test_api.py" in files
    assert not any(".venv" in f for f in files)
    assert not any("node_modules" in f for f in files)


# ---------------------------------------------------------------------------
# 4. Targeted Test Selection & Fallback
# ---------------------------------------------------------------------------


def test_targeted_test_selection_python(tmp_path: Path, discovery_service: TestDiscoveryService):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_auth.py").write_text("pass", encoding="utf-8")
    (tests_dir / "test_billing.py").write_text("pass", encoding="utf-8")

    suite = discovery_service.discover_suite(tmp_path)
    plan = discovery_service.select_tests_for_changes(
        suite=suite,
        repo_dir=tmp_path,
        modified_files=["app/auth.py"],
    )

    assert plan.is_targeted is True
    assert plan.fallback_occurred is False
    assert "tests/test_auth.py" in plan.selected_files
    assert "tests/test_billing.py" not in plan.selected_files
    assert "pytest -v tests/test_auth.py" in plan.command


def test_targeted_test_selection_typescript(tmp_path: Path, discovery_service: TestDiscoveryService):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "Button.tsx").write_text("export const Button = () => null;", encoding="utf-8")
    (src_dir / "Button.test.tsx").write_text("test('renders', () => {});", encoding="utf-8")
    (src_dir / "Modal.test.tsx").write_text("test('modal', () => {});", encoding="utf-8")
    (tmp_path / "package.json").write_text('{"devDependencies": {"vitest": "1.0"}}', encoding="utf-8")

    suite = discovery_service.discover_suite(tmp_path)
    plan = discovery_service.select_tests_for_changes(
        suite=suite,
        repo_dir=tmp_path,
        modified_files=["src/Button.tsx"],
    )

    assert plan.is_targeted is True
    assert "src/Button.test.tsx" in plan.selected_files
    assert "src/Modal.test.tsx" not in plan.selected_files
    assert "npx vitest run src/Button.test.tsx" in plan.command


def test_fallback_to_full_suite_when_no_targeted_match(tmp_path: Path, discovery_service: TestDiscoveryService):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_database.py").write_text("pass", encoding="utf-8")

    suite = discovery_service.discover_suite(tmp_path)
    # Modify an unrelated file without a direct test
    plan = discovery_service.select_tests_for_changes(
        suite=suite,
        repo_dir=tmp_path,
        modified_files=["app/unrelated_config.py"],
    )

    assert plan.is_targeted is False
    assert plan.fallback_occurred is True
    assert "pytest -v tests" in plan.command


def test_prevent_directory_traversal_in_modified_paths(tmp_path: Path, discovery_service: TestDiscoveryService):
    suite = discovery_service.discover_suite(tmp_path)
    with pytest.raises(BadRequestException):
        discovery_service.select_tests_for_changes(
            suite=suite,
            repo_dir=tmp_path,
            modified_files=["../../etc/passwd"],
        )


# ---------------------------------------------------------------------------
# 5. Output Normalization Tests Across Frameworks
# ---------------------------------------------------------------------------


def test_parse_pytest_output(discovery_service: TestDiscoveryService):
    stdout = "tests/test_auth.py ..F.\n\n================= 3 passed, 1 failed, 1 skipped in 0.45s ================="
    norm = discovery_service.parse_test_output(
        framework="pytest",
        stdout=stdout,
        stderr="",
        exit_code=1,
        duration_seconds=0.45,
        command="pytest",
    )

    assert norm.passed is False
    assert norm.total_tests == 5
    assert norm.passed_tests == 3
    assert norm.failed_tests == 1
    assert norm.skipped_tests == 1
    assert norm.failure_classification == "ASSERTION_FAILURE"


def test_parse_unittest_output(discovery_service: TestDiscoveryService):
    output = "Ran 8 tests in 0.120s\n\nFAILED (failures=2, errors=1, skipped=1)"
    norm = discovery_service.parse_test_output(
        framework="unittest",
        stdout="",
        stderr=output,
        exit_code=1,
        duration_seconds=0.12,
        command="python -m unittest",
    )

    assert norm.passed is False
    assert norm.total_tests == 8
    assert norm.failed_tests == 3
    assert norm.skipped_tests == 1
    assert norm.passed_tests == 4


def test_parse_jest_vitest_output(discovery_service: TestDiscoveryService):
    stdout = "Tests:       1 failed, 4 passed, 1 skipped, 6 total\nSnapshots:   0 total\nTime:        1.25 s"
    norm = discovery_service.parse_test_output(
        framework="vitest",
        stdout=stdout,
        stderr="",
        exit_code=1,
        duration_seconds=1.25,
        command="npx vitest run",
    )

    assert norm.passed is False
    assert norm.total_tests == 6
    assert norm.passed_tests == 4
    assert norm.failed_tests == 1
    assert norm.skipped_tests == 1


def test_parse_go_test_output(discovery_service: TestDiscoveryService):
    stdout = "=== RUN   TestLogin\n--- PASS: TestLogin (0.01s)\n=== RUN   TestLogout\n--- FAIL: TestLogout (0.02s)\nFAIL\nok  \texample.com/auth\t0.035s"
    norm = discovery_service.parse_test_output(
        framework="go test",
        stdout=stdout,
        stderr="",
        exit_code=1,
        duration_seconds=0.035,
        command="go test -v ./...",
    )

    assert norm.passed is False
    assert norm.passed_tests == 1
    assert norm.failed_tests == 1
    assert norm.total_tests == 2


def test_parse_cargo_test_output(discovery_service: TestDiscoveryService):
    stdout = "running 4 tests\ntest tests::test_add ... ok\ntest tests::test_sub ... ok\ntest tests::test_div ... ok\ntest tests::test_mul ... ok\n\ntest result: ok. 4 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s"
    norm = discovery_service.parse_test_output(
        framework="cargo test",
        stdout=stdout,
        stderr="",
        exit_code=0,
        duration_seconds=0.01,
        command="cargo test",
    )

    assert norm.passed is True
    assert norm.total_tests == 4
    assert norm.passed_tests == 4
    assert norm.failed_tests == 0


def test_parse_maven_test_output(discovery_service: TestDiscoveryService):
    stdout = "[INFO] Results:\n[INFO]\n[INFO] Tests run: 12, Failures: 1, Errors: 0, Skipped: 2\n[INFO]\n[ERROR] There are test failures."
    norm = discovery_service.parse_test_output(
        framework="maven test",
        stdout=stdout,
        stderr="",
        exit_code=1,
        duration_seconds=3.2,
        command="mvn test",
    )

    assert norm.passed is False
    assert norm.total_tests == 12
    assert norm.failed_tests == 1
    assert norm.skipped_tests == 2
    assert norm.passed_tests == 9


def test_parse_runner_unavailable(discovery_service: TestDiscoveryService):
    stderr = "/bin/sh: line 1: mvn: command not found"
    norm = discovery_service.parse_test_output(
        framework="maven test",
        stdout="",
        stderr=stderr,
        exit_code=127,
        duration_seconds=0.05,
        command="mvn test",
    )

    assert norm.passed is False
    assert norm.execution_status == "UNAVAILABLE"
    assert norm.failure_classification == "RUNNER_UNAVAILABLE"
    assert "not found in execution environment" in norm.failure_details[0]


def test_parse_execution_timeout(discovery_service: TestDiscoveryService):
    norm = discovery_service.parse_test_output(
        framework="pytest",
        stdout="",
        stderr="Execution timed out after 60 seconds.",
        exit_code=-1,
        duration_seconds=60.0,
        command="pytest",
    )

    assert norm.passed is False
    assert norm.execution_status == "TIMED_OUT"
    assert norm.failure_classification == "TIMEOUT"


def test_parse_missing_dependency(discovery_service: TestDiscoveryService):
    stderr = "Traceback (most recent call last):\n  File 'test.py', line 1\nModuleNotFoundError: No module named 'requests'"
    norm = discovery_service.parse_test_output(
        framework="pytest",
        stdout="",
        stderr=stderr,
        exit_code=1,
        duration_seconds=0.1,
        command="pytest",
    )

    assert norm.passed is False
    assert norm.failure_classification == "MISSING_DEPENDENCY"
    assert "requests" in (norm.diagnostic_warning or "")
