from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator
from typing import Optional

INSECURE_SECRET_KEY = "change-me-in-production"


class Settings(BaseSettings):
    APP_NAME: str = "Forge Terminal"
    API_V1_STR: str = "/api/v1"

    # "production" turns on fail-closed hardening (see the validator below):
    # a real SECRET_KEY and HELIUS_WEBHOOK_SECRET become mandatory and API
    # docs are hidden. Railway/prod must set ENVIRONMENT=production.
    ENVIRONMENT: str = "development"

    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/forge_terminal"
    REDIS_URL: str = "redis://localhost:6379/0"

    SECRET_KEY: str = INSECURE_SECRET_KEY
    ALGORITHM: str = "HS256"
    # Short-lived access + long-lived refresh (was a single 7-day access
    # token; shortened before taking payments).
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 30

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

    # Helius credit control. The program-wide webhook is a firehose (~95% of
    # credit spend); when disabled the app deletes it and relies on poll-based
    # discovery only. Poll cadences (seconds) drive the remaining DAS spend —
    # 300s keeps usage well within the free 1M/month tier pre-launch.
    WEBHOOK_ENABLED: bool = True
    DISCOVERY_POLL_SECONDS: float = 300.0
    ENRICH_POLL_SECONDS: float = 300.0

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

    # Owner accounts can't be self-registered (privilege is granted by
    # OWNER_EMAILS membership). When set, the first owner email is seeded
    # with this password on startup if it doesn't exist yet — so a database
    # reset doesn't lock the owner out. Change the password after first login.
    OWNER_INITIAL_PASSWORD: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() in {"production", "prod"}

    @model_validator(mode="after")
    def _enforce_production_secrets(self) -> "Settings":
        """Fail closed in production: refuse to boot with a forgeable JWT
        signing key or an unauthenticated webhook ingest. A misconfigured
        prod deploy should crash loudly, not run exploitable."""
        if self.is_production:
            if self.SECRET_KEY == INSECURE_SECRET_KEY or len(self.SECRET_KEY) < 32:
                raise ValueError(
                    "SECRET_KEY must be set to a strong random value "
                    "(>=32 chars) in production; refusing to start with the "
                    "default/weak key."
                )
            if not self.HELIUS_WEBHOOK_SECRET:
                raise ValueError(
                    "HELIUS_WEBHOOK_SECRET must be set in production so the "
                    "public webhook ingest rejects unauthenticated writes."
                )
        return self


settings = Settings()
