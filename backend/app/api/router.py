from fastapi import APIRouter

from app.api.routes import chat, health, terminology

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(terminology.router, prefix="/terminology", tags=["terminology"])

