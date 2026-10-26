import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.config import settings
from app.core.errors import unauthorized

# bcrypt only uses the first 72 bytes and bcrypt>=5 raises on longer input, so truncate explicitly.
_BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode()[:_BCRYPT_MAX_BYTES], bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode()[:_BCRYPT_MAX_BYTES], hashed.encode())


def create_access_token(user_id: int, role: str) -> tuple[str, int]:
    """Return (token, expires_in_seconds). `jti` lets logout revoke this specific token."""
    now = datetime.now(timezone.utc)
    expires_in = settings.jwt_expire_minutes * 60
    payload = {
        "sub": str(user_id),
        "role": role,
        "jti": uuid.uuid4().hex,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm), expires_in


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "jti", "exp"]}, # reject the token if any of these claims is missing
        )
    except jwt.ExpiredSignatureError:
        raise unauthorized("TOKEN_EXPIRED", "Token has expired. Please log in again.")
    except jwt.InvalidTokenError: # everything else: bad signature, malformed, missing claim, wrong alg
        raise unauthorized("INVALID_TOKEN", "Token is invalid.")
