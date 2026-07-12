"""
Shared pytest fixtures.

Environment is configured at import time — BEFORE any app module is
imported — because core.database builds its engine from DATABASE_URL when
the module loads. Tests run against a throwaway SQLite file; every test
gets a freshly recreated schema.
"""
import os
import sys
import tempfile
from pathlib import Path

_DB_FILE = os.path.join(tempfile.gettempdir(), "forge_api_tests.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_FILE}"
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("HELIUS_API_KEY", "test")
os.environ.setdefault("CELERY_ALWAYS_EAGER", "true")
# Unreachable on purpose: core.redis_cache degrades to compute-every-request,
# so a developer's live Redis can't serve stale cache hits across tests.
os.environ["REDIS_URL"] = "redis://127.0.0.1:1/0"

# Make `core`, `models`, `routes`, `services`, `main` importable when pytest
# is invoked from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _no_live_prices(monkeypatch):
    """CI runners have real internet — price lookups must be deterministic.

    Tests that need a price monkeypatch the consumer (e.g.
    services.copy.shadow_recorder.get_sol_price_usd) to a fixed value.
    """
    monkeypatch.setattr(
        "services.execution.price_feed.fetch_sol_price_usd", lambda: None
    )
    monkeypatch.setattr(
        "services.execution.price_feed.fetch_token_prices_usd",
        lambda mints: {mint: None for mint in mints},
    )
    monkeypatch.setattr(
        "services.execution.token_meta.fetch_token_decimals", lambda mint: None
    )
    monkeypatch.setattr(
        "services.discovery.token_metadata.fetch_das_metadata", lambda mints: {}
    )


@pytest.fixture()
def db():
    """A session against a freshly recreated schema."""
    from core.database import SessionLocal, engine
    from models.base import Base
    import models  # noqa: F401  register every model on Base

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture()
def client(db):
    """TestClient over the app, schema already reset by the db fixture."""
    from fastapi.testclient import TestClient
    import main

    return TestClient(main.app)


@pytest.fixture()
def owner_auth(db):
    """Bearer header for an owner account. Owner emails can't be registered
    via the API (privilege guard), so seed the user directly and mint a
    token for it."""
    from core.config import settings
    from core.security import create_access_token, hash_password
    from models.user import User

    email = settings.OWNER_EMAILS[0].lower()
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(email=email, password_hash=hash_password("ownerpass123"))
        db.add(user)
        db.commit()
        db.refresh(user)
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


@pytest.fixture()
def seed_activity(db):
    """Factory that inserts a WalletActivity row."""
    from datetime import datetime, timedelta, timezone

    from models.wallet import WalletActivity

    def _seed(wallet, token, side, sol, sig, mins_ago=0.0, cluster=None, ts=None):
        activity = WalletActivity(
            wallet_address=wallet,
            token_address=token,
            activity_type=side,
            sol_amount=sol,
            event_signature=sig,
            cluster_id=cluster,
            timestamp=ts
            if ts is not None
            else datetime.now(timezone.utc) - timedelta(minutes=mins_ago),
        )
        db.add(activity)
        return activity

    return _seed
