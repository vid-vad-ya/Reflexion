import jwt
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Union
from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlmodel import Session

from app.core.config import settings
from app.database import get_session
from app.models import User

JWT_ALGORITHM = "HS256"
security_bearer = HTTPBearer(auto_error=False)


def get_fernet() -> Fernet:
    """Helper to initialize Fernet with the encryption key."""
    if not settings.ENCRYPTION_KEY:
        raise ValueError("ENCRYPTION_KEY setting is not configured.")
    return Fernet(settings.ENCRYPTION_KEY.encode())


def encrypt_token(token: str) -> str:
    """Symmetrically encrypt a string token using Fernet."""
    if not token:
        return ""
    f = get_fernet()
    return f.encrypt(token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str:
    """Symmetrically decrypt an encrypted Fernet token."""
    if not encrypted_token:
        return ""
    f = get_fernet()
    return f.decrypt(encrypted_token.encode()).decode()


def create_access_token(subject: Union[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    session: Session = Depends(get_session)
) -> User:
    """FastAPI dependency to extract and validate the JWT and retrieve the user."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload: 'sub' claim missing",
            )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID format in token",
        )
        
    user = session.get(User, user_uuid)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user
