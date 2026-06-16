from fastapi import APIRouter, Depends, status
from app.user.schemas import UserCreate, UserRead
from app.auth.schemas import LoginRequest, RefreshRequest, Token, VerifyRequest
from app.auth.service import AuthService
from app.auth.dependencies import get_auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/signup",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Registers a new user with an email and password. Upon successful registration, the user receives an 'unverified' status and a verification code is printed to the console.",
)
async def signup(
    user_in: UserCreate,
    service: AuthService = Depends(get_auth_service),
):
    return await service.register_user(user_in)


@router.post(
    "/login",
    response_model=Token,
    status_code=status.HTTP_200_OK,
    summary="User login",
    description="Authenticates user credentials and issues access and refresh JWT tokens.",
)
async def login(
    login_in: LoginRequest,
    service: AuthService = Depends(get_auth_service),
):
    return await service.authenticate_user(login_in)


@router.post(
    "/refresh",
    response_model=Token,
    status_code=status.HTTP_200_OK,
    summary="Refresh access token",
    description="Generates a new access token using a valid refresh token.",
)
async def refresh(
    refresh_in: RefreshRequest,
    service: AuthService = Depends(get_auth_service),
):
    return await service.refresh_access_token(refresh_in)


@router.post(
    "/verify",
    response_model=UserRead,
    status_code=status.HTTP_200_OK,
    summary="Verify user account",
    description="Verifies the user account using the 6-digit confirmation code printed to the console.",
)
async def verify(
    verify_in: VerifyRequest,
    service: AuthService = Depends(get_auth_service),
):
    return await service.verify_user_code(verify_in)
