"""
Password hashing and JWT helpers.

Auth was planned for Phase 4 but pulled forward: Phase 2 copy subscriptions
are per-user and need an identity to hang off. Config knobs (SECRET_KEY,
ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES) have existed in core.config since
Phase 0.

Uses the bcrypt library directly rather than passlib: passlib 1.7.4 is
unmaintained and crashes reading version metadata from bcrypt >= 4.1.
bcrypt truncates passwords at 72 bytes, so request schemas cap password
length at 72.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import JWTError, jwt

from core.config import settings

logger = logging.getLogger(__name__)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        # Malformed stored hash — treat as a failed login, not a 500.
        logger.warning("verify_password: malformed password hash")
        return False


def create_token(
    subject: str, purpose: str, expires_minutes: Optional[int] = None
) -> str:
    """
    Signed JWT with the user id as `sub` and a `purpose` claim.

    Purposes keep token kinds mutually unusable: an access token can't
    reset a password and a reset token can't authenticate a request.
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(
        minutes=expires_minutes
        if expires_minutes is not None
        else settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": subject, "purpose": purpose, "iat": now, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str, purpose: str) -> Optional[str]:
    """Return the token's `sub` if valid, unexpired, and purpose-matched.

    Tokens minted before the purpose claim existed carry no `purpose`;
    they are honored as "access" tokens only.
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
    except JWTError:
        return None
    token_purpose = payload.get("purpose", "access")
    if token_purpose != purpose:
        return None
    sub = payload.get("sub")
    return sub if isinstance(sub, str) else None


def create_access_token(subject: str, expires_minutes: Optional[int] = None) -> str:
    return create_token(subject, "access", expires_minutes)


def decode_access_token(token: str) -> Optional[str]:
    return decode_token(token, "access")
