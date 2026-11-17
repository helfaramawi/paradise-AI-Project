"""Password hashing (PBKDF2-SHA256), JWT access tokens bound to server-side sessions, and TOTP."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import struct
import time
from datetime import UTC, datetime, timedelta

import jwt

from ..config import get_settings

PBKDF2_ITERATIONS = 310_000
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt_b64, dk_b64 = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt_b64), int(iters))
        return hmac.compare_digest(dk, base64.b64decode(dk_b64))
    except (ValueError, TypeError):
        return False


def validate_password_strength(password: str) -> list[str]:
    problems = []
    if len(password) < 10:
        problems.append("at least 10 characters")
    if not any(c.isdigit() for c in password):
        problems.append("at least one digit")
    if not any(c.isalpha() for c in password):
        problems.append("at least one letter")
    return problems


def create_access_token(user_id: str, org_id: str, session_id: str, minutes: int | None = None) -> tuple[str, datetime]:
    s = get_settings()
    exp = datetime.now(UTC) + timedelta(minutes=minutes or s.access_token_minutes)
    token = jwt.encode({"sub": user_id, "org": org_id, "sid": session_id, "exp": exp, "iat": datetime.now(UTC)},
                       s.secret_key, algorithm=ALGORITHM)
    return token, exp


def decode_token(token: str) -> dict:
    return jwt.decode(token, get_settings().secret_key, algorithms=[ALGORITHM])


# ---- TOTP (RFC 6238) — MFA readiness without external dependencies


def new_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def totp(secret: str, at: float | None = None, step: int = 30, digits: int = 6) -> str:
    key = base64.b32decode(secret + "=" * (-len(secret) % 8))
    counter = int((at or time.time()) // step)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return str(code).zfill(digits)


def verify_totp(secret: str, code: str, window: int = 1) -> bool:
    now = time.time()
    return any(hmac.compare_digest(totp(secret, now + i * 30), code.strip()) for i in range(-window, window + 1))
