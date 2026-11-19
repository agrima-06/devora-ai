"""Integration tests for Multi-Language Test Discovery and Execution Engine.
Verifies real execution through the SandboxService across Python pytest/unittest, Node.js,
and validates graceful UNAVAILABLE handling when language tools are not installed.
"""
import shutil
import pytest
from pathlib import Path

from app.agents.specialists.tester import tester_node as run_tester_node
from app.agents.state import DevoraWorkflowState
from app.services.sandbox_service import LocalIsolatedRunner, SandboxService
from app.services.test_discovery_service import TestDiscoveryService


@pytest.fixture
def sandbox():
    return SandboxService(runner=LocalIsolatedRunner())


# ---------------------------------------------------------------------------
# 1. Python + pytest Integration Test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_python_pytest_real_execution(tmp_path: Path):
    """Test real sandbox execution of a Python pytest suite with targeted selection."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    app_dir = workspace / "app"
    app_dir.mkdir()
    (app_dir / "calc.py").write_text("def add(a, b): return a + b\ndef sub(a, b): return a - b\n", encoding="utf-8")

    tests_dir = workspace / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_calc.py").write_text(
        "from app.calc import add, sub\n\n"
        "def test_add(): assert add(2, 3) == 5\n"
        "def test_sub(): assert sub(5, 2) == 3\n",
        encoding="utf-8",
    )
    (tests_dir / "test_other.py").write_text("def test_dummy(): assert True\n", encoding="utf-8")

    state: DevoraWorkflowState = {
        "task_id": "test-task-python",
        "workspace_path": str(workspace),
        "applied_file_changes": [{"file_path": "app/calc.py"}],
        "agent_execution_history": [],
    }

    res = await run_tester_node(state)
    assert res["current_agent"] == "tester"
    tr = res["test_results"]
    assert tr["passed"] is True
    assert tr["exit_code"] == 0
    assert tr["passed_tests"] == 2
    assert tr["is_targeted"] is True
    assert "tests/test_calc.py" in tr["selected_test_files"]
    assert "python" in tr["detected_languages"]
    assert "pytest" in tr["detected_frameworks"]


# ---------------------------------------------------------------------------
# 2. Python + unittest Integration Test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_python_unittest_real_execution(tmp_path: Path):
    """Test real sandbox execution of a Python unittest suite."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    tests_dir = workspace / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_math.py").write_text(
        "import unittest\n\n"
        "class TestMath(unittest.TestCase):\n"
        "    def test_mult(self): self.assertEqual(3 * 4, 12)\n"
        "    def test_div(self): self.assertEqual(10 / 2, 5)\n",
        encoding="utf-8",
    )

    discovery = TestDiscoveryService(workspace_path=workspace)
    suite = discovery.discover_suite(workspace)
    plan = discovery._build_execution_plan(
        framework="unittest",
        repo_dir=workspace,
        is_targeted=True,
        test_files=["tests/test_math.py"],
        reason="Targeted test run",
        fallback=False,
    )

    runner = LocalIsolatedRunner()
    exec_res = runner.run_command(command=plan.command, workspace_path=workspace)
    norm = discovery.parse_test_output(
        framework="unittest",
        stdout=exec_res.stdout,
        stderr=exec_res.stderr,
        exit_code=exec_res.exit_code,
        duration_seconds=exec_res.duration_seconds,
        command=plan.command,
    )

    assert norm.passed is True
    assert norm.total_tests == 2
    assert norm.passed_tests == 2
    assert norm.failed_tests == 0


# ---------------------------------------------------------------------------
# 3. JavaScript / Node.js Integration Test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_javascript_node_test_execution(tmp_path: Path):
    """Test JavaScript execution using node test runner if Node.js is present."""
    if not shutil.which("node"):
        pytest.skip("Node.js runtime is not available on this host.")

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "package.json").write_text(
        '{"name": "demo-js", "scripts": {"test": "node test.js"}}',
        encoding="utf-8",
    )
    (workspace / "test.js").write_text(
        "const assert = require('assert');\n"
        "assert.strictEqual(1 + 1, 2);\n"
        "console.log('Tests: 1 passed, 1 total');\n",
        encoding="utf-8",
    )

    discovery = TestDiscoveryService(workspace_path=workspace)
    suite = discovery.discover_suite(workspace)
    assert "javascript" in suite.detected_languages
    assert "npm test" in suite.detected_frameworks

    plan = discovery.select_tests_for_changes(suite, workspace, [])
    runner = LocalIsolatedRunner()
    exec_res = runner.run_command(command=plan.command, workspace_path=workspace)

    norm = discovery.parse_test_output(
        framework=plan.framework,
        stdout=exec_res.stdout,
        stderr=exec_res.stderr,
        exit_code=exec_res.exit_code,
        duration_seconds=exec_res.duration_seconds,
        command=plan.command,
    )

    assert norm.passed is True
    assert norm.total_tests >= 1
    assert norm.passed_tests >= 1


