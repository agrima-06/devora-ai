"""Unit tests for RepositoryScanner."""
import os
import tempfile
from pathlib import Path
import pytest
from app.services.scanner_service import RepositoryScanner


def test_scanner_basic_structure():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        # Create files
        (root / "main.py").write_text("print('hello world')\n")
        (root / "requirements.txt").write_text("fastapi==0.110.0\npytest==8.0.0\n")
        (root / "README.md").write_text("# Test Project\n")
        tests_dir = root / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_main.py").write_text("def test_dummy(): pass\n")

        scanner = RepositoryScanner()
        res = scanner.scan(root)

        assert res["total_files"] == 4
        assert res["primary_language"] == "Python"
        assert "FastAPI" in res["frameworks"]
        assert "Pytest" in res["frameworks"]
        assert any(f["file_path"] == "main.py" for f in res["files"])
        assert any(f["file_path"] == "requirements.txt" for f in res["files"])
        assert "tests" in res["test_directories"]


def test_scanner_ignores_sensitive_and_ignored_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        # Allowed file
        (root / "app.py").write_text("import sys\n")

        # Sensitive files
        (root / ".env").write_text("SECRET_KEY=supersecret\n")
        (root / ".env.production").write_text("DATABASE_URL=postgres://...\n")
        (root / "id_rsa").write_text("-----BEGIN RSA PRIVATE KEY-----\n")
        (root / "key.pem").write_text("CERTIFICATE DATA\n")

        # Ignored dirs
        git_dir = root / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("git config")

        node_dir = root / "node_modules" / "some_pkg"
        node_dir.mkdir(parents=True)
        (node_dir / "index.js").write_text("module.exports = {};")

        venv_dir = root / ".venv" / "bin"
        venv_dir.mkdir(parents=True)
        (venv_dir / "activate").write_text("#!/bin/sh")

        scanner = RepositoryScanner()
        res = scanner.scan(root)

        indexed_paths = [f["file_path"] for f in res["files"]]
        assert "app.py" in indexed_paths
        assert ".env" not in indexed_paths
        assert ".env.production" not in indexed_paths
        assert "id_rsa" not in indexed_paths
        assert "key.pem" not in indexed_paths
        assert not any("node_modules" in p for p in indexed_paths)
        assert not any(".git" in p for p in indexed_paths)
        assert not any(".venv" in p for p in indexed_paths)


def test_scanner_respects_gitignore():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "src").mkdir()
        (root / "src" / "index.ts").write_text("console.log('hi');")
        (root / "temp_log.txt").write_text("log data")
        (root / "build_output.js").write_text("var x = 1;")
        (root / ".gitignore").write_text("*.txt\nbuild_output.js\n")

        scanner = RepositoryScanner()
        res = scanner.scan(root)

        indexed_paths = [f["file_path"] for f in res["files"]]
        assert "src/index.ts" in indexed_paths
        assert "temp_log.txt" not in indexed_paths
        assert "build_output.js" not in indexed_paths


def test_scanner_detects_typescript_and_react():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "package.json").write_text('{"dependencies": {"react": "^18.0.0", "next": "^14.0.0"}}\n')
        (root / "app.tsx").write_text("export default function App() { return <div>App</div>; }\n")

        scanner = RepositoryScanner()
        res = scanner.scan(root)

        assert any("TypeScript" in lang for lang in res["language_breakdown"])
        assert "React" in res["frameworks"]
        assert "Next.js" in res["frameworks"]
