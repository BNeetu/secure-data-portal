"""
Security primitives: password hashing (bcrypt), JWT issuing/verification,
and TOTP (RFC 6238) generation/verification for MFA.

NOTE: We call the `bcrypt` library directly rather than going through
passlib's CryptContext. passlib 1.7.x (last released 2020) probes bcrypt's
internals in a way that breaks on bcrypt 4.x+ (raises
"AttributeError: module 'bcrypt' has no attribute '__about__'", then
mis-reports an unrelated "password cannot be longer than 72 bytes" error
from its broken self-test). Calling bcrypt directly avoids that entire
compatibility problem and removes a dependency.
"""
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import pyotp
from jose import JWTError, jwt

from app.core.config import settings

# bcrypt has a hard 72-byte input limit (it silently ignores anything beyond
# that in some implementations, which is a security footgun) — we hash a
# pre-step with the password's UTF-8 bytes truncated defensively here so
# behavior is explicit and consistent across platforms.
_BCRYPT_MAX_BYTES = 72


def _prepare(plain: str) -> bytes:
    encoded = plain.encode("utf-8")
    if len(encoded) > _BCRYPT_MAX_BYTES:
        encoded = encoded[:_BCRYPT_MAX_BYTES]
    return encoded


# ── Passwords ──────────────────────────────────────────────────────────────
def hash_password(plain: str) -> str:
    hashed = bcrypt.hashpw(_prepare(plain), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_prepare(plain), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        # Malformed hash (e.g. corrupted users.json entry) — fail closed.
        return False


def validate_password_strength(password: str) -> Optional[str]:
    """Returns an error message if weak, else None."""
    if len(password) < settings.MIN_PASSWORD_LENGTH:
        return f"Password must be at least {settings.MIN_PASSWORD_LENGTH} characters long."
    if len(password.encode("utf-8")) > _BCRYPT_MAX_BYTES:
        return f"Password is too long (max {_BCRYPT_MAX_BYTES} bytes)."
    if not re.search(r"[A-Z]", password):
        return "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return "Password must contain at least one lowercase letter."
    if not re.search(r"[0-9]", password):
        return "Password must contain at least one digit."
    if not re.search(r"[!@#$%^&*()\-_=+\[\]{};:,.<>/?]", password):
        return "Password must contain at least one special character."
    return None


# ── TOTP (MFA) ────────────────────────────────────────────────────────────
def generate_totp_secret() -> str:
    return pyotp.random_base32()


def get_totp_uri(username: str, secret: str) -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(
        name=username, issuer_name=settings.MFA_ISSUER_NAME
    )


def verify_totp(secret: str, code: str) -> bool:
    totp = pyotp.TOTP(secret)
    # valid_window=1 allows the previous/next 30s window for clock drift
    return totp.verify(code, valid_window=1)


# ── JWT ───────────────────────────────────────────────────────────────────
def create_access_token(data: dict, expires_minutes: Optional[int] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire, "type": "access", "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "refresh", "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Raises JWTError on invalid/expired token."""
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
