"""
FastAPI dependencies for authentication.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .jwt import verify_token

# Bearer token security scheme
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_client(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
) -> dict:
    """
    Dependency to get the current authenticated client.
    Returns the decoded JWT payload.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = verify_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


async def optional_auth(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
) -> dict | None:
    """
    Optional authentication - returns None if no valid token.
    Useful for public endpoints that have enhanced features for authenticated users.
    """
    if credentials is None:
        return None

    token = credentials.credentials
    return verify_token(token)
