from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from backend.app.core.config import settings

# API Key security scheme
api_key_header = APIKeyHeader(name="X-API-Key")


async def verify_api_key(api_key: str = Depends(api_key_header)) -> str:
    """Verify API key from X-API-Key header"""
    if api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return api_key