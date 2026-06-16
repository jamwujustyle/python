from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: Optional[str] = None
    exp: Optional[int] = None
    type: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class VerifyRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)
