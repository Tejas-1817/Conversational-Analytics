from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.config import get_settings


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def create_access_token(subject: str | Any, role: str, tenant_id: str) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode = {"exp": expire, "sub": str(subject), "role": role, "tenant_id": str(tenant_id), "type": "access"}
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return encoded_jwt


def create_refresh_token(subject: str | Any, jti: str) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.refresh_token_expire_minutes)
    to_encode = {"exp": expire, "sub": str(subject), "jti": jti, "type": "refresh"}
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return encoded_jwt


def decode_token(token: str) -> dict:
    settings = get_settings()
    try:
        decoded_token = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return decoded_token
    except jwt.ExpiredSignatureError:
        raise ValueError("Token expired")
    except jwt.InvalidTokenError:
        raise ValueError("Invalid token")
