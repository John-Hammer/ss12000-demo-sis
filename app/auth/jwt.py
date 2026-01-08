"""
JWT token handling for SS12000 API authentication.
"""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt

from ..config import get_settings

settings = get_settings()


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)

    to_encode.update({"exp": expire, "iat": datetime.utcnow()})

    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm
    )
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """Verify and decode a JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm]
        )
        return payload
    except JWTError:
        return None


def verify_client_credentials(client_id: str, client_secret: str) -> bool:
    """Verify client credentials for OAuth2 client_credentials flow."""
    return (
        client_id == settings.demo_client_id and
        client_secret == settings.demo_client_secret
    )
