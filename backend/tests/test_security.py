import time

import pytest

from app.core.security import (
    TokenError,
    create_access_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)


def test_password_roundtrip():
    stored = hash_password("Passw0rd!")
    assert stored.startswith("scrypt$")
    assert verify_password("Passw0rd!", stored)


def test_password_rejects_wrong_value():
    stored = hash_password("Passw0rd!")
    assert not verify_password("Passw0rd?", stored)
    assert not verify_password("", stored)


def test_salt_is_random_per_hash():
    assert hash_password("same") != hash_password("same")


def test_verify_rejects_malformed_hash():
    assert not verify_password("x", "not-a-hash")
    assert not verify_password("x", "")
    assert not verify_password("x", "scrypt$16384$8$1$onlyfourfields")


def test_hash_token_is_deterministic_and_not_the_input():
    token = "abc123"
    assert hash_token(token) == hash_token(token)
    assert hash_token(token) != token
    assert len(hash_token(token)) == 64


def test_access_token_roundtrip():
    token, expires_at = create_access_token("user-1", "zhangsan", ["admin"])
    assert expires_at.timestamp() > time.time()
    claims = decode_token(token, expected_type="access")
    assert claims["sub"] == "user-1"
    assert claims["username"] == "zhangsan"
    assert claims["roles"] == ["admin"]


def test_decode_rejects_wrong_token_type():
    token, _ = create_access_token("user-1", "zhangsan", [])
    with pytest.raises(TokenError):
        decode_token(token, expected_type="refresh")


def test_decode_rejects_tampered_signature():
    token, _ = create_access_token("user-1", "zhangsan", [])
    header, payload, signature = token.split(".")
    with pytest.raises(TokenError):
        decode_token(f"{header}.{payload}.{signature[:-2]}xx", expected_type="access")


def test_decode_rejects_garbage():
    with pytest.raises(TokenError):
        decode_token("not.a.jwt", expected_type="access")


def test_expired_token_is_rejected(monkeypatch):
    from app.core import security

    monkeypatch.setattr(security.settings, "jwt_access_ttl_minutes", -1)
    token, _ = create_access_token("user-1", "zhangsan", [])
    with pytest.raises(TokenError):
        decode_token(token, expected_type="access")
