"""
Auth REST endpoints.

POST /api/v1/auth/register         — create account (throttled), returns a token
POST /api/v1/auth/login            — email + password (throttled), returns a token
GET  /api/v1/auth/me               — current user from a Bearer token
POST /api/v1/auth/forgot-password  — email a reset link (never leaks existence)
POST /api/v1/auth/reset-password   — set a new password with a reset token
GET  /api/v1/auth/verify-email     — mark email verified, redirect to login

get_current_user is the reusable dependency for protected routes;
get_current_user_optional for public endpoints with tier-dependent behavior.

Throttling is per-IP via Redis (fail-open when Redis is down — the limiter
backend being unavailable must not lock users out). Reset/verify links use
purpose-scoped JWTs (core/security.create_token) so access tokens and email
tokens are mutually unusable.
"""
import logging
import secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from core.redis_cache import cache
from core.security import (
    create_access_token,
    create_refresh_token,
    create_token,
    decode_access_token,
    decode_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from models.user import User
from schemas.auth import (
    ForgotPasswordRequest,
    RefreshRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
)
from services.discovery.alert_service import send_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth")

_bearer = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=401,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)

# attempts / window (seconds), keyed per client IP.
LOGIN_RATE = (10, 300)
REGISTER_RATE = (5, 3600)
FORGOT_RATE = (5, 3600)

RESET_TOKEN_MINUTES = 30
VERIFY_TOKEN_MINUTES = 60 * 24 * 7

# A valid bcrypt hash of a random string, compared against on unknown-email
# logins so response timing doesn't reveal whether the account exists.
_DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(16))


def _client_ip(request: Request) -> str:
    """
    Client IP for rate limiting. X-Forwarded-For is a client-appendable
    list — the LEFTMOST entry is attacker-controlled, so keying on it lets
    an attacker rotate a fake value per request and bypass throttling. The
    trustworthy value is the RIGHTMOST hop, appended by our own proxy
    (Railway/Vercel) closest to the app.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        hops = [h.strip() for h in forwarded.split(",") if h.strip()]
        if hops:
            return hops[-1]
    return request.client.host if request.client else "unknown"


def _throttle(request: Request, bucket: str, rate: tuple) -> None:
    max_attempts, window = rate
    if not cache.rate_limit(f"rl:{bucket}:{_client_ip(request)}", max_attempts, window):
        raise HTTPException(
            status_code=429, detail="Too many attempts — try again later"
        )


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the Bearer token to a User row. 401 on any failure."""
    if credentials is None:
        raise _UNAUTHORIZED
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise _UNAUTHORIZED
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise _UNAUTHORIZED
    return user


def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    Like get_current_user, but anonymous/invalid tokens resolve to None
    instead of 401 — for public endpoints whose behavior varies by tier
    (e.g. the free-tier feed delay).
    """
    if credentials is None:
        return None
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        return None
    return db.query(User).filter(User.id == user_id).first()


def require_owner(user: User = Depends(get_current_user)) -> User:
    """Guard for operational endpoints: only accounts in OWNER_EMAILS."""
    if user.email not in settings.OWNER_EMAILS:
        raise HTTPException(status_code=403, detail="Owner access required")
    return user


def _token_response(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        user=UserResponse.model_validate(user),
    )


def _send_verification_email(user: User) -> None:
    """Best-effort: no-ops (with a log line) when SMTP isn't configured."""
    token = create_token(user.id, "verify", expires_minutes=VERIFY_TOKEN_MINUTES)
    # Backend endpoint verifies and bounces to the login page.
    link = f"{settings.FRONTEND_URL}/login?verify_token={token}"
    sent = send_email(
        user.email,
        "Verify your Forge Terminal email",
        f"""<p>Welcome to Forge Terminal.</p>
<p><a href="{link}">Click here to verify your email address.</a></p>
<p>This link expires in 7 days. If you didn't create this account, ignore this email.</p>""",
    )
    if not sent:
        logger.info("verification email skipped (SMTP unconfigured) for %s", user.id)


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(
    body: RegisterRequest, request: Request, db: Session = Depends(get_db)
) -> TokenResponse:
    _throttle(request, "register", REGISTER_RATE)
    email = body.email.lower()
    # Privilege is granted by email membership in OWNER_EMAILS, so an owner
    # address must never be self-registerable by a stranger.
    if email in {e.lower() for e in settings.OWNER_EMAILS}:
        raise HTTPException(status_code=403, detail="This email cannot be registered")
    if db.query(User.id).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(email=email, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("auth/register: created user %s", user.id)
    _send_verification_email(user)
    return _token_response(user)


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest, request: Request, db: Session = Depends(get_db)
) -> TokenResponse:
    _throttle(request, "login", LOGIN_RATE)
    user = db.query(User).filter(User.email == body.email.lower()).first()
    # Same message AND same timing for unknown-email vs wrong-password: run a
    # bcrypt compare against a dummy hash when the email is unknown so the
    # ~100ms hashing cost can't be used as an account-existence oracle.
    if user is None:
        verify_password(body.password, _DUMMY_PASSWORD_HASH)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    user.last_login = datetime.now(timezone.utc)
    db.commit()
    return _token_response(user)


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """
    Exchange a valid refresh token for a fresh access+refresh pair
    (rotation: the response's refresh token replaces the one sent).
    Stateless JWTs — a stolen refresh token stays valid until expiry;
    revocation storage is a known follow-up before high-value accounts.
    """
    user_id = decode_refresh_token(body.refresh_token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    return _token_response(user)


@router.post("/forgot-password")
def forgot_password(
    body: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)
):
    """Always 200 — the response must not reveal whether the email exists."""
    _throttle(request, "forgot", FORGOT_RATE)
    user = db.query(User).filter(User.email == body.email.lower()).first()
    if user is not None:
        token = create_token(user.id, "pwreset", expires_minutes=RESET_TOKEN_MINUTES)
        link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
        sent = send_email(
            user.email,
            "Reset your Forge Terminal password",
            f"""<p>A password reset was requested for this account.</p>
<p><a href="{link}">Click here to choose a new password.</a></p>
<p>This link expires in {RESET_TOKEN_MINUTES} minutes. If you didn't request
this, you can safely ignore it.</p>""",
        )
        if not sent:
            logger.warning("password reset email not sent (SMTP unconfigured) for %s", user.id)
    return {"status": "ok", "detail": "If that email exists, a reset link was sent"}


@router.post("/reset-password")
def reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)):
    user_id = decode_token(body.token, "pwreset")
    if user_id is None:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")
    user.password_hash = hash_password(body.new_password)
    db.commit()
    logger.info("auth/reset-password: password updated for %s", user.id)
    return {"status": "ok", "detail": "Password updated — sign in with the new password"}


@router.get("/verify-email")
def verify_email(
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    """Called by the login page when the emailed link's verify_token is present."""
    user_id = decode_token(token, "verify")
    if user_id is None:
        raise HTTPException(status_code=400, detail="Invalid or expired verification link")
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=400, detail="Invalid or expired verification link")
    if not user.email_verified:
        user.email_verified = True
        db.commit()
    return {"status": "ok", "detail": "Email verified"}