# ---------------------------------------------------------------------------
# 4. TypeScript / Vitest Discovery Test
# ---------------------------------------------------------------------------


def test_typescript_vitest_discovery(tmp_path: Path):
    """Test TypeScript + Vitest discovery and execution plan construction."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "tsconfig.json").write_text("{}", encoding="utf-8")
    (workspace / "package.json").write_text(
        '{"name": "ts-vitest", "devDependencies": {"vitest": "^1.0.0"}, "scripts": {"test": "vitest run"}}',
        encoding="utf-8",
    )
    src = workspace / "src"
    src.mkdir()
    (src / "service.ts").write_text("export const run = () => 42;", encoding="utf-8")
    (src / "service.test.ts").write_text("test('service', () => {});", encoding="utf-8")

    discovery = TestDiscoveryService(workspace_path=workspace)
    suite = discovery.discover_suite(workspace)

    assert "typescript" in suite.detected_languages
    assert "vitest" in suite.detected_frameworks
    assert "src/service.test.ts" in suite.test_files

    plan = discovery.select_tests_for_changes(suite, workspace, ["src/service.ts"])
    assert plan.is_targeted is True
    assert "src/service.test.ts" in plan.selected_files
    assert "npx vitest run src/service.test.ts" in plan.command


# ---------------------------------------------------------------------------
# 5. Go Test Real / Graceful Unavailable Handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_go_test_integration(tmp_path: Path):
    """Verify Go test discovery and either real execution or structured RUNNER_UNAVAILABLE."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "go.mod").write_text("module example.com/calc\n\ngo 1.22\n", encoding="utf-8")
    (workspace / "calc.go").write_text("package calc\n\nfunc Add(a, b int) int { return a + b }\n", encoding="utf-8")
    (workspace / "calc_test.go").write_text(
        "package calc\n\nimport \"testing\"\n\n"
        "func TestAdd(t *testing.T) {\n"
        "    if Add(2, 3) != 5 { t.Errorf(\"expected 5\") }\n"
        "}\n",
        encoding="utf-8",
    )

    discovery = TestDiscoveryService(workspace_path=workspace)
    suite = discovery.discover_suite(workspace)
    assert "go" in suite.detected_languages
    assert "go test" in suite.detected_frameworks

    plan = discovery.select_tests_for_changes(suite, workspace, ["calc.go"])
    runner = LocalIsolatedRunner()

    if shutil.which("go"):
        exec_res = runner.run_command(command=plan.command, workspace_path=workspace)
        norm = discovery.parse_test_output(
            framework=plan.framework,
            stdout=exec_res.stdout,
            stderr=exec_res.stderr,
            exit_code=exec_res.exit_code,
            duration_seconds=exec_res.duration_seconds,
            command=plan.command,
        )
        assert norm.passed is True
        assert norm.passed_tests >= 1
    else:
        # Runtime is absent: engine must gracefully handle RUNNER_UNAVAILABLE
        norm = discovery.parse_test_output(
            framework=plan.framework,
            stdout="",
            stderr="/bin/sh: line 1: go: command not found",
            exit_code=127,
            duration_seconds=0.01,
            command=plan.command,
        )
        assert norm.passed is False
        assert norm.execution_status == "UNAVAILABLE"
        assert norm.failure_classification == "RUNNER_UNAVAILABLE"


# ---------------------------------------------------------------------------
# 6. Rust Cargo Test Real / Graceful Unavailable Handling
# ---------------------------------------------------------------------------


