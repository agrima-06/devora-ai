"""Multi-language test discovery, manifest inspection, targeted test selection, and output normalization engine."""
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from app.config import settings
from app.core.exceptions import BadRequestException
from app.core.logging import get_logger

logger = get_logger("test_discovery_service")

# Standard directories to ignore during test discovery
IGNORED_DIRS: Set[str] = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    ".venv",
    "venv",
    "env",
    "vendor",
    "target",
    "dist",
    "build",
    "out",
    "bin",
    "obj",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".coverage",
    "coverage",
    ".next",
    ".nuxt",
    ".turbo",
    ".cache",
    ".gradle",
    ".idea",
    ".vscode",
}


@dataclass
class NormalizedTestResult:
    """Standardized test execution result across all languages and frameworks."""
    framework: str
    command: str
    exit_code: int
    passed: bool
    total_tests: int
    passed_tests: int
    failed_tests: int
    skipped_tests: int
    duration_seconds: float
    raw_stdout: str
    raw_stderr: str
    failure_details: List[str] = field(default_factory=list)
    failure_classification: Optional[str] = None
    execution_status: str = "PASSED"  # PASSED, FAILED, SKIPPED, UNAVAILABLE, TIMED_OUT, OOM_KILLED
    is_targeted: bool = False
    selected_test_files: List[str] = field(default_factory=list)
    diagnostic_warning: Optional[str] = None

    # Extended Resource Telemetry (Phase 9 Stage 9.3)
    peak_memory_rss_bytes: Optional[int] = None
    peak_memory_rss_mb: Optional[float] = None
    cpu_time_seconds: Optional[float] = None
    wall_time_seconds: Optional[float] = None
    memory_limit_bytes: Optional[int] = None
    memory_limit_mb: Optional[float] = None
    cpu_limit: Optional[float] = None
    oom_killed: bool = False
    termination_reason: Optional[str] = None
    exit_classification: str = "EXECUTION_FAILURE"
    resource_telemetry_available: bool = False


@dataclass
class DiscoveredSuite:
    """Discovered test suite metadata for a repository."""
    detected_languages: List[str]
    detected_frameworks: List[str]
    primary_language: str
    primary_framework: str
    package_manager: Optional[str]
    test_files: List[str]
    discovery_status: str  # DISCOVERED, UNAVAILABLE, DISCOVERY_ERROR
    config_files: List[str] = field(default_factory=list)
    diagnostic_message: Optional[str] = None


@dataclass
class TestExecutionPlan:
    """Actionable test execution command and metadata."""
    __test__ = False

    command: str
    args: List[str]
    framework: str
    is_targeted: bool
    selected_files: List[str]
    selection_reason: str
    fallback_occurred: bool
    timeout_seconds: int = 60
    original_timeout_seconds: int = 60
    timeout_scaling_reason: Optional[str] = None


class TestTimeoutScaler:
    """Dynamic test timeout scaling engine based on suite characteristics."""

    @classmethod
    def calculate_timeout(
        cls,
        total_tests: int,
        base_timeout: Optional[int] = None,
    ) -> Tuple[int, str]:
        """Calculate deterministic timeout scaling based on suite size and configured policies.

        - Suites with <= threshold tests: base timeout (default 60s)
        - Suites with > threshold tests: base timeout * multiplier, capped at ceiling
        """
        threshold = settings.TEST_LARGE_SUITE_THRESHOLD
        multiplier = settings.TEST_LARGE_SUITE_MULTIPLIER
        ceiling = settings.TEST_MAX_TIMEOUT_SECONDS
        base = base_timeout or settings.TEST_BASE_TIMEOUT_SECONDS

        if total_tests <= threshold:
            return base, f"Standard suite ({total_tests} tests <= threshold {threshold}): base timeout {base}s"

        scaled = int(base * multiplier)
        final_timeout = min(scaled, ceiling)
        reason = (
            f"Large suite detected ({total_tests} tests > threshold {threshold}): "
            f"scaled from {base}s to {final_timeout}s (multiplier={multiplier}, ceiling={ceiling}s)"
        )
        logger.info(
            "test_timeout_scaled",
            total_tests=total_tests,
            base_timeout=base,
            scaled_timeout=final_timeout,
            threshold=threshold,
            ceiling=ceiling,
        )
        return final_timeout, reason


