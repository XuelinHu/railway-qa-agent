from fastapi import APIRouter

from app.api.routes import (
    admin_chat,
    admin_models,
    admin_roles,
    admin_terminology,
    admin_users,
    agent,
    auth,
    chat,
    dashboard,
    health,
    models,
    terminology,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(agent.router, prefix="/agent", tags=["agent"])
api_router.include_router(terminology.router, prefix="/terminology", tags=["terminology"])
api_router.include_router(models.router, prefix="/models", tags=["models"])

# Administration console. Every collection endpoint under /admin is paginated.
api_router.include_router(dashboard.router, prefix="/admin", tags=["admin"])
api_router.include_router(admin_models.router, prefix="/admin/models", tags=["admin"])
api_router.include_router(admin_users.router, prefix="/admin/users", tags=["admin"])
api_router.include_router(admin_roles.router, prefix="/admin/roles", tags=["admin"])
api_router.include_router(admin_chat.router, prefix="/admin", tags=["admin"])
api_router.include_router(
    admin_terminology.router, prefix="/admin/terminology", tags=["admin"]
)
