#!/usr/bin/env python3
"""Repository-wide Secret and Credential Security Scanner.

Audits current tracked files and recent Git history for exposed high-entropy secrets,
tokens, API keys, and private keys.
Safe by design: NEVER logs, prints, or outputs matched secret values.

Exit Codes:
  0: Clean scan (no secret exposures detected in working tree)
  1: Secret exposures detected in tracked files
  2: Scanner runtime error or missing dependency
"""
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# Patterns to scan
SECRET_PATTERNS: Dict[str, re.Pattern] = {
    "Google API Key": re.compile(r"\bAIza[0-9A-Za-z-_]{35}\b"),
    "GitHub Personal Access Token": re.compile(r"\bghp_[a-zA-Z0-9]{36}\b"),
    "GitHub Fine-Grained Token": re.compile(r"\bgithub_pat_[a-zA-Z0-9_]{82}\b"),
    "AWS Access Key ID": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "OpenAI / Anthropic Secret Key": re.compile(r"\bsk-[a-zA-Z0-9]{20,}\b"),
    "Private Cryptographic Key": re.compile(r"-----BEGIN (?:RSA|EC|OPENSSH|PGP|DSA) PRIVATE KEY-----"),
    "Slack Token": re.compile(r"\bxox[baprs]-[0-9a-zA-Z]{10,}\b"),
    "Hardcoded Database Connection with Password": re.compile(r"postgres(?:ql)?://[a-zA-Z0-9_-]+:[^@\s/:]+@[a-zA-Z0-9.-]+"),
}

IGNORED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    ".next",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "build",
    ".turbo",
    ".cache",
    "artifacts",
}

IGNORED_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".ico",
    ".svg",
    ".woff",
    ".woff2",
    ".ttf",
    ".joblib",
    ".pyc",
    ".lock",
}

# Narrow allowlist strictly for documentation files discussing detection rules & security audits
DOCS_ALLOWLIST = {
    "docs/PHASE_8_GITHUB_NATIVE_ENGINEERING_PLAN.md",
    "docs/SECURITY.md",
    "docs/ARCHITECTURE.md",
    "docs/PHASE_9_STAGE_3_IMPLEMENTATION_REPORT.md",
    "docs/PHASE_9_STAGE_4_IMPLEMENTATION_REPORT.md",
    "docs/PHASE_9_STAGE_2_IMPLEMENTATION_REPORT.md",
    "docs/SECURITY_AUDIT_PHASE_10_STAGE_3.md",
    "docs/SECURITY_FOLLOWUP_PHASE_10_STAGE_4.md",
    "docs/PHASE_10_STAGE_4_IMPLEMENTATION_PLAN.md",
    "docs/PHASE_10_STAGE_4_IMPLEMENTATION_REPORT.md",
}


def scan_file(file_path: Path) -> List[Tuple[str, int, str]]:
    """Scan a single file for exposed secret patterns.

    Returns a list of (category, line_number, masked_snippet).
    """
    path_obj = Path(file_path)
    if not path_obj.is_file():
        return []

    try:
        content = path_obj.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:
        sys.stderr.write(f"Warning: Failed to read {file_path}: {exc}\n")
        return []

    findings = []
    lines = content.splitlines()
    for line_no, line in enumerate(lines, start=1):
        for category, pattern in SECRET_PATTERNS.items():
            if pattern.search(line):
                # Never return secret value; only masked snippet
                findings.append((category, line_no, "***[REDACTED]***"))
    return findings


