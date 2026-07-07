"""Auth hardening: throttling, password reset, email verification."""
import pytest


def _register(client, email="hard@example.com", password="password123"):
    r = client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    return r.json()


# ---------- throttling ----------

def test_rate_limiter_fails_open_without_redis():
    from core.redis_cache import cache

    # Redis is unreachable in the test environment (conftest) — the limiter
    # must allow rather than lock everyone out.
    assert cache.available is False
    assert cache.rate_limit("rl:test", 1, 60) is True
    assert cache.rate_limit("rl:test", 1, 60) is True


def test_login_throttled_when_limiter_denies(client, db, monkeypatch):
    from routes import auth as auth_routes

    _register(client, "throttle@example.com")
    monkeypatch.setattr(auth_routes.cache, "rate_limit", lambda *a, **k: False)

    r = client.post("/api/v1/auth/login",
                    json={"email": "throttle@example.com", "password": "password123"})
    assert r.status_code == 429
    assert "try again" in r.json()["detail"].lower()

    r = client.post("/api/v1/auth/register",
                    json={"email": "other@example.com", "password": "password123"})
    assert r.status_code == 429


def test_throttle_key_uses_forwarded_for(client, db, monkeypatch):
    from routes import auth as auth_routes

    seen_keys = []

    def spy(key, max_attempts, window):
        seen_keys.append(key)
        return True

    monkeypatch.setattr(auth_routes.cache, "rate_limit", spy)
    client.post("/api/v1/auth/login",
                json={"email": "x@example.com", "password": "password123"},
                headers={"X-Forwarded-For": "203.0.113.9, 10.0.0.1"})
    assert seen_keys and seen_keys[-1] == "rl:login:203.0.113.9"


# ---------- password reset ----------

@pytest.fixture()
def sent_emails(monkeypatch):
    """Capture outbound auth emails (SMTP is unconfigured in tests anyway)."""
    from routes import auth as auth_routes

    outbox = []

    def fake_send(to_email, subject, body_html):
        outbox.append({"to": to_email, "subject": subject, "body": body_html})
        return True

    monkeypatch.setattr(auth_routes, "send_email", fake_send)
    return outbox


def _extract_token(body: str, marker: str) -> str:
    start = body.index(marker) + len(marker)
    end = min(
        (i for i in (body.find('"', start), body.find("&", start)) if i != -1),
        default=len(body),
    )
    return body[start:end]


def test_password_reset_flow(client, db, sent_emails):
    _register(client, "reset@example.com", "originalpass1")

    # Unknown email answers identically (no account leaking) and sends nothing.
    r = client.post("/api/v1/auth/forgot-password", json={"email": "ghost@example.com"})
    assert r.status_code == 200
    reset_mails = [m for m in sent_emails if "Reset" in m["subject"]]
    assert len(reset_mails) == 0

    r = client.post("/api/v1/auth/forgot-password", json={"email": "reset@example.com"})
    assert r.status_code == 200
    reset_mails = [m for m in sent_emails if "Reset" in m["subject"]]
    assert len(reset_mails) == 1
    token = _extract_token(reset_mails[0]["body"], "/reset-password?token=")

    r = client.post("/api/v1/auth/reset-password",
                    json={"token": token, "new_password": "brandnewpass1"})
    assert r.status_code == 200

    # Old password dead, new password works.
    assert client.post("/api/v1/auth/login",
                       json={"email": "reset@example.com", "password": "originalpass1"}
                       ).status_code == 401
    assert client.post("/api/v1/auth/login",
                       json={"email": "reset@example.com", "password": "brandnewpass1"}
                       ).status_code == 200


def test_reset_rejects_wrong_purpose_and_garbage_tokens(client, db):
    body = _register(client, "purpose@example.com")
    access_token = body["access_token"]  # purpose=access, not pwreset

    for bad in (access_token, "garbage"):
        r = client.post("/api/v1/auth/reset-password",
                        json={"token": bad, "new_password": "whatever123"})
        assert r.status_code == 400

    # Expired reset token.
    from core.security import create_token
    expired = create_token(body["user"]["id"], "pwreset", expires_minutes=-5)
    r = client.post("/api/v1/auth/reset-password",
                    json={"token": expired, "new_password": "whatever123"})
    assert r.status_code == 400


# ---------- email verification ----------

def test_email_verification_flow(client, db, sent_emails):
    body = _register(client, "verifyme@example.com")
    auth = {"Authorization": f"Bearer {body['access_token']}"}
    assert body["user"]["email_verified"] is False

    verify_mails = [m for m in sent_emails if "Verify" in m["subject"]]
    assert len(verify_mails) == 1 and verify_mails[0]["to"] == "verifyme@example.com"
    token = _extract_token(verify_mails[0]["body"], "verify_token=")

    r = client.get(f"/api/v1/auth/verify-email?token={token}")
    assert r.status_code == 200

    me = client.get("/api/v1/auth/me", headers=auth).json()
    assert me["email_verified"] is True

    # Re-verifying is idempotent; access tokens don't verify.
    assert client.get(f"/api/v1/auth/verify-email?token={token}").status_code == 200
    assert client.get(
        f"/api/v1/auth/verify-email?token={body['access_token']}"
    ).status_code == 400
