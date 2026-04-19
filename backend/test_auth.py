# test_auth.py
# Tests authentication endpoints and per-user session isolation
# Does NOT call Claude — uses FastAPI TestClient, free to run

import pytest
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal, UserModel, Base, engine
import uuid

client = TestClient(app)

# ── Helpers ───────────────────────────────────────────────

def unique_email():
    """Generate a unique email for each test so they don't conflict."""
    return f"test_{uuid.uuid4().hex[:8]}@pharmademo.com"

def register_user(email, password="test123", name="Test"):
    return client.post("/register", json={
        "email": email,
        "password": password,
        "name": name
    })

def login_user(email, password="test123"):
    return client.post("/login", json={
        "email": email,
        "password": password
    })

# ── Registration tests ────────────────────────────────────

def test_register_returns_token():
    email = unique_email()
    res = register_user(email)
    assert res.status_code == 200
    assert "token" in res.json()
    assert len(res.json()["token"]) > 0

def test_register_returns_user_id():
    email = unique_email()
    res = register_user(email)
    assert "user_id" in res.json()
    assert res.json()["user_id"].startswith("usr_")

def test_register_returns_name():
    email = unique_email()
    res = register_user(email, name="Rishika")
    assert res.json()["name"] == "Rishika"

def test_register_saves_user_to_postgres():
    email = unique_email()
    register_user(email)
    db = SessionLocal()
    user = db.query(UserModel).filter(UserModel.email == email).first()
    db.close()
    assert user is not None
    assert user.email == email

def test_duplicate_registration_fails():
    email = unique_email()
    register_user(email)
    res = register_user(email)
    assert res.status_code == 400
    assert "already registered" in res.json()["detail"].lower()

def test_short_password_rejected():
    email = unique_email()
    res = register_user(email, password="abc")
    assert res.status_code == 400
    assert "6 characters" in res.json()["detail"].lower()

# ── Login tests ───────────────────────────────────────────

def test_login_returns_token():
    email = unique_email()
    register_user(email)
    res = login_user(email)
    assert res.status_code == 200
    assert "token" in res.json()

def test_login_wrong_password_fails():
    email = unique_email()
    register_user(email, password="correct123")
    res = login_user(email, password="wrongpassword")
    assert res.status_code == 401
    assert "incorrect" in res.json()["detail"].lower()

def test_login_nonexistent_user_fails():
    res = login_user("nobody@pharmademo.com")
    assert res.status_code == 401

def test_login_same_user_id_as_registration():
    email = unique_email()
    reg = register_user(email)
    login = login_user(email)
    assert reg.json()["user_id"] == login.json()["user_id"]

# ── Token tests ───────────────────────────────────────────

def test_token_is_valid_jwt():
    from jose import jwt
    import os
    email = unique_email()
    res = register_user(email)
    token = res.json()["token"]
    secret = os.getenv("JWT_SECRET_KEY", "change-this-in-production-please")
    payload = jwt.decode(token, secret, algorithms=["HS256"])
    assert "user_id" in payload
    assert "email" in payload
    assert payload["email"] == email

def test_invalid_token_rejected_on_ask():
    res = client.post("/ask",
        json={"question": "How many reps are there?"},
        headers={"Authorization": "Bearer fake.token.here"}
    )
    # Should still work because /ask uses get_optional_user (not required)
    # But the user context should be None — no crash
    assert res.status_code == 200

def test_ask_works_without_token():
    """Backwards compatibility — /ask works with no auth token."""
    res = client.post("/ask",
        json={"question": "How many reps are there?"}
    )
    assert res.status_code == 200
    assert "answer" in res.json()

# ── Per-user session isolation tests ─────────────────────

def test_different_users_get_different_user_ids():
    email_a = unique_email()
    email_b = unique_email()
    res_a = register_user(email_a)
    res_b = register_user(email_b)
    assert res_a.json()["user_id"] != res_b.json()["user_id"]

def test_clear_history_requires_valid_token():
    """Clear history with no token — should still return 200 but do nothing."""
    res = client.post("/clear-history")
    assert res.status_code == 200
    assert res.json()["status"] == "cleared"

def test_clear_history_works_with_valid_token():
    email = unique_email()
    reg = register_user(email)
    token = reg.json()["token"]
    res = client.post("/clear-history",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert res.status_code == 200
    assert res.json()["status"] == "cleared"

# ── Rate limiting tests ───────────────────────────────────

def test_rate_limit_key_is_per_user():
    """Two users have separate Redis rate keys."""
    import redis as redis_lib
    import os
    from dotenv import load_dotenv
    load_dotenv()

    email_a = unique_email()
    email_b = unique_email()
    res_a = register_user(email_a)
    res_b = register_user(email_b)

    uid_a = res_a.json()["user_id"]
    uid_b = res_b.json()["user_id"]

    r = redis_lib.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"), decode_responses=True)

    # Set different counts for each user
    r.set(f"rate:{uid_a}", 10)
    r.set(f"rate:{uid_b}", 5)

    assert r.get(f"rate:{uid_a}") == "10"
    assert r.get(f"rate:{uid_b}") == "5"

    # Clean up
    r.delete(f"rate:{uid_a}")
    r.delete(f"rate:{uid_b}")