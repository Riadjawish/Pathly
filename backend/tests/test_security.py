from uuid import uuid4

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)


def test_password_hash_and_verify() -> None:
    encoded = hash_password("very-secure-password")
    assert encoded != "very-secure-password"
    assert verify_password("very-secure-password", encoded)
    assert not verify_password("wrong-password", encoded)


def test_access_token_round_trip() -> None:
    user_id = uuid4()
    payload = decode_access_token(create_access_token(user_id))
    assert payload["sub"] == str(user_id)
    assert payload["typ"] == "access"


def test_refresh_tokens_are_stored_as_hashes() -> None:
    raw = "a" * 48
    assert hash_refresh_token(raw) != raw
    assert hash_refresh_token(raw) == hash_refresh_token(raw)