def test_rust_cargo_test_integration(tmp_path: Path):
    """Verify Rust discovery and execution plan with graceful unavailable handling."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "Cargo.toml").write_text('[package]\nname = "rustdemo"\nversion = "0.1.0"\n', encoding="utf-8")
    tests_dir = workspace / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_lib.rs").write_text("#[test]\nfn it_works() { assert_eq!(2 + 2, 4); }\n", encoding="utf-8")

    discovery = TestDiscoveryService(workspace_path=workspace)
    suite = discovery.discover_suite(workspace)
    assert "rust" in suite.detected_languages
    assert "cargo test" in suite.detected_frameworks
    assert "tests/test_lib.rs" in suite.test_files

    plan = discovery.select_tests_for_changes(suite, workspace, ["src/lib.rs"])
    assert "cargo test" in plan.command

    if not shutil.which("cargo"):
        norm = discovery.parse_test_output(
            framework="cargo test",
            stdout="",
            stderr="cargo: command not found",
            exit_code=127,
            duration_seconds=0.01,
            command=plan.command,
        )
        assert norm.execution_status == "UNAVAILABLE"
        assert norm.failure_classification == "RUNNER_UNAVAILABLE"


# ---------------------------------------------------------------------------
# 7. Java Maven Test Real / Graceful Unavailable Handling
# ---------------------------------------------------------------------------


def test_java_maven_test_integration(tmp_path: Path):
    """Verify Java Maven discovery and execution plan with graceful unavailable handling."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "pom.xml").write_text("<project></project>", encoding="utf-8")
    src = workspace / "src" / "test" / "java" / "com" / "example"
    src.mkdir(parents=True)
    (src / "AppTest.java").write_text("public class AppTest {}", encoding="utf-8")

    discovery = TestDiscoveryService(workspace_path=workspace)
    suite = discovery.discover_suite(workspace)
    assert "java" in suite.detected_languages
    assert "maven test" in suite.detected_frameworks

    plan = discovery.select_tests_for_changes(suite, workspace, ["src/main/java/com/example/App.java"])
    assert plan.is_targeted is True
    assert "mvn test -Dtest=AppTest" in plan.command

    if not shutil.which("mvn"):
        norm = discovery.parse_test_output(
            framework="maven test",
            stdout="",
            stderr="mvn: command not found",
            exit_code=127,
            duration_seconds=0.01,
            command=plan.command,
        )
        assert norm.execution_status == "UNAVAILABLE"
        assert norm.failure_classification == "RUNNER_UNAVAILABLE"


# ---------------------------------------------------------------------------
# 8. Mixed-Language Repository Integration Test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mixed_language_repository_integration(tmp_path: Path):
    """Verify discovery and targeted test execution in a mixed Python + JS repository."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Backend Python
    backend_dir = workspace / "backend"
    backend_dir.mkdir()
    (backend_dir / "api.py").write_text("def get_data(): return {'status': 'ok'}\n", encoding="utf-8")
    tests_dir = workspace / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_api.py").write_text("from backend.api import get_data\ndef test_api(): assert get_data()['status'] == 'ok'\n", encoding="utf-8")

    # Frontend TS
    (workspace / "package.json").write_text('{"name": "frontend", "devDependencies": {"vitest": "1.0"}}', encoding="utf-8")
    (workspace / "tsconfig.json").write_text("{}", encoding="utf-8")
    frontend_dir = workspace / "frontend"
    frontend_dir.mkdir()
    (frontend_dir / "Widget.tsx").write_text("export const Widget = () => null;", encoding="utf-8")
    (frontend_dir / "Widget.test.tsx").write_text("test('widget', () => {});", encoding="utf-8")

    discovery = TestDiscoveryService(workspace_path=workspace)
    suite = discovery.discover_suite(workspace)

    assert "python" in suite.detected_languages
    assert "typescript" in suite.detected_languages
    assert "tests/test_api.py" in suite.test_files
    assert "frontend/Widget.test.tsx" in suite.test_files

    # When Python file is modified, targets Python tests
    py_plan = discovery.select_tests_for_changes(suite, workspace, ["backend/api.py"])
    assert py_plan.is_targeted is True
    assert "tests/test_api.py" in py_plan.selected_files

    # Execute Python test via tester_node
    state: DevoraWorkflowState = {
        "task_id": "mixed-task",
        "workspace_path": str(workspace),
        "applied_file_changes": [{"file_path": "backend/api.py"}],
        "agent_execution_history": [],
    }
    res = await run_tester_node(state)
    assert res["test_results"]["passed"] is True
    assert res["test_results"]["is_targeted"] is True
    assert "python" in res["test_results"]["detected_languages"]
    assert "typescript" in res["test_results"]["detected_languages"]
