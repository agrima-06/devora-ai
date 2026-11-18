"""Unit tests for security utilities (password hashing and JWT)."""
from datetime import timedelta
import pytest
from app.core.exceptions import UnauthorizedException
from app.core.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password,
)


def test_password_hashing():
    password = "SuperSecurePassword123!"
    hashed = get_password_hash(password)

    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword!", hashed) is False


def test_access_token_creation_and_decoding():
    subject = "123e4567-e89b-12d3-a456-426614174000"
    token = create_access_token(
        subject=subject,
        extra_claims={"role": "engineer"},
        expires_delta=timedelta(minutes=15),
    )

    payload = decode_access_token(token)
    assert payload["sub"] == subject
    assert payload["role"] == "engineer"
    assert "exp" in payload


def test_expired_token_rejection():
    subject = "123e4567-e89b-12d3-a456-426614174000"
    # Token that expired 5 minutes ago
    token = create_access_token(
        subject=subject,
        expires_delta=timedelta(minutes=-5),
    )

    with pytest.raises(UnauthorizedException) as exc_info:
        decode_access_token(token)
    assert "expired" in str(exc_info.value.message).lower()


def test_invalid_token_rejection():
    with pytest.raises(UnauthorizedException):
        decode_access_token("not-a-valid-token")
