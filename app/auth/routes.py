"""
Authentication routes for SS12000 API.
Implements OAuth2 client_credentials flow.
"""
from fastapi import APIRouter, HTTPException, status, Form
from pydantic import BaseModel

from .jwt import create_access_token, verify_client_credentials
from ..config import get_settings

router = APIRouter(tags=["Authentication"])
settings = get_settings()


class TokenResponse(BaseModel):
    """OAuth2 token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


@router.post("/token", response_model=TokenResponse)
async def get_token(
    grant_type: str = Form(...),
    client_id: str = Form(...),
    client_secret: str = Form(...),
):
    """
    OAuth2 token endpoint.
    Implements client_credentials grant type for machine-to-machine auth.

    Demo credentials:
    - client_id: skolskold_demo
    - client_secret: demo_secret_123
    """
    if grant_type != "client_credentials":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported grant_type. Use 'client_credentials'."
        )

    if not verify_client_credentials(client_id, client_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid client credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create token with client info
    token_data = {
        "sub": client_id,
        "client_id": client_id,
        "scope": "ss12000:read"  # Read-only scope for demo
    }

    access_token = create_access_token(token_data)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.jwt_expire_minutes * 60
    )
