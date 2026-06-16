from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import decode_token
from app.user.models import User, UserRole
from app.user.service import UserService

# Reusable security scheme for extracting JWT token
security_scheme = HTTPBearer(auto_error=False)


async def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    """Dependency provider to instantiate UserService."""
    return UserService(db)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    user_service: UserService = Depends(get_user_service),
) -> User:
    """Dependency to retrieve the current authenticated user from a JWT access token."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Access token is missing.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = decode_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials. Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_type = payload.get("type")
    if token_type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type. Access token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload is invalid. Subject missing.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await user_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User associated with this token does not exist.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Dependency to ensure the current authenticated user has verified their email/account."""
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not verified. Please verify your email.",
        )
    return current_user


async def get_admin_user(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Dependency to ensure the current user is an Admin."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied. Admin role required.",
        )
    return current_user
