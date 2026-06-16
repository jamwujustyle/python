import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from app.user.models import UserRole


class UserBase(BaseModel):
    email: EmailStr
    first_name: Optional[str] = Field(None, max_length=50)
    last_name: Optional[str] = Field(None, max_length=50)


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128)


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    first_name: Optional[str] = Field(None, max_length=50)
    last_name: Optional[str] = Field(None, max_length=50)
    password: Optional[str] = Field(None, min_length=8, max_length=128)


class UserUpdateRole(BaseModel):
    role: UserRole


class UserRead(UserBase):
    id: uuid.UUID
    role: UserRole
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    # Included in development/testing for UI convenience; set to None once verified
    verification_code: Optional[str] = None

    class Config:
        from_attributes = True