def scan_repository(repo_root: Path) -> List[Tuple[str, int, str]]:
    """Scan all tracked and source files in the repository.

    Returns a list of (file_path, line_number, secret_category).
    """
    repo_root = Path(repo_root)
    if not repo_root.is_dir():
        raise FileNotFoundError(f"Repository path does not exist: {repo_root}")

    findings = []

    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
        rel_root = Path(root).relative_to(repo_root)

        for f in files:
            file_path = rel_root / f
            posix_path = file_path.as_posix()

            if file_path.suffix.lower() in IGNORED_EXTENSIONS:
                continue

            if posix_path in DOCS_ALLOWLIST:
                continue

            # Ignore dynamic synthetic credentials builder itself
            if "synthetic_credentials.py" in posix_path:
                continue

            # Ignore unit test testing the scanner itself
            if "test_security_audit_and_hardening.py" in posix_path:
                continue

            full_path = repo_root / file_path
            file_findings = scan_file(full_path)
            for category, line_no, _ in file_findings:
                findings.append((posix_path, line_no, category))

    return findings


def scan_git_history(repo_root: Path, max_commits: int = 50) -> List[Tuple[str, str, str]]:
    """Scan recent git commit diffs for additions that match secret patterns.

    Returns a list of (commit_hash, file_path, category).
    """
    repo_root = Path(repo_root)
    git_dir = repo_root / ".git"
    if not git_dir.exists():
        return []

    try:
        cmd = ["git", "log", "-p", f"-n{max_commits}", "--no-merges", "--unified=0"]
        res = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True, check=True)
    except Exception as exc:
        sys.stderr.write(f"Warning: Git history scan failed: {exc}\n")
        return []

    history_findings = []
    current_commit = "UNKNOWN"
    current_file = "UNKNOWN"

    for line in res.stdout.splitlines():
        if line.startswith("commit "):
            current_commit = line.split()[1][:8]
        elif line.startswith("+++ b/"):
            current_file = line[6:]
        elif line.startswith("+") and not line.startswith("+++"):
            if current_file in DOCS_ALLOWLIST or "synthetic_credentials.py" in current_file:
                continue
            added_content = line[1:]
            for category, pattern in SECRET_PATTERNS.items():
                if pattern.search(added_content):
                    history_findings.append((current_commit, current_file, category))
                    break

    return history_findings


def main():
    parser = argparse.ArgumentParser(description="Devora AI Secret Security Scanner")
    parser.add_argument("--repo-root", default=None, help="Root path of repository to scan")
    parser.add_argument("--scan-history", action="store_true", help="Also scan recent git commit history")
    parser.add_argument("--max-commits", type=int, default=30, help="Number of historical commits to inspect")
    parser.add_argument("--fail-on-detected", action="store_true", help="Exit code 1 if any leak found")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path(__file__).resolve().parent.parent.parent

    try:
        print(f"Scanning repository working tree at: {repo_root}")
        findings = scan_repository(repo_root)
    except Exception as exc:
        print(f"\n[ERROR] Scanner failed to execute: {exc}", file=sys.stderr)
        sys.exit(2)

    has_working_tree_findings = len(findings) > 0

    if has_working_tree_findings:
        print(f"\n[FAILED] {len(findings)} potential secret exposure(s) detected in current working tree:")
        for path, line, category in findings:
            print(f"  - {path}:{line} [{category}] (Value: ***[REDACTED]***)")
        print("\nAction required: Remove all static credentials and replace with safe dynamic fixtures or environment variables.")
    else:
        print("\n[PASSED] No exposed secrets or credentials detected across current repository source files.")

    if args.scan_history:
        print(f"\nScanning last {args.max_commits} Git commits for historical secret additions...")
        hist_findings = scan_git_history(repo_root, max_commits=args.max_commits)
        if hist_findings:
            print(f"[ALERT] {len(hist_findings)} secret pattern(s) identified in historical git commits:")
            for commit_id, file_path, category in hist_findings:
                print(f"  - Commit {commit_id} in {file_path} [{category}] (Value: ***[REDACTED]***)")
            print("Note: If these were synthetic test fixtures, ensure GitHub Secret Scanning alert is marked as False Positive / Test Fixture.")
        else:
            print("[PASSED] No exposed secrets found in scanned git commit history.")

    if has_working_tree_findings:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
