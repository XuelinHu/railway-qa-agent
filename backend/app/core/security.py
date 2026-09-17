"""Password hashing and JWT helpers.

Password hashing uses the standard library's scrypt (RFC 7914) so the project
gains no compiled dependency for its most security-sensitive primitive. Hashes
are stored as a self-describing string, which leaves room to migrate to another
algorithm later without touching existing rows.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.core.config import settings

SCRYPT_ALGORITHM = "scrypt"
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 64
SALT_BYTES = 16

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


class TokenError(Exception):
    """Raised when a JWT is missing, malformed, expired or otherwise invalid."""


def _b64encode(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.b64decode(value.encode("ascii"))


def hash_password(password: str) -> str:
    """Return a self-describing scrypt hash: ``scrypt$n$r$p$salt$hash``."""
    if not password:
        raise ValueError("password must not be empty")

    salt = secrets.token_bytes(SALT_BYTES)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_DKLEN,
    )
    return "$".join(
        [
            SCRYPT_ALGORITHM,
            str(SCRYPT_N),
            str(SCRYPT_R),
            str(SCRYPT_P),
            _b64encode(salt),
            _b64encode(derived),
        ]
    )


def verify_password(password: str, stored: str | None) -> bool:
    """Constant-time verification of a password against a stored hash."""
    if not password or not stored:
        return False

    parts = stored.split("$")
    if len(parts) != 6 or parts[0] != SCRYPT_ALGORITHM:
        return False

    _, raw_n, raw_r, raw_p, raw_salt, raw_hash = parts
    try:
        n, r, p = int(raw_n), int(raw_r), int(raw_p)
        salt = _b64decode(raw_salt)
        expected = _b64decode(raw_hash)
    except (ValueError, TypeError):
        return False

    try:
        derived = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=n,
            r=r,
            p=p,
            dklen=len(expected),
        )
    except ValueError:
        return False

    return hmac.compare_digest(derived, expected)


def generate_opaque_token() -> str:
    """A high-entropy token for refresh / password reset flows."""
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    """Refresh and reset tokens are stored hashed, never in plaintext."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _create_token(
    subject: str,
    token_type: str,
    expires_delta: timedelta,
    extra_claims: dict[str, Any] | None = None,
) -> tuple[str, datetime]:
    now = datetime.now(UTC)
    expires_at = now + expires_delta
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": uuid.uuid4().hex,
    }
    if extra_claims:
        payload.update(extra_claims)

    encoded = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return encoded, expires_at


def create_access_token(
    user_id: uuid.UUID | str,
    username: str,
    roles: list[str] | None = None,
) -> tuple[str, datetime]:
    return _create_token(
        subject=str(user_id),
        token_type=ACCESS_TOKEN_TYPE,
        expires_delta=timedelta(minutes=settings.jwt_access_ttl_minutes),
        extra_claims={"username": username, "roles": roles or []},
    )


def create_refresh_token(user_id: uuid.UUID | str) -> tuple[str, datetime]:
    return _create_token(
        subject=str(user_id),
        token_type=REFRESH_TOKEN_TYPE,
        expires_delta=timedelta(days=settings.jwt_refresh_ttl_days),
    )


def decode_token(token: str, expected_type: str | None = None) -> dict[str, Any]:
    """Decode and validate a JWT, raising :class:`TokenError` on any problem."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("登录状态已过期，请重新登录") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("登录凭证无效") from exc

    if expected_type is not None and payload.get("type") != expected_type:
        raise TokenError("登录凭证类型不匹配")

    return payload


def access_token_expires_in() -> int:
    return settings.jwt_access_ttl_minutes * 60
