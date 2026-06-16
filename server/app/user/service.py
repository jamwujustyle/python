import uuid
from typing import List, Optional, Union
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import get_password_hash
from app.user.models import User, UserRole
from app.user.schemas import UserCreate, UserUpdate


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_by_id(self, user_id: Union[uuid.UUID, str]) -> Optional[User]:
        """Retrieve a user by their UUID."""
        if isinstance(user_id, str):
            try:
                user_id = uuid.UUID(user_id)
            except ValueError:
                return None
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Retrieve a user by their email address."""
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        """Retrieve a list of users with pagination."""
        result = await self.db.execute(select(User).offset(skip).limit(limit))
        return list(result.scalars().all())

    async def create_user(self, user_in: UserCreate) -> User:
        """Create a new user with hashed password and unverified status."""
        hashed_password = get_password_hash(user_in.password)
        db_user = User(
            email=user_in.email,
            hashed_password=hashed_password,
            first_name=user_in.first_name,
            last_name=user_in.last_name,
            is_verified=False,
        )
        self.db.add(db_user)
        await self.db.commit()
        await self.db.refresh(db_user)
        return db_user

    async def update_user(self, db_user: User, user_in: UserUpdate) -> User:
        """Partially update user details, hashing the password if it is provided."""
        update_data = user_in.model_dump(exclude_unset=True)
        if "password" in update_data:
            update_data["hashed_password"] = get_password_hash(update_data.pop("password"))
        
        for key, value in update_data.items():
            setattr(db_user, key, value)
            
        self.db.add(db_user)
        await self.db.commit()
        await self.db.refresh(db_user)
        return db_user

    async def delete_user(self, user_id: Union[uuid.UUID, str]) -> bool:
        """Delete a user by their ID."""
        db_user = await self.get_user_by_id(user_id)
        if not db_user:
            return False
        await self.db.delete(db_user)
        await self.db.commit()
        return True

    async def promote_user(self, db_user: User) -> User:
        """Promote a user to Admin role."""
        db_user.role = UserRole.ADMIN
        self.db.add(db_user)
        await self.db.commit()
        await self.db.refresh(db_user)
        return db_user

    async def demote_user(self, db_user: User) -> User:
        """Demote an admin user to standard User role."""
        db_user.role = UserRole.USER
        self.db.add(db_user)
        await self.db.commit()
        await self.db.refresh(db_user)
        return db_user
