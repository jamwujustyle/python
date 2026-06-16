import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from app.auth.dependencies import get_current_user, get_admin_user, get_user_service
from app.user.models import User, UserRole
from app.user.schemas import UserRead, UserUpdate
from app.user.service import UserService

router = APIRouter(tags=["Users"])


@router.get(
    "/me",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    summary="Get current user profile",
    description="Returns the profile information of the currently authenticated user.",
)
async def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user


@router.get(
    "/users",
    response_model=List[UserRead],
    dependencies=[Depends(get_admin_user)],
    status_code=status.HTTP_200_OK,
    summary="List users",
    description="Returns a paginated list of all registered users. Access is restricted to Admin users.",
)
async def read_users(
    skip: int = 0,
    limit: int = 100,
    service: UserService = Depends(get_user_service),
):
    return await service.get_users(skip=skip, limit=limit)


@router.get(
    "/users/{id}",
    response_model=UserRead,
    dependencies=[Depends(get_admin_user)],
    status_code=status.HTTP_200_OK,
    summary="Get user by ID",
    description="Retrieves the profile details of a specific user by their UUID. Access is restricted to Admin users.",
)
async def read_user_by_id(
    id: uuid.UUID,
    service: UserService = Depends(get_user_service),
):
    user = await service.get_user_by_id(id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    return user


@router.patch(
    "/users/{id}",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    summary="Partially update user",
    description="Allows a user to update their own profile data, or an Admin to update any user's profile data.",
)
async def update_user_profile(
    id: uuid.UUID,
    user_in: UserUpdate,
    service: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_user),
):
    # Check permissions: user can update themselves; admins can update anyone
    if current_user.id != id and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied. You can only update your own profile.",
        )

    db_user = await service.get_user_by_id(id)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    # Check for email conflicts if changing email
    if user_in.email and user_in.email != db_user.email:
        conflict_user = await service.get_user_by_email(user_in.email)
        if conflict_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email address already exists.",
            )

    return await service.update_user(db_user, user_in)


@router.delete(
    "/users/{id}",
    dependencies=[Depends(get_admin_user)],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete user",
    description="Deletes a user from the system by their UUID. Access is restricted to Admin users.",
)
async def delete_user_profile(
    id: uuid.UUID,
    service: UserService = Depends(get_user_service),
):
    deleted = await service.delete_user(id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    return None
