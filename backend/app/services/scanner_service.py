"""Repository scanner: file tree inspection, ecosystem identification, and sensitivity filtering."""
import fnmatch
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from app.core.logging import get_logger

logger = get_logger("scanner_service")

# Default ignore directories
IGNORED_DIRECTORIES: Set[str] = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "env",
    "vendor",
    "dist",
    "build",
    "__pycache__",
    ".next",
    ".turbo",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".coverage",
    "coverage",
    "target",
    "bin",
    "obj",
}

# Sensitive file patterns to block unconditionally
SENSITIVE_FILE_PATTERNS: List[str] = [
    "*.env",
    "*.env.*",
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "id_rsa",
    "id_rsa.*",
    "id_ed25519",
    "id_ed25519.*",
    "*.keystore",
    "credentials.json",
    "service_account.json",
    "*.secret",
]

# Binary file extensions
BINARY_EXTENSIONS: Set[str] = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp",
    ".pdf", ".zip", ".tar", ".gz", ".7z", ".rar",
    ".exe", ".bin", ".dll", ".so", ".dylib",
    ".class", ".pyc", ".pyo", ".jar", ".war",
    ".woff", ".woff2", ".ttf", ".eot",
    ".mp3", ".mp4", ".mov", ".avi",
    ".sqlite", ".db",
}

# Language file extensions mapping
LANGUAGE_EXTENSIONS: Dict[str, str] = {
    ".py": "Python",
    ".ts": "TypeScript",
    ".tsx": "TypeScript (React)",
    ".js": "JavaScript",
    ".jsx": "JavaScript (React)",
    ".go": "Go",
    ".java": "Java",
    ".php": "PHP",
    ".rb": "Ruby",
    ".rs": "Rust",
    ".cs": "C#",
    ".cpp": "C++",
    ".c": "C",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sql": "SQL",
    ".sh": "Shell",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".xml": "XML",
    ".md": "Markdown",
}