class TestDiscoveryService:
    """Language-aware test discovery, targeted test selection, and execution planning service."""
    __test__ = False

    def __init__(self, workspace_path: Optional[Path] = None):
        self.workspace_path = workspace_path

    # ---------------------------------------------------------------------------
    # Language Detection
    # ---------------------------------------------------------------------------

    def detect_languages(self, repo_dir: Path) -> List[str]:
        """Detect all programming languages present in the repository with evidence."""
        detected = set()

        # Check manifests and root configurations
        if (repo_dir / "pyproject.toml").exists() or (repo_dir / "requirements.txt").exists() or (repo_dir / "setup.py").exists() or (repo_dir / "setup.cfg").exists():
            detected.add("python")
        if (repo_dir / "package.json").exists():
            # Check if TypeScript is configured
            if (repo_dir / "tsconfig.json").exists():
                detected.add("typescript")
            else:
                detected.add("javascript")
        if (repo_dir / "go.mod").exists() or (repo_dir / "go.work").exists():
            detected.add("go")
        if (repo_dir / "Cargo.toml").exists():
            detected.add("rust")
        if (repo_dir / "pom.xml").exists() or (repo_dir / "build.gradle").exists() or (repo_dir / "build.gradle.kts").exists():
            detected.add("java")

        # Scan for source files if manifests alone didn't capture or to confirm
        for root, dirs, files in os.walk(repo_dir):
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext == ".py":
                    detected.add("python")
                elif ext in (".ts", ".tsx"):
                    detected.add("typescript")
                elif ext in (".js", ".jsx", ".mjs", ".cjs"):
                    detected.add("javascript")
                elif ext == ".go":
                    detected.add("go")
                elif ext == ".rs":
                    detected.add("rust")
                elif ext == ".java":
                    detected.add("java")

        # Order consistently
        priority_order = ["python", "typescript", "javascript", "go", "rust", "java"]
        return [lang for lang in priority_order if lang in detected] or ["unknown"]

    # ---------------------------------------------------------------------------
    # Package Manager Detection
    # ---------------------------------------------------------------------------

    def detect_package_manager(self, repo_dir: Path, languages: List[str]) -> Optional[str]:
        """Detect the package manager used in the repository."""
        if "javascript" in languages or "typescript" in languages:
            if (repo_dir / "pnpm-lock.yaml").exists():
                return "pnpm"
            if (repo_dir / "yarn.lock").exists():
                return "yarn"
            if (repo_dir / "package-lock.json").exists() or (repo_dir / "package.json").exists():
                return "npm"

        if "python" in languages:
            if (repo_dir / "uv.lock").exists():
                return "uv"
            if (repo_dir / "poetry.lock").exists():
                return "poetry"
            if (repo_dir / "Pipfile").exists():
                return "pipenv"
            if (repo_dir / "pyproject.toml").exists() or (repo_dir / "requirements.txt").exists():
                return "pip"

        if "go" in languages and (repo_dir / "go.mod").exists():
            return "go modules"

        if "rust" in languages and (repo_dir / "Cargo.toml").exists():
            return "cargo"

        if "java" in languages:
            if (repo_dir / "pom.xml").exists():
                return "maven"
            if (repo_dir / "build.gradle").exists() or (repo_dir / "build.gradle.kts").exists():
                return "gradle"

        return None

    # ---------------------------------------------------------------------------
    # Framework Discovery
    # ---------------------------------------------------------------------------

    def detect_test_frameworks(self, repo_dir: Path, languages: List[str]) -> List[str]:
        """Detect all testing frameworks configured in the repository."""
        frameworks = []

        # Python frameworks
        if "python" in languages:
            has_pytest = False
            # Check pyproject.toml, pytest.ini, setup.cfg, tox.ini
            for cfg in ("pytest.ini", "tox.ini", "setup.cfg"):
                if (repo_dir / cfg).exists():
                    has_pytest = True
                    break
            if not has_pytest and (repo_dir / "pyproject.toml").exists():
                try:
                    content = (repo_dir / "pyproject.toml").read_text(encoding="utf-8", errors="ignore")
                    if "pytest" in content or "[tool.pytest" in content:
                        has_pytest = True
                except Exception:
                    pass
            if not has_pytest and (repo_dir / "requirements.txt").exists():
                try:
                    content = (repo_dir / "requirements.txt").read_text(encoding="utf-8", errors="ignore")
                    if re.search(r"^pytest(?:[=><\s]|$)", content, re.MULTILINE):
                        has_pytest = True
                except Exception:
                    pass

            if has_pytest:
                frameworks.append("pytest")
            else:
                # Default python runner is pytest if tests exist, with unittest compatibility
                frameworks.append("pytest")

        # JS / TS frameworks
        if "javascript" in languages or "typescript" in languages:
            pkg_json = repo_dir / "package.json"
            if pkg_json.exists():
                try:
                    data = json.loads(pkg_json.read_text(encoding="utf-8", errors="ignore"))
                    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                    scripts = data.get("scripts", {})
                    test_script = scripts.get("test", "")

                    if "vitest" in deps or "vitest" in test_script:
                        frameworks.append("vitest")
                    if "jest" in deps or "jest" in test_script:
                        frameworks.append("jest")

                    if not frameworks and "test" in scripts:
                        # Fallback to general npm test
                        frameworks.append("npm test")
                except Exception as e:
                    logger.warning("failed_to_parse_package_json", error=str(e))

        # Go test
        if "go" in languages:
            frameworks.append("go test")

        # Rust test
        if "rust" in languages:
            frameworks.append("cargo test")

        # Java test
        if "java" in languages:
            if (repo_dir / "pom.xml").exists():
                frameworks.append("maven test")
            elif (repo_dir / "build.gradle").exists() or (repo_dir / "build.gradle.kts").exists():
                frameworks.append("gradle test")

        return frameworks or ["unknown"]

    # ---------------------------------------------------------------------------
    # Test File Discovery
    # ---------------------------------------------------------------------------

    def discover_test_files(self, repo_dir: Path, languages: List[str]) -> List[str]:
        """Discover all test files in the workspace while ignoring vendor/cache directories."""
        test_files = []

        python_patterns = (re.compile(r"^test_.*\.py$"), re.compile(r".*_test\.py$"))
        js_patterns = (
            re.compile(r".*\.(test|spec)\.(js|jsx|ts|tsx|mjs|cjs)$"),
        )
        go_patterns = (re.compile(r".*_test\.go$"),)
        rust_patterns = (re.compile(r".*_test\.rs$"), re.compile(r"^test.*\.rs$"))
        java_patterns = (re.compile(r".*Test\.java$"), re.compile(r"^Test.*\.java$"), re.compile(r".*TestCase\.java$"))

        for root, dirs, files in os.walk(repo_dir):
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
            rel_root = Path(root).relative_to(repo_dir)

            for f in files:
                rel_path = (rel_root / f).as_posix() if str(rel_root) != "." else f

                # Python
                if "python" in languages and any(p.match(f) for p in python_patterns):
                    test_files.append(rel_path)
                # JS / TS
                elif ("javascript" in languages or "typescript" in languages) and any(p.match(f) for p in js_patterns):
                    test_files.append(rel_path)
                # Go
                elif "go" in languages and any(p.match(f) for p in go_patterns):
                    test_files.append(rel_path)
                # Rust
                elif "rust" in languages and ("tests/" in rel_path or any(p.match(f) for p in rust_patterns)):
                    test_files.append(rel_path)
                # Java
                elif "java" in languages and any(p.match(f) for p in java_patterns):
                    test_files.append(rel_path)

        return sorted(test_files)

    # ---------------------------------------------------------------------------
    # Complete Suite Discovery
    # ---------------------------------------------------------------------------

    def discover_suite(self, repo_dir: Path) -> DiscoveredSuite:
        """Perform comprehensive language, framework, and test file discovery."""
        if not repo_dir.exists() or not repo_dir.is_dir():
            return DiscoveredSuite(
                detected_languages=[],
                detected_frameworks=[],
                primary_language="unknown",
                primary_framework="unknown",
                package_manager=None,
                test_files=[],
                discovery_status="DISCOVERY_ERROR",
                diagnostic_message=f"Workspace path '{repo_dir}' does not exist or is not a directory.",
            )

        languages = self.detect_languages(repo_dir)
        package_manager = self.detect_package_manager(repo_dir, languages)
        frameworks = self.detect_test_frameworks(repo_dir, languages)
        test_files = self.discover_test_files(repo_dir, languages)

        primary_lang = languages[0] if languages else "unknown"
        primary_framework = frameworks[0] if frameworks else "unknown"

        # Detect config files
        config_files = []
        for cfg in (
            "pyproject.toml", "pytest.ini", "setup.cfg", "package.json", "tsconfig.json",
            "go.mod", "Cargo.toml", "pom.xml", "build.gradle"
        ):
            if (repo_dir / cfg).exists():
                config_files.append(cfg)

        status = "DISCOVERED" if test_files or primary_framework != "unknown" else "UNAVAILABLE"
        diag_msg = None
        if not test_files:
            diag_msg = f"No automated test files discovered in repository for language(s): {', '.join(languages)}."

        return DiscoveredSuite(
            detected_languages=languages,
            detected_frameworks=frameworks,
            primary_language=primary_lang,
            primary_framework=primary_framework,
            package_manager=package_manager,
            test_files=test_files,
            discovery_status=status,
            config_files=config_files,
            diagnostic_message=diag_msg,
        )

    # ---------------------------------------------------------------------------
    # Targeted Test Selection
    # ---------------------------------------------------------------------------

    def select_tests_for_changes(
        self,
        suite: DiscoveredSuite,
        repo_dir: Path,
        modified_files: List[str],
    ) -> TestExecutionPlan:
        """Plan test execution, attempting targeted test selection for modified files with safe full-suite fallback."""
        framework = suite.primary_framework
        clean_modified = [f.strip().lstrip("/") for f in modified_files if f.strip()]

        # Prevent directory traversal attacks in modified file names
        for f in clean_modified:
            if ".." in f or f.startswith("/") or f.startswith("\\"):
                raise BadRequestException(f"Invalid modified file path '{f}' detected.")

        matched_test_files: List[str] = []

        if clean_modified and suite.test_files:
            # Map modified source files to test files
            for mod_file in clean_modified:
                mod_path = Path(mod_file)
                base_name = mod_path.stem  # e.g., 'auth' from 'app/auth.py'
                parent_dir = mod_path.parent.as_posix()

                for test_file in suite.test_files:
                    test_path = Path(test_file)
                    test_stem = test_path.stem

                    # Python matching: test_auth.py, auth_test.py
                    if suite.primary_language == "python":
                        if test_stem in (f"test_{base_name}", f"{base_name}_test"):
                            matched_test_files.append(test_file)
                        elif base_name in test_stem and len(base_name) > 3:
                            matched_test_files.append(test_file)

                    # JS / TS matching: auth.test.ts, auth.spec.js
                    elif suite.primary_language in ("javascript", "typescript"):
                        if test_stem.startswith(f"{base_name}.test") or test_stem.startswith(f"{base_name}.spec"):
                            matched_test_files.append(test_file)
                        elif test_path.name in (f"{base_name}.test.ts", f"{base_name}.test.tsx", f"{base_name}.test.js", f"{base_name}.test.jsx", f"{base_name}.spec.ts", f"{base_name}.spec.js"):
                            matched_test_files.append(test_file)

                    # Go matching: auth_test.go
                    elif suite.primary_language == "go":
                        if test_stem == f"{base_name}_test":
                            matched_test_files.append(test_file)
                        elif parent_dir != "." and test_file.startswith(parent_dir):
                            matched_test_files.append(test_file)

                    # Rust matching: tests/test_auth.rs or tests/auth.rs
                    elif suite.primary_language == "rust":
                        if test_stem in (base_name, f"test_{base_name}", f"{base_name}_test"):
                            matched_test_files.append(test_file)

                    # Java matching: AuthServiceTest.java, TestAuthService.java
                    elif suite.primary_language == "java":
                        if test_stem in (f"{base_name}Test", f"Test{base_name}", f"{base_name}TestCase"):
                            matched_test_files.append(test_file)

        # Remove duplicates while preserving order
        unique_matches = list(dict.fromkeys(matched_test_files))

        if unique_matches:
            # Targeted execution succeeded
            return self._build_execution_plan(
                framework=framework,
                repo_dir=repo_dir,
                is_targeted=True,
                test_files=unique_matches,
                reason=f"Targeted {len(unique_matches)} test file(s) matching modified code ({', '.join(clean_modified[:3])}).",
                fallback=False,
            )

        # Fallback to full test suite
        fallback_reason = "No direct matching test files found for modified code; falling back to full test suite." if clean_modified else "Running full repository test suite."
        return self._build_execution_plan(
            framework=framework,
            repo_dir=repo_dir,
            is_targeted=False,
            test_files=suite.test_files,
            reason=fallback_reason,
            fallback=bool(clean_modified),
        )

    # ---------------------------------------------------------------------------
    # Execution Command Builder
    # ---------------------------------------------------------------------------

    def _build_execution_plan(
        self,
        framework: str,
        repo_dir: Path,
        is_targeted: bool,
        test_files: List[str],
        reason: str,
        fallback: bool,
    ) -> TestExecutionPlan:
        """Construct safe command string and arguments for test runner."""
        # Sanitize test file arguments to prevent shell metacharacter injection
        safe_files = []
        for f in test_files:
            clean_f = f.strip().replace(";", "").replace("&", "").replace("|", "")
            if clean_f:
                safe_files.append(clean_f)

        if framework == "pytest":
            if is_targeted and safe_files:
                args = ["pytest", "-v"] + safe_files
                cmd = f"pytest -v {' '.join(safe_files)}"
            elif (repo_dir / "tests").exists():
                args = ["pytest", "-v", "tests"]
                cmd = "pytest -v tests"
            else:
                args = ["pytest"]
                cmd = "pytest"

        elif framework == "unittest":
            if is_targeted and safe_files:
                args = ["python", "-m", "unittest"] + safe_files
                cmd = f"python -m unittest {' '.join(safe_files)}"
            else:
                start_dir = "tests" if (repo_dir / "tests").exists() else "."
                args = ["python", "-m", "unittest", "discover", "-s", start_dir]
                cmd = f"python -m unittest discover -s {start_dir}"

        elif framework == "vitest":
            if is_targeted and safe_files:
                args = ["npx", "vitest", "run"] + safe_files
                cmd = f"npx vitest run {' '.join(safe_files)}"
            else:
                args = ["npx", "vitest", "run"]
                cmd = "npx vitest run"

        elif framework == "jest":
            if is_targeted and safe_files:
                args = ["npx", "jest", "--runInBand"] + safe_files
                cmd = f"npx jest --runInBand {' '.join(safe_files)}"
            else:
                args = ["npx", "jest", "--runInBand"]
                cmd = "npx jest --runInBand"

        elif framework == "npm test":
            if is_targeted and safe_files:
                args = ["npm", "test", "--"] + safe_files
                cmd = f"npm test -- {' '.join(safe_files)}"
            else:
                args = ["npm", "test"]
                cmd = "npm test"

        elif framework == "go test":
            if is_targeted and safe_files:
                # Group by directory for Go packages
                pkg_dirs = list(dict.fromkeys([Path(f).parent.as_posix() for f in safe_files]))
                pkg_targets = [f"./{d}/..." if d != "." else "./..." for d in pkg_dirs]
                args = ["go", "test", "-v"] + pkg_targets
                cmd = f"go test -v {' '.join(pkg_targets)}"
            else:
                args = ["go", "test", "-v", "./..."]
                cmd = "go test -v ./..."

        elif framework == "cargo test":
            if is_targeted and safe_files:
                target_names = [Path(f).stem for f in safe_files]
                test_args = []
                for t in target_names:
                    test_args.extend(["--test", t])
                args = ["cargo", "test"] + test_args
                cmd = f"cargo test {' '.join(test_args)}"
            else:
                args = ["cargo", "test"]
                cmd = "cargo test"

        elif framework == "maven test":
            if is_targeted and safe_files:
                class_names = [Path(f).stem for f in safe_files]
                test_param = f"-Dtest={','.join(class_names)}"
                args = ["mvn", "test", test_param]
                cmd = f"mvn test {test_param}"
            else:
                args = ["mvn", "test"]
                cmd = "mvn test"

        elif framework == "gradle test":
            if is_targeted and safe_files:
                class_names = [Path(f).stem for f in safe_files]
                test_args = []
                for c in class_names:
                    test_args.extend(["--tests", c])
                args = ["gradle", "test"] + test_args
                cmd = f"gradle test {' '.join(test_args)}"
            else:
                args = ["gradle", "test"]
                cmd = "gradle test"

        else:
            args = ["pytest"]
            cmd = "pytest"

        total_discovered_tests = len(safe_files) if is_targeted else len(test_files)
        scaled_timeout, scaling_reason = TestTimeoutScaler.calculate_timeout(
            total_tests=total_discovered_tests,
            base_timeout=settings.TEST_BASE_TIMEOUT_SECONDS,
        )

        return TestExecutionPlan(
            command=cmd,
            args=args,
            framework=framework,
            is_targeted=is_targeted,
            selected_files=safe_files if is_targeted else test_files,
            selection_reason=reason,
            fallback_occurred=fallback,
            timeout_seconds=scaled_timeout,
            original_timeout_seconds=settings.TEST_BASE_TIMEOUT_SECONDS,
            timeout_scaling_reason=scaling_reason,
        )

    # ---------------------------------------------------------------------------
    # Output Normalization
    # ---------------------------------------------------------------------------

    def parse_test_output(
        self,
        framework: str,
        stdout: str,
        stderr: str,
        exit_code: int,
        duration_seconds: float,
        command: str = "",
        is_targeted: bool = False,
        selected_files: Optional[List[str]] = None,
        oom_killed: bool = False,
        termination_reason: Optional[str] = None,
        exit_classification: Optional[str] = None,
        peak_memory_rss_bytes: Optional[int] = None,
        peak_memory_rss_mb: Optional[float] = None,
        cpu_time_seconds: Optional[float] = None,
        wall_time_seconds: Optional[float] = None,
        memory_limit_bytes: Optional[int] = None,
        memory_limit_mb: Optional[float] = None,
        cpu_limit: Optional[float] = None,
        resource_telemetry_available: bool = False,
    ) -> NormalizedTestResult:
        """Parse raw test stdout/stderr across any framework into NormalizedTestResult with telemetry."""
        stdout = stdout or ""
        stderr = stderr or ""
        combined = f"{stdout}\n{stderr}"

        # 1. Detect Out of Memory (OOM) termination
        if oom_killed or exit_classification == "OOM_KILLED":
            return NormalizedTestResult(
                framework=framework,
                command=command,
                exit_code=exit_code,
                passed=False,
                total_tests=0,
                passed_tests=0,
                failed_tests=1,
                skipped_tests=0,
                duration_seconds=duration_seconds,
                raw_stdout=stdout,
                raw_stderr=stderr,
                failure_details=[termination_reason or "Execution terminated due to memory exhaustion (OOMKilled)."],
                failure_classification="OOM_KILLED",
                execution_status="OOM_KILLED",
                is_targeted=is_targeted,
                selected_test_files=selected_files or [],
                diagnostic_warning="Execution terminated due to container memory limit exhaustion. Increase memory limit or batch test execution.",
                peak_memory_rss_bytes=peak_memory_rss_bytes,
                peak_memory_rss_mb=peak_memory_rss_mb,
                cpu_time_seconds=cpu_time_seconds,
                wall_time_seconds=wall_time_seconds,
                memory_limit_bytes=memory_limit_bytes,
                memory_limit_mb=memory_limit_mb,
                cpu_limit=cpu_limit,
                oom_killed=True,
                termination_reason=termination_reason or "Container exceeded memory limit (OOMKilled)",
                exit_classification="OOM_KILLED",
                resource_telemetry_available=resource_telemetry_available,
            )

        # 2. Detect tool/runner unavailability or command not found
        if exit_classification == "COMMAND_NOT_FOUND" or exit_code == 127 or "command not found" in combined.lower() or ("not found" in combined.lower() and exit_code != 0):
            return NormalizedTestResult(
                framework=framework,
                command=command,
                exit_code=exit_code,
                passed=False,
                total_tests=0,
                passed_tests=0,
                failed_tests=0,
                skipped_tests=0,
                duration_seconds=duration_seconds,
                raw_stdout=stdout,
                raw_stderr=stderr,
                failure_details=[f"Test runner executable for framework '{framework}' was not found in execution environment."],
                failure_classification="RUNNER_UNAVAILABLE",
                execution_status="UNAVAILABLE",
                is_targeted=is_targeted,
                selected_test_files=selected_files or [],
                diagnostic_warning=f"Execution environment does not have '{framework}' installed. Install the necessary package or runtime to run tests.",
                peak_memory_rss_bytes=peak_memory_rss_bytes,
                peak_memory_rss_mb=peak_memory_rss_mb,
                cpu_time_seconds=cpu_time_seconds,
                wall_time_seconds=wall_time_seconds,
                memory_limit_bytes=memory_limit_bytes,
                memory_limit_mb=memory_limit_mb,
                cpu_limit=cpu_limit,
                oom_killed=False,
                termination_reason=termination_reason,
                exit_classification="COMMAND_NOT_FOUND",
                resource_telemetry_available=resource_telemetry_available,
            )

        # 3. Detect command not executable (exit 126)
        if exit_classification == "COMMAND_NOT_EXECUTABLE" or exit_code == 126:
            return NormalizedTestResult(
                framework=framework,
                command=command,
                exit_code=exit_code,
                passed=False,
                total_tests=0,
                passed_tests=0,
                failed_tests=0,
                skipped_tests=0,
                duration_seconds=duration_seconds,
                raw_stdout=stdout,
                raw_stderr=stderr,
                failure_details=[f"Test command for '{framework}' was found but cannot be executed (Permission denied or invalid format)."],
                failure_classification="COMMAND_NOT_EXECUTABLE",
                execution_status="UNAVAILABLE",
                is_targeted=is_targeted,
                selected_test_files=selected_files or [],
                diagnostic_warning=f"Command '{command}' is not executable. Verify file permissions.",
                peak_memory_rss_bytes=peak_memory_rss_bytes,
                peak_memory_rss_mb=peak_memory_rss_mb,
                cpu_time_seconds=cpu_time_seconds,
                wall_time_seconds=wall_time_seconds,
                memory_limit_bytes=memory_limit_bytes,
                memory_limit_mb=memory_limit_mb,
                cpu_limit=cpu_limit,
                oom_killed=False,
                termination_reason=termination_reason,
                exit_classification="COMMAND_NOT_EXECUTABLE",
                resource_telemetry_available=resource_telemetry_available,
            )

        # 4. Detect execution timeouts
        if exit_classification == "TIMEOUT" or exit_code in (-1, 124) or "timed out" in combined.lower():
            return NormalizedTestResult(
                framework=framework,
                command=command,
                exit_code=exit_code,
                passed=False,
                total_tests=0,
                passed_tests=0,
                failed_tests=1,
                skipped_tests=0,
                duration_seconds=duration_seconds,
                raw_stdout=stdout,
                raw_stderr=stderr,
                failure_details=[termination_reason or "Execution timed out."],
                failure_classification="TIMEOUT",
                execution_status="TIMED_OUT",
                is_targeted=is_targeted,
                selected_test_files=selected_files or [],
                diagnostic_warning="Test execution exceeded the allowed timeout threshold.",
                peak_memory_rss_bytes=peak_memory_rss_bytes,
                peak_memory_rss_mb=peak_memory_rss_mb,
                cpu_time_seconds=cpu_time_seconds,
                wall_time_seconds=wall_time_seconds,
                memory_limit_bytes=memory_limit_bytes,
                memory_limit_mb=memory_limit_mb,
                cpu_limit=cpu_limit,
                oom_killed=False,
                termination_reason=termination_reason or "Execution timeout expired",
                exit_classification="TIMEOUT",
                resource_telemetry_available=resource_telemetry_available,
            )

        # 5. Detect forced process killed (SIGKILL without OOM)
        if exit_classification == "PROCESS_KILLED" or (exit_code in (137, -9) and not oom_killed):
            return NormalizedTestResult(
                framework=framework,
                command=command,
                exit_code=exit_code,
                passed=False,
                total_tests=0,
                passed_tests=0,
                failed_tests=1,
                skipped_tests=0,
                duration_seconds=duration_seconds,
                raw_stdout=stdout,
                raw_stderr=stderr,
                failure_details=[termination_reason or "Process was killed by external signal (SIGKILL)."],
                failure_classification="PROCESS_KILLED",
                execution_status="FAILED",
                is_targeted=is_targeted,
                selected_test_files=selected_files or [],
                diagnostic_warning="Process was killed with SIGKILL. Root cause may be external container limits or manual cancellation.",
                peak_memory_rss_bytes=peak_memory_rss_bytes,
                peak_memory_rss_mb=peak_memory_rss_mb,
                cpu_time_seconds=cpu_time_seconds,
                wall_time_seconds=wall_time_seconds,
                memory_limit_bytes=memory_limit_bytes,
                memory_limit_mb=memory_limit_mb,
                cpu_limit=cpu_limit,
                oom_killed=False,
                termination_reason=termination_reason or "Process killed (SIGKILL)",
                exit_classification="PROCESS_KILLED",
                resource_telemetry_available=resource_telemetry_available,
            )

        # 3. Detect missing dependencies
        missing_dep = None
        if "modulenotfounderror:" in combined.lower():
            m = re.search(r"ModuleNotFoundError:\s+No module named\s+'([^']+)'", combined, re.IGNORECASE)
            missing_dep = m.group(1) if m else "python module"
        elif "cannot find module" in combined.lower():
            m = re.search(r"Cannot find module\s+'([^']+)'", combined, re.IGNORECASE)
            missing_dep = m.group(1) if m else "npm package"

        total_tests = 0
        passed_tests = 0
        failed_tests = 0
        skipped_tests = 0
        failure_details: List[str] = []

        # ----------------- Framework Specific Parsing -----------------
        if framework in ("pytest", "python"):
            pass_m = re.search(r"(\d+)\s+passed", stdout)
            fail_m = re.search(r"(\d+)\s+failed", stdout)
            skip_m = re.search(r"(\d+)\s+skipped", stdout)
            err_m = re.search(r"(\d+)\s+error", stdout)

            if pass_m:
                passed_tests = int(pass_m.group(1))
            if fail_m:
                failed_tests = int(fail_m.group(1))
            if skip_m:
                skipped_tests = int(skip_m.group(1))
            if err_m:
                failed_tests += int(err_m.group(1))

            total_tests = passed_tests + failed_tests + skipped_tests

            for line in stdout.splitlines():
                if line.startswith("FAILED ") or line.startswith("ERROR "):
                    failure_details.append(line.strip())

        elif framework == "unittest":
            ran_m = re.search(r"Ran\s+(\d+)\s+test[s]?\s+in", combined)
            if ran_m:
                total_tests = int(ran_m.group(1))

            fail_m = re.search(r"failures=(\d+)", combined)
            err_m = re.search(r"errors=(\d+)", combined)
            skip_m = re.search(r"skipped=(\d+)", combined)

            if fail_m:
                failed_tests += int(fail_m.group(1))
            if err_m:
                failed_tests += int(err_m.group(1))
            if skip_m:
                skipped_tests = int(skip_m.group(1))

            if exit_code == 0 and "OK" in combined:
                passed_tests = total_tests - skipped_tests
            else:
                passed_tests = max(0, total_tests - failed_tests - skipped_tests)

            for line in combined.splitlines():
                if line.startswith("FAIL: ") or line.startswith("ERROR: "):
                    failure_details.append(line.strip())

        elif framework in ("jest", "vitest", "npm test"):
            # Format: Tests:       1 failed, 2 passed, 3 total
            # or:      Tests:  3 passed, 3 total
            pass_m = re.search(r"(\d+)\s+passed", stdout)
            fail_m = re.search(r"(\d+)\s+failed", stdout)
            skip_m = re.search(r"(\d+)\s+(?:skipped|todo)", stdout)
            tot_m = re.search(r"(\d+)\s+total", stdout)

            if pass_m:
                passed_tests = int(pass_m.group(1))
            if fail_m:
                failed_tests = int(fail_m.group(1))
            if skip_m:
                skipped_tests = int(skip_m.group(1))
            if tot_m:
                total_tests = int(tot_m.group(1))
            else:
                total_tests = passed_tests + failed_tests + skipped_tests

            for line in stdout.splitlines():
                if "● " in line or "FAIL " in line or "✕ " in line:
                    failure_details.append(line.strip())

        elif framework == "go test":
            # Go test line parsing
            for line in stdout.splitlines():
                if line.startswith("--- PASS:"):
                    passed_tests += 1
                elif line.startswith("--- FAIL:"):
                    failed_tests += 1
                    failure_details.append(line.strip())
                elif line.startswith("--- SKIP:"):
                    skipped_tests += 1

            total_tests = passed_tests + failed_tests + skipped_tests
            if total_tests == 0:
                if exit_code == 0 and "PASS" in stdout:
                    passed_tests = 1
                    total_tests = 1
                elif exit_code != 0 and "FAIL" in stdout:
                    failed_tests = 1
                    total_tests = 1

        elif framework == "cargo test":
            # Format: test result: ok. 5 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out
            res_m = re.search(
                r"test result:\s+(?:ok|FAILED)\.\s+(\d+)\s+passed;\s+(\d+)\s+failed;\s+(\d+)\s+ignored",
                stdout,
            )
            if res_m:
                passed_tests = int(res_m.group(1))
                failed_tests = int(res_m.group(2))
                skipped_tests = int(res_m.group(3))
                total_tests = passed_tests + failed_tests + skipped_tests
            else:
                for line in stdout.splitlines():
                    if " ... ok" in line:
                        passed_tests += 1
                    elif " ... FAILED" in line:
                        failed_tests += 1
                        failure_details.append(line.strip())
                    elif " ... ignored" in line:
                        skipped_tests += 1
                total_tests = passed_tests + failed_tests + skipped_tests

        elif framework in ("maven test", "gradle test"):
            # Maven: Tests run: 5, Failures: 0, Errors: 0, Skipped: 0
            mvn_m = re.search(
                r"Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+),\s*Skipped:\s*(\d+)",
                stdout,
            )
            if mvn_m:
                total_tests = int(mvn_m.group(1))
                fails = int(mvn_m.group(2))
                errs = int(mvn_m.group(3))
                skipped_tests = int(mvn_m.group(4))
                failed_tests = fails + errs
                passed_tests = max(0, total_tests - failed_tests - skipped_tests)
            for line in stdout.splitlines():
                if "FAILURE!" in line or "ERROR!" in line:
                    failure_details.append(line.strip())

        # Fallback if counts could not be parsed but exit code was 0
        passed = (exit_code == 0)
        if total_tests == 0:
            if passed:
                total_tests = 1
                passed_tests = 1
            else:
                total_tests = 1
                failed_tests = 1

        failure_class = None
        warning = None
        if not passed:
            if missing_dep:
                failure_class = "MISSING_DEPENDENCY"
                warning = f"Missing dependency detected: '{missing_dep}'"
            elif exit_code in (-1, 124):
                failure_class = "TIMEOUT"
            else:
                failure_class = "ASSERTION_FAILURE"

        return NormalizedTestResult(
            framework=framework,
            command=command,
            exit_code=exit_code,
            passed=passed,
            total_tests=total_tests,
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            skipped_tests=skipped_tests,
            duration_seconds=duration_seconds,
            raw_stdout=stdout,
            raw_stderr=stderr,
            failure_details=failure_details[:15],
            failure_classification=failure_class,
            execution_status="PASSED" if passed else "FAILED",
            is_targeted=is_targeted,
            selected_test_files=selected_files or [],
            diagnostic_warning=warning,
            peak_memory_rss_bytes=peak_memory_rss_bytes,
            peak_memory_rss_mb=peak_memory_rss_mb,
            cpu_time_seconds=cpu_time_seconds,
            wall_time_seconds=wall_time_seconds,
            memory_limit_bytes=memory_limit_bytes,
            memory_limit_mb=memory_limit_mb,
            cpu_limit=cpu_limit,
            oom_killed=oom_killed,
            termination_reason=termination_reason,
            exit_classification=exit_classification or ("SUCCESS" if passed else "EXECUTION_FAILURE"),
            resource_telemetry_available=resource_telemetry_available,
        )
