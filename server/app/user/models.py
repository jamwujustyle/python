import uuid
from enum import Enum
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, String, UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    # Primary key: DB automatically creates a unique index. No need for index=True.
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    
    # Unique constraint: DB automatically creates a unique index. No need for index=True.
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    first_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # Not indexed: low-cardinality/selectivity fields. Indexing would be ignored by the query planner.
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole),
        default=UserRole.USER,
        nullable=False,
    )
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Not indexed: transient code lookup is handled via email-first filtering.
    verification_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    verification_code_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Not indexed: created_at/updated_at can be indexed later if sorting large datasets becomes a query bottleneck.
    # We avoid indexing updated_at due to the high write/update penalty on a frequently modified timestamp.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
