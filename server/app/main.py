import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from app.core.config import settings
from app.core.database import init_db, SessionLocal
from app.core.security import get_password_hash
from app.user.models import User, UserRole
from app.api.v1 import api_router
from app.logging_config import logger


async def _init_db_with_retry(retries: int = 10, delay: float = 3.0) -> None:
    """
    Attempts to initialize the DB, retrying on transient connection failures.
    Docker's internal DNS can return EAI_AGAIN immediately after container start
    even when depends_on: service_healthy is satisfied.
    """
    for attempt in range(1, retries + 1):
        try:
            await init_db()
            return
        except Exception as exc:
            if attempt == retries:
                logger.error(f"Database connection failed after {retries} attempts. Giving up.")
                raise
            logger.warning(
                f"Database not ready (attempt {attempt}/{retries}): {exc}. "
                f"Retrying in {delay}s..."
            )
            await asyncio.sleep(delay)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI Lifespan handler.
    Performs database initialization and seeds the default admin user.
    """
    logger.info("Initializing database...")
    await _init_db_with_retry()

    logger.info("Checking for default admin user...")
    async with SessionLocal() as db:
        admin_email = "admin@example.com"
        result = await db.execute(select(User).where(User.email == admin_email))
        admin = result.scalar_one_or_none()
        if not admin:
            hashed_pw = get_password_hash("adminpassword")
            admin_user = User(
                email=admin_email,
                hashed_password=hashed_pw,
                first_name="Default",
                last_name="Admin",
                role=UserRole.ADMIN,
                is_verified=True,  # Admins are verified by default
            )
            db.add(admin_user)
            await db.commit()
            logger.info("Default admin user created successfully.")
            logger.info(f"Admin Credentials -> Email: {admin_email} | Password: adminpassword")
        else:
            logger.info("Default admin user already exists.")

    yield
    logger.info("Shutting down application...")



app = FastAPI(
    title="Users API — Identity & Access Management",
    description=(
        "Modular monolith backend service for user lifecycle management.\n\n"
        "## Authentication\n"
        "JWT-based authentication with short-lived access tokens and long-lived refresh tokens. "
        "Passwords are hashed with **bcrypt**.\n\n"
        "## User Management\n"
        "Full CRUD operations on user profiles with role-based access control (RBAC). "
        "Admin-restricted endpoints for listing, lookup, and deletion.\n\n"
        "## Verification\n"
        "Email verification flow with 6-digit codes. Unverified accounts are automatically "
        "purged after 48 hours via a Celery Beat scheduled task.\n\n"
        "## Infrastructure\n"
        "PostgreSQL · Redis · Celery · Docker Compose"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Register global exception handlers
from app.core.exception_handlers import register_exception_handlers
register_exception_handlers(app)

# Set up CORS middleware
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Register routers:
# 1. Root-level to support exact specification requirements (e.g. /auth/signup, /me)
app.include_router(api_router)

# 2. Versioned-level to align with standard API architecture practices (/api/v1/auth/signup, /api/v1/me)
app.include_router(api_router, prefix=settings.API_V1_STR)

# 3. Debug routes — only available when DEBUG=True (disabled in production)
if settings.DEBUG:
    from app.api.debug.router import router as debug_router
    app.include_router(debug_router)


@app.get("/", tags=["Health Check"])
async def root():
    """Health check endpoint containing basic API metadata."""
    return {
        "status": "healthy",
        "project": settings.PROJECT_NAME,
        "docs_url": "/docs",
        "redoc_url": "/redoc",
    }
