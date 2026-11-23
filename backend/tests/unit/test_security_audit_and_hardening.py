"""Unit tests for security audit, credential hygiene, and secret scanning."""

import os
import sys
import tempfile
from pathlib import Path
import pytest

from tests.fixtures.synthetic_credentials import (
    get_synthetic_google_api_key,
    get_synthetic_github_pat,
    get_synthetic_bearer_token,
    get_synthetic_secret_key,
)

# Add scripts directory to sys.path
scripts_dir = Path(__file__).resolve().parents[2] / "scripts"
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))

from security_scanner import scan_file, scan_repository, SECRET_PATTERNS


def test_synthetic_credentials_generator():
    """Verify synthetic credentials generate valid strings for redaction tests."""
    google_key = get_synthetic_google_api_key()
    assert google_key.startswith("AIza")
    assert len(google_key) == 39

    pat = get_synthetic_github_pat()
    assert pat.startswith("ghp_")
    assert len(pat) == 40

    token = get_synthetic_bearer_token()
    assert len(token) >= 32

    secret_key = get_synthetic_secret_key()
    assert len(secret_key) >= 32


def test_scanner_clean_repo():
    """Verify that the Devora AI repository passes the security scan with zero findings."""
    root_dir = Path(__file__).resolve().parents[3]
    findings = scan_repository(root_dir)
    assert len(findings) == 0, f"Detected unexpected secret exposures in repository: {findings}"


def test_scanner_detects_secrets_in_temp_file():
    """Verify that the scanner accurately flags known secret patterns with redaction."""
    # Construct a dummy string dynamically so static scanners do not flag this test file
    dummy_key = "".join(["A", "I", "z", "a", "S", "y"]) + ("X" * 33)

    with tempfile.NamedTemporaryFile("w+", suffix=".py", delete=False) as f:
        f.write(f'MOCK_API_KEY = "{dummy_key}"\n')
        temp_path = f.name

    try:
        findings = scan_file(Path(temp_path))
        assert len(findings) == 1
        category, line_num, _ = findings[0]
        assert "Google API Key" in category
        assert line_num == 1
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def test_secret_patterns_coverage():
    """Ensure scanner covers critical credential providers."""
    names = list(SECRET_PATTERNS.keys())
    assert any("Google API Key" in n for n in names)
    assert any("GitHub Personal Access Token" in n for n in names)
    assert any("OpenAI" in n for n in names)
    assert any("Slack Token" in n for n in names)
    assert any("Database Connection" in n for n in names)
    assert any("Private" in n and "Key" in n for n in names)
