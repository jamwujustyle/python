from fastapi import APIRouter, Request
from app.core.config import settings

router = APIRouter(prefix="/debug", tags=["Debug"])


@router.get("/routes")
async def list_routes(request: Request):
    """Lists all registered API routes with their methods and names."""
    routes = []

    def traverse_routes(route_list, prefix=""):
        for route in route_list:
            if hasattr(route, "routes"):
                # Nested/mounted router
                sub_prefix = prefix + getattr(route, "path", "")
                traverse_routes(route.routes, sub_prefix)
            elif hasattr(route, "original_router"):
                # FastAPI _IncludedRouter wrapper (modern FastAPI behavior)
                sub_prefix = prefix + getattr(route.include_context, "prefix", "")
                traverse_routes(route.original_router.routes, sub_prefix)
            else:
                path = prefix + getattr(route, "path", "")
                methods = sorted(list(getattr(route, "methods", set())))
                # Skip HEAD methods to keep the output clean if GET is present
                if "GET" in methods and "HEAD" in methods:
                    methods.remove("HEAD")
                routes.append({
                    "path": path,
                    "methods": methods,
                    "name": getattr(route, "name", None),
                })

    traverse_routes(request.app.routes)
    # Sort routes for readability
    routes.sort(key=lambda x: x["path"])
    return {"total": len(routes), "routes": routes}


@router.get("/config")
async def show_config():
    """Exposes non-sensitive runtime configuration values."""
    return {
        "project_name": settings.PROJECT_NAME,
        "debug": settings.DEBUG,
        "api_version": settings.API_V1_STR,
        "cors_origins": settings.BACKEND_CORS_ORIGINS,
        "access_token_expire_minutes": settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        "refresh_token_expire_days": settings.REFRESH_TOKEN_EXPIRE_DAYS,
        "jwt_algorithm": settings.JWT_ALGORITHM,
    }


@router.get("/health")
async def deep_health():
    """Extended health check with runtime metadata."""
    import sys
    import platform
    return {
        "status": "healthy",
        "python_version": sys.version,
        "platform": platform.platform(),
        "debug": settings.DEBUG,
    }
