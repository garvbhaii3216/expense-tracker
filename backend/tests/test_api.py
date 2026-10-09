import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import Base, engine, SessionLocal
from backend.rate_limiter import rate_limiter

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    rate_limiter.requests.clear()
    yield


def test_user_registration_and_login():
    # Register User 1
    reg_response = client.post(
        "/api/auth/register",
        json={
            "full_name": "Aarav Sharma",
            "email": "aarav@example.com",
            "phone": "+919876543210",
            "password": "Password123!",
            "currency_symbol": "₹",
            "currency_code": "INR"
        }
    )
    assert reg_response.status_code == 201
    data = reg_response.json()
    assert "access_token" in data
    assert data["user"]["full_name"] == "Aarav Sharma"
    assert data["user"]["currency_symbol"] == "₹"

    # Login with email
    login_response = client.post(
        "/api/auth/login",
        json={
            "username": "aarav@example.com",
            "password": "Password123!"
        }
    )
    assert login_response.status_code == 200
    assert "access_token" in login_response.json()

    # Login with mobile number
    login_phone_response = client.post(
        "/api/auth/login",
        json={
            "username": "+919876543210",
            "password": "Password123!"
        }
    )
    assert login_phone_response.status_code == 200


def test_data_isolation_between_users():
    # Register User A
    res_a = client.post(
        "/api/auth/register",
        json={
            "full_name": "User Alpha",
            "email": "alpha@example.com",
            "password": "SecretPassword1"
        }
    )
    token_a = res_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Set User A allowance to 10000
    client.post(
        "/api/cycles",
        headers=headers_a,
        json={
            "month_year": "2026-10",
            "initial_allowance": 10000.0,
            "funding_source": "Parents",
            "notes": "Alpha monthly budget"
        }
    )

    # Add Expense for User A
    exp_a = client.post(
        "/api/expenses",
        headers=headers_a,
        json={
            "amount": 1200.0,
            "category": "Food & Dining",
            "date": "2026-10-05",
            "description": "Hostel canteen bill",
            "payment_mode": "UPI"
        }
    )
    assert exp_a.status_code == 201

    # Register User B
    res_b = client.post(
        "/api/auth/register",
        json={
            "full_name": "User Beta",
            "email": "beta@example.com",
            "password": "SecretPassword2"
        }
    )
    token_b = res_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User B checks their expenses -> Must be 0, totally isolated
    get_exp_b = client.get("/api/expenses?month_year=2026-10", headers=headers_b)
    assert get_exp_b.status_code == 200
    assert len(get_exp_b.json()) == 0

    # User B summary must have 0 spent and independent balance
    sum_b = client.get("/api/dashboard/summary?month_year=2026-10", headers=headers_b)
    assert sum_b.status_code == 200
    assert sum_b.json()["total_spent"] == 0.0

    # User A summary must have 1200 spent and 8800 remaining
    sum_a = client.get("/api/dashboard/summary?month_year=2026-10", headers=headers_a)
    assert sum_a.status_code == 200
    assert sum_a.json()["total_spent"] == 1200.0
    assert sum_a.json()["remaining_balance"] == 8800.0


def test_allowance_dynamic_balance_and_mid_month_refill():
    reg = client.post(
        "/api/auth/register",
        json={
            "full_name": "Priya Patel",
            "email": "priya@example.com",
            "password": "Password123"
        }
    )
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Set Initial Allowance ₹5,000
    client.post(
        "/api/cycles",
        headers=headers,
        json={
            "month_year": "2026-10",
            "initial_allowance": 5000.0,
            "funding_source": "Dad"
        }
    )

    # Log Expense 1: ₹3,000 for textbooks
    client.post(
        "/api/expenses",
        headers=headers,
        json={
            "amount": 3000.0,
            "category": "Books & Study",
            "date": "2026-10-02",
            "description": "Semester Engineering Books"
        }
    )

    # Log Expense 2: ₹2,500 for Hostel groceries
    client.post(
        "/api/expenses",
        headers=headers,
        json={
            "amount": 2500.0,
            "category": "Groceries",
            "date": "2026-10-08",
            "description": "Monthly pantry & groceries"
        }
    )

    # Check dashboard before refill:
    # Initial: 5000, Spent: 5500 -> Deficit -500
    dash_before = client.get("/api/dashboard/summary?month_year=2026-10", headers=headers).json()
    assert dash_before["total_budget"] == 5000.0
    assert dash_before["total_spent"] == 5500.0
    assert dash_before["remaining_balance"] == -500.0

    # User logs Mid-Month Refill: ₹2,000 from Mom
    refill_res = client.post(
        "/api/refills",
        headers=headers,
        json={
            "amount": 2000.0,
            "funding_source": "Mom",
            "reason": "Mid-month groceries top-up",
            "date": "2026-10-08",
            "payment_mode": "UPI"
        }
    )
    assert refill_res.status_code == 201

    # Check dashboard after refill:
    # Total Budget: 5000 + 2000 = 7000. Total Spent: 5500. Remaining: 1500!
    dash_after = client.get("/api/dashboard/summary?month_year=2026-10", headers=headers).json()
    assert dash_after["total_budget"] == 7000.0
    assert dash_after["total_refills"] == 2000.0
    assert dash_after["remaining_balance"] == 1500.0
    assert len(dash_after["refills"]) == 1