class RepositoryScanner:
    """Scans and extracts structural and architectural metadata from a repository."""

    def __init__(
        self,
        max_file_size_bytes: int = 1_500_000,  # 1.5 MB max per file
        max_total_files: int = 5_000,
    ):
        self.max_file_size_bytes = max_file_size_bytes
        self.max_total_files = max_total_files

    def parse_gitignore(self, repo_dir: Path) -> List[str]:
        """Read .gitignore rules if present in the repository root."""
        gitignore_path = repo_dir / ".gitignore"
        patterns = []
        if gitignore_path.exists() and gitignore_path.is_file():
            try:
                with open(gitignore_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            patterns.append(line)
            except Exception as e:
                logger.warning("failed_to_read_gitignore", error=str(e))
        return patterns

    def is_ignored(self, rel_path: str, filename: str, gitignore_patterns: List[str]) -> bool:
        """Check if file or path matches default ignores, sensitive patterns, or gitignore."""
        # 1. Check directory path components
        parts = rel_path.split(os.sep)
        for part in parts:
            if part in IGNORED_DIRECTORIES:
                return True

        # 2. Check sensitive patterns
        for pattern in SENSITIVE_FILE_PATTERNS:
            if fnmatch.fnmatch(filename, pattern):
                return True

        # 3. Check binary extensions
        ext = os.path.splitext(filename)[1].lower()
        if ext in BINARY_EXTENSIONS:
            return True

        # 4. Check gitignore patterns
        for pattern in gitignore_patterns:
            clean_pat = pattern.rstrip("/")
            if fnmatch.fnmatch(rel_path, clean_pat) or fnmatch.fnmatch(filename, clean_pat):
                return True

        return False

    def scan(self, repo_path: Path) -> Dict[str, Any]:
        """Perform a complete scan of the repository filesystem."""
        if not repo_path.exists() or not repo_path.is_dir():
            raise ValueError(f"Path does not exist or is not a directory: {repo_path}")

        gitignore_patterns = self.parse_gitignore(repo_path)

        indexed_files: List[Dict[str, Any]] = []
        language_counts: Dict[str, int] = {}
        language_bytes: Dict[str, int] = {}
        manifests_found: List[str] = []
        test_dirs: Set[str] = set()
        configs_found: List[str] = []
        entry_points: List[str] = []
        total_lines = 0

        for root, dirs, files in os.walk(repo_path):
            # Prune ignored directories in-place
            dirs[:] = [
                d
                for d in dirs
                if d not in IGNORED_DIRECTORIES and not any(fnmatch.fnmatch(d, p.rstrip("/")) for p in gitignore_patterns)
            ]

            rel_root = os.path.relpath(root, repo_path)
            if rel_root == ".":
                rel_root = ""

            # Check if current directory is a test directory
            dir_name = os.path.basename(root).lower()
            if dir_name in {"tests", "test", "__tests__", "spec"}:
                test_dirs.add(rel_root or dir_name)

            for file in files:
                rel_file_path = os.path.join(rel_root, file) if rel_root else file

                if self.is_ignored(rel_file_path, file, gitignore_patterns):
                    continue

                full_path = Path(root) / file
                try:
                    file_stat = full_path.stat()
                    file_size = file_stat.st_size

                    # Skip files exceeding maximum size
                    if file_size > self.max_file_size_bytes or file_size == 0:
                        continue

                    ext = os.path.splitext(file)[1].lower()
                    language = LANGUAGE_EXTENSIONS.get(ext)

                    # Count lines
                    lines_count = 0
                    try:
                        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                            lines_count = sum(1 for _ in f)
                    except Exception:
                        lines_count = 0

                    total_lines += lines_count

                    # Categorize file
                    category = "source"
                    if "test" in rel_file_path.lower():
                        category = "test"
                    elif ext in {".md", ".rst", ".txt"}:
                        category = "docs"
                    elif ext in {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".xml"}:
                        category = "config"

                    # Detect package manifests
                    if file in {
                        "package.json", "requirements.txt", "pyproject.toml",
                        "Pipfile", "go.mod", "pom.xml", "build.gradle",
                        "composer.json", "Cargo.toml", "Gemfile"
                    }:
                        manifests_found.append(rel_file_path)

                    # Detect configs
                    if file in {
                        "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
                        "tsconfig.json", "alembic.ini", "pytest.ini",
                        "setup.py", "Makefile", "webpack.config.js"
                    }:
                        configs_found.append(rel_file_path)

                    # Detect potential entry points
                    if file in {
                        "main.py", "app.py", "wsgi.py", "asgi.py", "server.py",
                        "index.ts", "index.js", "server.ts", "server.js", "main.go"
                    }:
                        entry_points.append(rel_file_path)

                    if language:
                        language_counts[language] = language_counts.get(language, 0) + 1
                        language_bytes[language] = language_bytes.get(language, 0) + file_size

                    indexed_files.append({
                        "file_path": rel_file_path,
                        "language": language,
                        "size_bytes": file_size,
                        "lines_count": lines_count,
                        "category": category,
                    })

                    if len(indexed_files) >= self.max_total_files:
                        logger.warning("max_files_limit_reached", limit=self.max_total_files)
                        break

                except Exception as e:
                    logger.debug("failed_to_inspect_file", file=rel_file_path, error=str(e))

        # Detect primary language
        primary_language = "Unknown"
        if language_bytes:
            primary_language = max(language_bytes.items(), key=lambda item: item[1])[0]

        # Detect frameworks based on manifests and file signatures
        frameworks = self._detect_frameworks(repo_path, manifests_found, indexed_files)

        return {
            "primary_language": primary_language,
            "language_breakdown": language_counts,
            "total_files": len(indexed_files),
            "total_lines": total_lines,
            "manifests": manifests_found,
            "configs": configs_found,
            "entry_points": entry_points,
            "test_directories": list(test_dirs),
            "frameworks": frameworks,
            "files": indexed_files,
        }

    def _detect_frameworks(
        self,
        repo_path: Path,
        manifests: List[str],
        files: List[Dict[str, Any]],
    ) -> List[str]:
        """Identify frameworks based on dependency manifests and file content."""
        frameworks: Set[str] = set()

        # Check Python dependencies
        for manifest in manifests:
            full_path = repo_path / manifest
            if not full_path.exists():
                continue
            try:
                content = full_path.read_text(encoding="utf-8", errors="ignore").lower()
                if "fastapi" in content:
                    frameworks.add("FastAPI")
                if "django" in content:
                    frameworks.add("Django")
                if "flask" in content:
                    frameworks.add("Flask")
                if "next" in content or "next.js" in content:
                    frameworks.add("Next.js")
                if "react" in content:
                    frameworks.add("React")
                if "express" in content:
                    frameworks.add("Express")
                if "spring" in content:
                    frameworks.add("Spring Boot")
                if "laravel" in content:
                    frameworks.add("Laravel")
                if "gin" in content:
                    frameworks.add("Gin")
                if "pytest" in content:
                    frameworks.add("Pytest")
                if "jest" in content:
                    frameworks.add("Jest")
            except Exception:
                pass

        # Check directory signatures
        for f in files:
            p = f["file_path"].lower()
            if p.startswith("src/app") or p.startswith("pages/"):
                frameworks.add("Next.js")
            if "alembic" in p:
                frameworks.add("Alembic")
            if "tailwind" in p:
                frameworks.add("Tailwind CSS")

        return sorted(list(frameworks))
