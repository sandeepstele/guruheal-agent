from fastapi import APIRouter

from .chat import router as chat_router

v1_router = APIRouter()
v1_router.include_router(chat_router, tags=["chat"], prefix="/chat")
