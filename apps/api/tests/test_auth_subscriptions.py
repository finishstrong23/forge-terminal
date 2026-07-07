"""Auth flow + copy-subscription lifecycle."""
import pytest


@pytest.fixture()
def seeded_client(client, db, seed_activity):
    seed_activity("walletA", "TOK1", "buy", 1.0, "sig1", mins_ago=10)
    db.commit()
    return client


def _register(client, email, password="password123"):
    r = client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    return r.json()


def test_register_login_me(seeded_client):
    client = seeded_client
    body = _register(client, "Trader@Example.com", "hunter2secure")
    assert body["user"]["email"] == "trader@example.com"  # lowercased
    assert body["user"]["subscription_tier"] == "free"

    # duplicate email (case-insensitive) and weak password
    r = client.post("/api/v1/auth/register",
                    json={"email": "trader@example.com", "password": "hunter2secure"})
    assert r.status_code == 409
    r = client.post("/api/v1/auth/register",
                    json={"email": "b@example.com", "password": "short"})
    assert r.status_code == 422

    r = client.post("/api/v1/auth/login",
                    json={"email": "trader@example.com", "password": "hunter2secure"})
    assert r.status_code == 200
    token = r.json()["access_token"]

    # Same 401 body for wrong password and unknown email.
    for creds in [
        {"email": "trader@example.com", "password": "wrongpass1"},
        {"email": "ghost@example.com", "password": "whatever123"},
    ]:
        r = client.post("/api/v1/auth/login", json=creds)
        assert r.status_code == 401 and r.json()["detail"] == "Invalid email or password"

    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200 and r.json()["email"] == "trader@example.com"
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me",
                      headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_expired_token_rejected(seeded_client):
    from core.security import create_access_token

    client = seeded_client
    body = _register(client, "expiry@example.com")
    expired = create_access_token(body["user"]["id"], expires_minutes=-5)
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401


def test_subscription_lifecycle(seeded_client):
    client = seeded_client
    auth = {"Authorization": f"Bearer {_register(client, 'u1@example.com')['access_token']}"}

    assert client.get("/api/v1/copy/subscriptions").status_code == 401

    r = client.post("/api/v1/copy/subscriptions",
                    json={"wallet_address": "walletA", "max_position_usd": 100},
                    headers=auth)
    assert r.status_code == 201, r.text
    sub = r.json()
    assert (sub["status"], sub["mode"], sub["max_position_usd"]) == ("active", "shadow", 100)

    # duplicate follow / unknown wallet / live mode
    assert client.post("/api/v1/copy/subscriptions",
                       json={"wallet_address": "walletA"}, headers=auth).status_code == 409
    assert client.post("/api/v1/copy/subscriptions",
                       json={"wallet_address": "ghost"}, headers=auth).status_code == 404
    assert client.post("/api/v1/copy/subscriptions",
                       json={"wallet_address": "walletA", "mode": "live"},
                       headers=auth).status_code == 422

    assert client.get("/api/v1/copy/subscriptions", headers=auth).json()["count"] == 1

    sid = sub["id"]

    def act(action):
        return client.patch(f"/api/v1/copy/subscriptions/{sid}",
                            json={"action": action}, headers=auth)

    assert act("resume").status_code == 409  # active can't resume
    r = act("pause")
    assert r.status_code == 200 and r.json()["status"] == "paused" and r.json()["paused_at"]
    r = act("resume")
    assert r.status_code == 200 and r.json()["status"] == "active" and r.json()["paused_at"] is None
    r = act("stop")
    assert r.status_code == 200 and r.json()["status"] == "stopped" and r.json()["stopped_at"]
    assert act("pause").status_code == 409  # stopped is terminal

    # Re-follow after stop is allowed.
    assert client.post("/api/v1/copy/subscriptions",
                       json={"wallet_address": "walletA"}, headers=auth).status_code == 201

    # Status filter.
    r = client.get("/api/v1/copy/subscriptions", params={"status": "stopped"}, headers=auth)
    assert r.json()["count"] == 1 and r.json()["subscriptions"][0]["status"] == "stopped"


def test_cross_user_isolation(seeded_client):
    client = seeded_client
    auth1 = {"Authorization": f"Bearer {_register(client, 'a@example.com')['access_token']}"}
    auth2 = {"Authorization": f"Bearer {_register(client, 'b@example.com')['access_token']}"}

    sid = client.post("/api/v1/copy/subscriptions",
                      json={"wallet_address": "walletA"}, headers=auth1).json()["id"]

    assert client.get("/api/v1/copy/subscriptions", headers=auth2).json()["count"] == 0
    # Someone else's subscription id reads as 404, not 403.
    r = client.patch(f"/api/v1/copy/subscriptions/{sid}",
                     json={"action": "stop"}, headers=auth2)
    assert r.status_code == 404
