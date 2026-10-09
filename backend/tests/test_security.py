import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import Base, engine
from backend.models import User
from backend.rate_limiter import rate_limiter
import os

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    rate_limiter.requests.clear()
    yield


def test_password_complexity_enforcement():
    # Attempt registering with weak password (missing uppercase)
    res_no_upper = client.post(
        "/api/auth/register",
        json={
            "full_name": "Test User",
            "email": "test1@example.com",
            "password": "password123"
        }
    )
    assert res_no_upper.status_code == 422

    # Attempt registering with weak password (missing digit)
    res_no_digit = client.post(
        "/api/auth/register",
        json={
            "full_name": "Test User",
            "email": "test2@example.com",
            "password": "PasswordOnly"
        }
    )
    assert res_no_digit.status_code == 422

    # Attempt registering with short password (< 8 chars)
    res_short = client.post(
        "/api/auth/register",
        json={
            "full_name": "Test User",
            "email": "test3@example.com",
            "password": "Pass1"
        }
    )
    assert res_short.status_code == 422

    # Valid strong password succeeds
    res_valid = client.post(
        "/api/auth/register",
        json={
            "full_name": "Test User",
            "email": "test4@example.com",
            "password": "SecurePassword123!"
        }
    )
    assert res_valid.status_code == 201


def test_xss_input_sanitization():
    reg = client.post(
        "/api/auth/register",
        json={
            "full_name": "XSS Tester",
            "email": "xsstester@example.com",
            "password": "SecurePassword123!"
        }
    )
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Attempt injecting malicious XSS script payload in expense description
    res = client.post(
        "/api/expenses",
        headers=headers,
        json={
            "amount": 250.0,
            "category": "Food & Dining",
            "date": "2026-10-09",
            "description": "<script>alert('pwned')</script>Canteen lunch",
            "receipt_note": "<iframe src='evil.com'></iframe>Receipt #123"
        }
    )
    assert res.status_code == 201
    data = res.json()
    # Malicious script and iframe tags must be completely stripped out
    assert "<script>" not in data["description"]
    assert "alert('pwned')" not in data["description"]
    assert "Canteen lunch" in data["description"]
    assert "<iframe>" not in data["receipt_note"]
    assert "Receipt #123" in data["receipt_note"]


def test_admin_route_protection_and_rbac():
    # Register standard non-admin user
    reg_user = client.post(
        "/api/auth/register",
        json={
            "full_name": "Normal User",
            "email": "normal@example.com",
            "password": "SecurePassword123!"
        }
    )
    user_token = reg_user.json()["access_token"]
    user_headers = {"Authorization": f"Bearer {user_token}"}

    # Regular user attempting to access admin endpoints must receive 403 Forbidden
    res_stats = client.get("/api/admin/stats", headers=user_headers)
    assert res_stats.status_code == 403
    assert "Administrator access required" in res_stats.json()["detail"]

    res_users = client.get("/api/admin/users", headers=user_headers)
    assert res_users.status_code == 403

    res_health = client.get("/api/admin/system-health", headers=user_headers)
    assert res_health.status_code == 403

    # Attempt registering admin with invalid key -> 403
    res_bad_admin = client.post(
        "/api/auth/register",
        json={
            "full_name": "Fake Admin",
            "email": "fakeadmin@example.com",
            "password": "SecurePassword123!",
            "admin_secret": "wrong_key_123"
        }
    )
    assert res_bad_admin.status_code == 403

    # Register admin with correct admin registration key
    admin_key = os.getenv("ADMIN_REGISTRATION_KEY")
    if not admin_key:
        # Set for test
        os.environ["ADMIN_REGISTRATION_KEY"] = "test_admin_key_abc"
        admin_key = "test_admin_key_abc"

    reg_admin = client.post(
        "/api/auth/register",
        json={
            "full_name": "Verified Admin",
            "email": "admin@example.com",
            "password": "SecurePassword123!",
            "admin_secret": admin_key
        }
    )
    assert reg_admin.status_code == 201
    assert reg_admin.json()["user"]["is_admin"] is True

    admin_token = reg_admin.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Authorized admin can access admin endpoints
    stats_ok = client.get("/api/admin/stats", headers=admin_headers)
    assert stats_ok.status_code == 200
    assert stats_ok.json()["total_users"] >= 2
    assert stats_ok.json()["admin_users"] >= 1

    users_ok = client.get("/api/admin/users", headers=admin_headers)
    assert users_ok.status_code == 200
    assert len(users_ok.json()) >= 2

    health_ok = client.get("/api/admin/system-health", headers=admin_headers)
    assert health_ok.status_code == 200
    assert health_ok.json()["status"] == "operational"


def test_security_headers_present():
    res = client.get("/")
    assert res.status_code == 200
    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["x-frame-options"] == "DENY"
    assert res.headers["x-xss-protection"] == "1; mode=block"
    assert "strict-origin-when-cross-origin" in res.headers["referrer-policy"]
    assert "default-src 'self'" in res.headers["content-security-policy"]
    assert "camera=()" in res.headers["permissions-policy"]


def test_deactivated_user_cannot_login():
    admin_key = os.getenv("ADMIN_REGISTRATION_KEY") or "test_admin_key_abc"
    os.environ["ADMIN_REGISTRATION_KEY"] = admin_key

    reg_admin = client.post(
        "/api/auth/register",
        json={
            "full_name": "Admin Owner",
            "email": "owner@example.com",
            "password": "SecurePassword123!",
            "admin_secret": admin_key
        }
    )
    admin_token = reg_admin.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    reg_user = client.post(
        "/api/auth/register",
        json={
            "full_name": "Bad Actor",
            "email": "badactor@example.com",
            "password": "SecurePassword123!"
        }
    )
    user_id = reg_user.json()["user"]["id"]

    # Admin deactivates bad actor
    deact_res = client.put(
        f"/api/admin/users/{user_id}/toggle-status",
        headers=admin_headers,
        json={"is_active": False}
    )
    assert deact_res.status_code == 200
    assert deact_res.json()["is_active"] is False

    # Deactivated user attempts login -> 403 Forbidden
    login_attempt = client.post(
        "/api/auth/login",
        json={
            "username": "badactor@example.com",
            "password": "SecurePassword123!"
        }
    )
    assert login_attempt.status_code == 403
    assert "deactivated" in login_attempt.json()["detail"].lower()


def test_rate_limiting_blocks_brute_force():
    # Exhaust auth rate limit (10 requests per minute)
    for i in range(10):
        res = client.post(
            "/api/auth/login",
            json={"username": f"user_{i}@test.com", "password": "WrongPassword1!"}
        )
        assert res.status_code == 401

    # 11th attempt must be blocked by rate limiter with 429
    blocked = client.post(
        "/api/auth/login",
        json={"username": "user_blocked@test.com", "password": "WrongPassword1!"}
    )
    assert blocked.status_code == 429
    assert "Rate limit exceeded" in blocked.json()["detail"]
    assert "Retry-After" in blocked.headers


def test_sensitive_files_not_exposed():
    # Attempting to access database or environment files via web must return 404
    assert client.get("/expense_tracker.db").status_code == 404
    assert client.get("/.env").status_code == 404
    assert client.get("/.env.example").status_code == 404
    assert client.get("/backend/auth.py").status_code == 404
    assert client.get("/static/../expense_tracker.db").status_code == 404


