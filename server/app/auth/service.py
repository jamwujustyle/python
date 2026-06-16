import random
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.user.models import User, UserRole
from app.user.service import UserService
from app.user.schemas import UserCreate
from app.auth.schemas import LoginRequest, RefreshRequest, Token, VerifyRequest
from app.logging_config import logger


def generate_verification_code() -> str:
    """Generate a random 6-digit numeric string."""
    return f"{random.randint(100000, 999999)}"


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_service = UserService(db)

    async def register_user(self, user_in: UserCreate) -> User:
        """
        Register a new user, checking if the email is unique.
        Generates an email verification code and prints it to the console (for development).
        """
        existing_user = await self.user_service.get_user_by_email(user_in.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this email address already exists.",
            )

        hashed_password = get_password_hash(user_in.password)
        code = generate_verification_code()
        # Code is valid for 24 hours
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

        db_user = User(
            email=user_in.email,
            hashed_password=hashed_password,
            first_name=user_in.first_name,
            last_name=user_in.last_name,
            role=UserRole.USER,  # Default role is user
            is_verified=False,
            verification_code=code,
            verification_code_expires_at=expires_at,
        )

        self.db.add(db_user)
        await self.db.commit()
        await self.db.refresh(db_user)

        # NOTE: [PRODUCTION SCALING EXPLANATION]
        # In a production environment, we would implement the verification delivery as follows:
        # 1. Asynchronous Task Dispatch: Instead of blocking the HTTP request or printing to console,
        #    we would trigger a Celery background task (e.g. send_verification_email.delay(db_user.email, code)).
        # 2. Integration with Notification Gateways: The Celery task would interface with:
        #    - Email: SMTP servers or third-party APIs like SendGrid, Mailgun, Amazon SES, or Postmark.
        #    - SMS: SMS gateways like Twilio, MessageBird, or Vonage.
        # 3. Cache Storage (Redis): To prevent database bloat, verification codes can be cached in Redis
        #    with a TTL of 24 hours (e.g., redis.setex(f"verify:{email}", 86400, code)) instead of saving
        #    them on the SQL User table.
        # 4. Security & Rate Limiting: Implement IP and email-based rate limits (using Redis token bucket)
        #    on the signup and verify endpoints to prevent malicious actors from spamming notification APIs.
        verification_message = (
            "\n"
            "========================================================================\n"
            f" [MOCK VERIFICATION EMAIL SENT]\n"
            f" To: {db_user.email}\n"
            f" Code: {code}\n"
            f" Expires At: {expires_at.isoformat()}\n"
            "========================================================================\n"
        )
        print(verification_message, flush=True)
        logger.info(f"Verification code generated for {db_user.email}")

        return db_user

    async def authenticate_user(self, login_in: LoginRequest) -> Token:
        """
        Authenticate a user using their email and password.
        Returns access and refresh tokens upon success.
        """
        user = await self.user_service.get_user_by_email(login_in.email)
        if not user or not verify_password(login_in.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Generate tokens
        access_token = create_access_token(subject=str(user.id))
        refresh_token = create_refresh_token(subject=str(user.id))

        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
        )

    async def refresh_access_token(self, refresh_in: RefreshRequest) -> Token:
        """
        Validate the refresh token and return a new access token.
        """
        payload = decode_token(refresh_in.refresh_token)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token.",
            )

        token_type = payload.get("type")
        if token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type. Refresh token required.",
            )

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token payload is invalid. Subject missing.",
            )

        user = await self.user_service.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User associated with this refresh token does not exist.",
            )

        # Issue a new access token, reuse the refresh token
        new_access_token = create_access_token(subject=str(user.id))

        return Token(
            access_token=new_access_token,
            refresh_token=refresh_in.refresh_token,
            token_type="bearer",
        )

    async def verify_user_code(self, verify_in: VerifyRequest) -> User:
        """
        Verify the user using the code sent to their email.
        If matching and not expired, updates the status to verified.
        """
        user = await self.user_service.get_user_by_email(verify_in.email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email address does not exist.",
            )

        if user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email address is already verified.",
            )

        if not user.verification_code or user.verification_code != verify_in.code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid verification code.",
            )

        now = datetime.now(timezone.utc)
        # Ensure verification_code_expires_at is timezone-aware
        expires_at = user.verification_code_expires_at
        if expires_at and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at and now > expires_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification code has expired. Please sign up or request a new code.",
            )

        # Mark user as verified
        user.is_verified = True
        user.verification_code = None
        user.verification_code_expires_at = None

        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        logger.info(f"User {user.email} successfully verified.")
        return user
