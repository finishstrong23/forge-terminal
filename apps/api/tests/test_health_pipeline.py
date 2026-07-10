"""GET /health/pipeline diagnostics.

Redis is unreachable in the test environment (conftest points REDIS_URL at
a dead port), so these tests exercise the degraded path deliberately: the
endpoint must stay a 200 with readable diagnostics even with no cache and
no heartbeats — that is exactly the situation it exists to explain.
"""
from datetime import datetime, timezone


def test_empty_pipeline_reports_degraded_with_reasons(client):
    r = client.get("/health/pipeline")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "degraded"
    assert body["database"]["ok"] is True
    assert body["redis"]["ok"] is False
    assert any("redis" in p for p in body["problems"])
    assert any("webhook events" in p for p in body["problems"])
    assert body["ingestion"]["last_event_at"] is None
    assert body["ingestion"]["events_last_hour"] == 0
    # Redis down → heartbeats unreadable → "unknown", not "never".
    assert all(t["state"] == "unknown" for t in body["beat_tasks"].values())


def test_fresh_data_clears_ingestion_problem(client, db, seed_activity):
    from models.token import HeliusEvent, TokenSignal

    now = datetime.now(timezone.utc)
    db.add(HeliusEvent(event_type="SWAP", signature="sig-h1", raw_data={},
                       event_timestamp=now, received_at=now, processed=True))
    db.add(TokenSignal(id="ts1", token_address="TOK1", symbol="TOK1",
                       scan_timestamp=now, momentum_score=80.0, rug_risk_score=20.0))
    seed_activity("walletA", "TOK1", "buy", 1.0, "sig-a1", mins_ago=1)
    db.commit()

    body = client.get("/health/pipeline").json()
    assert body["ingestion"]["events_last_hour"] == 1
    assert body["ingestion"]["unprocessed_backlog"] == 0
    assert body["ingestion"]["age_seconds"] is not None
    assert body["discovery"]["tokens_last_hour"] == 1
    assert body["discovery"]["last_scored_token_at"] is not None
    assert body["wallet_activity"]["last_at"] is not None
    assert not any("webhook events" in p for p in body["problems"])
    # Still degraded overall: Redis is down in the test environment.
    assert body["status"] == "degraded"


def test_heartbeat_helpers_never_raise_without_redis():
    from core.heartbeat import beat, read

    beat("some_task")  # no-op with Redis down, must not raise
    assert read(["some_task"]) == {"some_task": None}


def test_liveness_endpoint_still_works(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["database"] == "connected"


def test_redis_debug_reports_failure_stage_without_secrets(client):
    r = client.get("/health/redis-debug")
    assert r.status_code == 200
    body = r.json()
    # conftest points REDIS_URL at 127.0.0.1:1 — DNS resolves, TCP refused.
    assert body["url"]["host"] == "127.0.0.1"
    assert body["dns"]["ok"] is True
    assert all(t["ok"] is False for t in body["tcp"])
    assert body["ping"]["ok"] is False and "error" in body["ping"]
    # Password must never appear anywhere in the payload, only its length.
    assert "password_length" in body["url"]
    assert "password" not in str(body).replace("password_length", "")
