from fastapi import APIRouter
from app.auth.router import router as auth_router
from app.user.router import router as user_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(user_router)
