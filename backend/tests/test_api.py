from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.main import app


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    async def override_db() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = override_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as value:
        yield value
    app.dependency_overrides.clear()


async def register(client: AsyncClient, email: str = "student@example.com") -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "correct-horse-battery-staple",
            "full_name": "Pathly Student",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_health(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


@pytest.mark.asyncio
async def test_register_login_refresh_and_profile(client: AsyncClient) -> None:
    tokens = await register(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    profile = await client.get("/api/v1/users/me", headers=headers)
    assert profile.status_code == 200
    assert profile.json()["email"] == "student@example.com"
    assert "xp" not in profile.json()

    progress = await client.get("/api/v1/progress/summary", headers=headers)
    assert progress.status_code == 200
    assert "xp" not in progress.json()
    assert progress.json()["subjects"] == []

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "student@example.com", "password": "correct-horse-battery-staple"},
    )
    assert login.status_code == 200
    refreshed = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": login.json()["refresh_token"]},
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["refresh_token"] != login.json()["refresh_token"]


@pytest.mark.asyncio
async def test_password_reset_flow(client: AsyncClient) -> None:
    await register(client, "reset@example.com")

    requested = await client.post(
        "/api/v1/auth/password-reset/request", json={"email": "reset@example.com"}
    )
    assert requested.status_code == 200

    outbox = await client.get("/api/v1/auth/dev-outbox", params={"email": "reset@example.com"})
    assert outbox.status_code == 200
    messages = outbox.json()
    assert messages
    token = messages[-1]["body"].rsplit("token=", 1)[1].strip()

    confirmed = await client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": token, "new_password": "brand-new-password-123"},
    )
    assert confirmed.status_code == 200

    old_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "reset@example.com", "password": "correct-horse-battery-staple"},
    )
    assert old_login.status_code == 401

    new_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "reset@example.com", "password": "brand-new-password-123"},
    )
    assert new_login.status_code == 200

    reused = await client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": token, "new_password": "another-password-456"},
    )
    assert reused.status_code == 400


@pytest.mark.asyncio
async def test_password_reset_request_for_unknown_email_is_generic(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/password-reset/request", json={"email": "nobody@example.com"}
    )
    assert response.status_code == 200

    outbox = await client.get("/api/v1/auth/dev-outbox", params={"email": "nobody@example.com"})
    assert outbox.json() == []


@pytest.mark.asyncio
async def test_email_verification_flow(client: AsyncClient) -> None:
    tokens = await register(client, "verify@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    profile = await client.get("/api/v1/users/me", headers=headers)
    assert profile.json()["email_verified"] is False

    outbox = await client.get("/api/v1/auth/dev-outbox", params={"email": "verify@example.com"})
    messages = outbox.json()
    assert messages
    token = messages[-1]["body"].rsplit("token=", 1)[1].strip()

    confirmed = await client.post("/api/v1/auth/verify-email/confirm", json={"token": token})
    assert confirmed.status_code == 200

    profile_after = await client.get("/api/v1/users/me", headers=headers)
    assert profile_after.json()["email_verified"] is True

    resend = await client.post("/api/v1/auth/verify-email/request", headers=headers)
    assert resend.status_code == 200
    assert resend.json()["message"] == "Your email is already verified"


@pytest.mark.asyncio
async def test_subject_crud_is_owned_by_current_user(client: AsyncClient) -> None:
    tokens = await register(client, "owner@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    created = await client.post(
        "/api/v1/subjects",
        headers=headers,
        json={
            "name": "Calculus",
            "short_name": "Math",
            "description": "Limits and integrals",
            "icon": "∑",
            "tone": "blue",
        },
    )
    assert created.status_code == 201, created.text
    subject_id = created.json()["id"]
    updated = await client.patch(
        f"/api/v1/subjects/{subject_id}",
        headers=headers,
        json={"name": "Calculus II", "tone": "indigo"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Calculus II"
    listed = await client.get("/api/v1/subjects", headers=headers)
    assert [item["id"] for item in listed.json()] == [subject_id]
    removed = await client.delete(f"/api/v1/subjects/{subject_id}", headers=headers)
    assert removed.status_code == 204
    missing = await client.get(f"/api/v1/subjects/{subject_id}", headers=headers)
    assert missing.status_code == 404