def test_settlement_and_parent_breakdown_generator():
    reg = client.post(
        "/api/auth/register",
        json={
            "full_name": "Rohan Gupta",
            "email": "rohan@example.com",
            "password": "Password123"
        }
    )
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    client.post(
        "/api/cycles",
        headers=headers,
        json={
            "month_year": "2026-10",
            "initial_allowance": 4000.0,
            "funding_source": "Parents"
        }
    )

    client.post(
        "/api/expenses",
        headers=headers,
        json={
            "amount": 1500.0,
            "category": "Food & Dining",
            "date": "2026-10-04",
            "description": "Weekly mess food and fruits"
        }
    )

    settlement = client.get("/api/settlement/summary?month_year=2026-10", headers=headers).json()
    assert settlement["user_name"] == "Rohan Gupta"
    assert settlement["initial_allowance"] == 4000.0
    assert settlement["total_spent"] == 1500.0
    assert settlement["remaining_balance"] == 2500.0
    assert "whatsapp_share_text" in settlement
    assert "Food & Dining" in settlement["whatsapp_share_text"]
    assert "Rohan Gupta" in settlement["whatsapp_share_text"]


def test_csv_export():
    reg = client.post(
        "/api/auth/register",
        json={
            "full_name": "Neha Sharma",
            "email": "neha@example.com",
            "password": "Password123"
        }
    )
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    client.post(
        "/api/expenses",
        headers=headers,
        json={
            "amount": 450.0,
            "category": "Transport & Fuel",
            "date": "2026-10-06",
            "description": "Metro smartcard recharge"
        }
    )

    csv_res = client.get("/api/export/csv?month_year=2026-10", headers=headers)
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers["content-type"]
    assert "Metro smartcard recharge" in csv_res.text
    assert "Transport & Fuel" in csv_res.text


def test_frontend_serving():
    # Test index.html serving
    index_res = client.get("/")
    assert index_res.status_code == 200
    assert "Personal Expense & Allowance Tracker" in index_res.text

    # Test manifest serving
    manifest_res = client.get("/manifest.json")
    assert manifest_res.status_code == 200
    assert "AllowanceTracker" in manifest_res.text

    # Test sw.js serving
    sw_res = client.get("/sw.js")
    assert sw_res.status_code == 200


def test_initial_allowance_is_zero_on_first_login():
    reg_response = client.post(
        "/api/auth/register",
        json={
            "full_name": "New User",
            "email": "newuser@example.com",
            "password": "Password123!"
        }
    )
    token = reg_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Verify current cycle starts with 0.0 initial allowance
    cycle_res = client.get("/api/cycles/current", headers=headers)
    assert cycle_res.status_code == 200
    assert cycle_res.json()["initial_allowance"] == 0.0

    # Summary must have total_budget = 0.0
    sum_res = client.get("/api/dashboard/summary", headers=headers)
    assert sum_res.status_code == 200
    assert sum_res.json()["initial_allowance"] == 0.0
    assert sum_res.json()["total_budget"] == 0.0


def test_ai_category_classification():
    # Test food detection
    res1 = client.post("/api/ai/classify-category", json={"description": "Canteen lunch with burger and chai"})
    assert res1.status_code == 200
    assert res1.json()["category"] == "Food & Dining"
    assert res1.json()["matched"] is True

    # Test transport detection
    res2 = client.post("/api/ai/classify-category", json={"description": "Metro rail recharge and rapido bike ride"})
    assert res2.status_code == 200
    assert res2.json()["category"] == "Transport & Fuel"

    # Test study detection
    res3 = client.post("/api/ai/classify-category", json={"description": "Notebooks, pen and semester xerox"})
    assert res3.status_code == 200
    assert res3.json()["category"] == "Books & Study"

    # Test unknown description
    res4 = client.post("/api/ai/classify-category", json={"description": "Random miscellaneous stuff"})
    assert res4.status_code == 200
    assert res4.json()["category"] == "Other"


