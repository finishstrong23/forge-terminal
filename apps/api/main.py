import asyncio
import logging
import os
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.pubsub import subscribe_and_fanout
from routes.auth import router as auth_router
from routes.billing import router as billing_router
from routes.copy import router as copy_router
from routes.copy_subscriptions import router as copy_subscriptions_router
from routes.discovery import router as discovery_router
from routes.execute import router as execute_router
from routes.health import router as health_router
from routes.signals import router as signals_router
from routes.ws import router as ws_router
from services.discovery.webhook_handler import router as webhook_router

logger = logging.getLogger(__name__)

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=0.1,
        # Railway injects the deploy SHA; release tagging groups errors by deploy.
        release=os.getenv("RAILWAY_GIT_COMMIT_SHA") or os.getenv("GIT_COMMIT_SHA"),
        environment=os.getenv("SENTRY_ENVIRONMENT", "production"),
    )


def _seed_owner_account() -> None:
    """Create the first owner account from OWNER_INITIAL_PASSWORD if it does
    not exist. Owner emails can't be self-registered, so this keeps a
    database reset from locking the owner out. Idempotent; never fatal."""
    if not settings.OWNER_INITIAL_PASSWORD or not settings.OWNER_EMAILS:
        return
    try:
        from core.database import SessionLocal
        from core.security import hash_password
        from models.user import User

        email = settings.OWNER_EMAILS[0].lower()
        db = SessionLocal()
        try:
            if db.query(User.id).filter(User.email == email).first() is None:
                db.add(User(email=email,
                            password_hash=hash_password(settings.OWNER_INITIAL_PASSWORD)))
                db.commit()
                logger.info("seeded owner account %s", email)
        finally:
            db.close()
    except Exception as exc:
        logger.warning("owner seed skipped: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure the owner account exists (no-op unless OWNER_INITIAL_PASSWORD set).
    _seed_owner_account()
    # Start the Redis pubsub subscriber that fans messages out to WS clients.
    subscriber_task = asyncio.create_task(subscribe_and_fanout())
    logger.info("lifespan: pubsub subscriber task started")
    # Self-heal the Helius webhook registration on every boot (no-op unless
    # HELIUS_API_KEY + a public domain are configured; never raises).
    from services.discovery.helius_webhooks import ensure_webhook_registered

    registration_task = asyncio.create_task(ensure_webhook_registered())
    try:
        yield
    finally:
        registration_task.cancel()
        subscriber_task.cancel()
        try:
            await subscriber_task
        except asyncio.CancelledError:
            pass
        logger.info("lifespan: pubsub subscriber task stopped")


# Hide the interactive API explorer + schema in production so the full
# route map (including operational endpoints) isn't handed to anyone.
_docs_enabled = not settings.is_production
app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    # Auth is Bearer-token, not cookie-based, so credentialed CORS isn't
    # needed — keeping it off avoids the fragile allow_credentials + origin
    # combination if the allowlist is ever broadened.
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(health_router)
app.include_router(signals_router)
app.include_router(discovery_router)
app.include_router(copy_router)
app.include_router(copy_subscriptions_router)
app.include_router(auth_router)
app.include_router(billing_router)
app.include_router(execute_router)
app.include_router(ws_router)
app.include_router(webhook_router, prefix="/api/v1")


@app.get("/")
def root():
    return {
        "app": settings.APP_NAME,
        "version": "0.1.0",
        "docs": "/docs",
    }
