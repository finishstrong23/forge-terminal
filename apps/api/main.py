import asyncio
import logging
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings
from core.pubsub import subscribe_and_fanout
from routes.copy import router as copy_router
from routes.discovery import router as discovery_router
from routes.health import router as health_router
from routes.signals import router as signals_router
from routes.ws import router as ws_router
from services.discovery.webhook_handler import router as webhook_router

logger = logging.getLogger(__name__)

if settings.SENTRY_DSN:
    sentry_sdk.init(dsn=settings.SENTRY_DSN, traces_sample_rate=0.1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the Redis pubsub subscriber that fans messages out to WS clients.
    subscriber_task = asyncio.create_task(subscribe_and_fanout())
    logger.info("lifespan: pubsub subscriber task started")
    try:
        yield
    finally:
        subscriber_task.cancel()
        try:
            await subscriber_task
        except asyncio.CancelledError:
            pass
        logger.info("lifespan: pubsub subscriber task stopped")


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(signals_router)
app.include_router(discovery_router)
app.include_router(copy_router)
app.include_router(ws_router)
app.include_router(webhook_router, prefix="/api/v1")


@app.get("/")
def root():
    return {
        "app": settings.APP_NAME,
        "version": "0.1.0",
        "docs": "/docs",
    }
