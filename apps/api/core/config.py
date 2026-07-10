from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    APP_NAME: str = "Forge Terminal"
    API_V1_STR: str = "/api/v1"

    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/forge_terminal"
    REDIS_URL: str = "redis://localhost:6379/0"

    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_PUBLISHABLE_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    STRIPE_PRICE_PRO_MONTHLY: Optional[str] = None
    STRIPE_PRICE_PRO_YEARLY: Optional[str] = None

    # Base URL of the web app, used for Stripe checkout/portal redirects.
    FRONTEND_URL: str = "http://localhost:3000"

    # Public base URL of THIS API, for Helius webhook self-registration.
    # Optional: on Railway the injected RAILWAY_PUBLIC_DOMAIN is used instead.
    PUBLIC_API_URL: Optional[str] = None

    HELIUS_API_KEY: Optional[str] = None
    HELIUS_WEBHOOK_SECRET: Optional[str] = None
    HELIUS_RPC_URL: Optional[str] = None
    # Preferred RPC for confirmation checks; falls back to HELIUS_RPC_URL,
    # then the public mainnet endpoint.
    SOLANA_RPC_URL: Optional[str] = None

    PUMP_FUN_PROGRAM_ID: str = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
    HELIUS_WEBHOOK_ID: Optional[str] = None
    DISCOVERY_BATCH_SIZE: int = 20
    DISCOVERY_ENABLED: bool = True

    MAX_TOKENS_FREE: int = 20
    FREE_TIER_DELAY_MINUTES: int = 15
    FREE_TIER_MAX_DAILY_SIGNALS: int = 50
    MAX_TOKENS_TRADER: int = 100
    MAX_TOKENS_PRO: int = 500
    FREE_TIER_MAX_ACTIVE_FOLLOWS: int = 3
    PRO_TIER_MAX_ACTIVE_FOLLOWS: int = 50

    ALERT_MIN_MOMENTUM: float = 60.0
    ALERT_MIN_CONFIDENCE: float = 70.0
    ALERT_MAX_RUG_RISK: float = 40.0
    MIN_CONFIDENCE_FOR_DISPLAY: float = 50.0

    # SMTP (for alert emails)
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    ALERT_FROM_EMAIL: str = "alerts@forgeterminal.com"

    SENTRY_DSN: Optional[str] = None

    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "https://forge-terminal.vercel.app",
    ]

    OWNER_EMAILS: list[str] = [
        "finishstrong23@gmail.com",
    ]

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)


settings = Settings()
