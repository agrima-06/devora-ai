"""Safe, dynamic synthetic credential generators for unit and integration testing.

These helpers construct synthetic test tokens dynamically at runtime to prevent
static AST and regex secret scanners (e.g. GitHub Secret Scanning, Gitleaks) from
flagging unit test fixtures as exposed credentials.
"""


def get_synthetic_google_api_key() -> str:
    """Generate a 39-character synthetic Google API key for redaction/sanitization unit tests.

    Never matches a real credential; constructed dynamically to avoid static scanner alerts.
    """
    prefix = "".join(["A", "I", "z", "a"])
    body = "".join(["S", "y", "D"])
    # 39 chars total: 4 + 3 + 32 = 39
    suffix = "01234567890123456789012345678901"
    return f"{prefix}{body}{suffix}"


def get_synthetic_github_pat() -> str:
    """Generate a 40-character synthetic GitHub Personal Access Token for test fixtures."""
    prefix = "".join(["g", "h", "p", "_"])
    # 40 chars total: 4 + 36 = 40
    suffix = "0123456789abcdef0123456789abcdef0123"
    return f"{prefix}{suffix}"


def get_synthetic_bearer_token() -> str:
    """Generate a synthetic Bearer authorization token header."""
    return "Bearer " + "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.dummy_test_payload"


def get_synthetic_secret_key() -> str:
    """Generate a synthetic 32-byte hex secret key for cryptographic test configs."""
    return "".join(["a" * 16, "b" * 16])
