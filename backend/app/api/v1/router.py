"""Agrupa los routers de todos los recursos de la versión 1."""

from fastapi import APIRouter

from app.api.v1.endpoints import clasificaciones, modelos, salud

api_router = APIRouter()
api_router.include_router(salud.router, tags=["salud"])
api_router.include_router(modelos.router)
api_router.include_router(
    clasificaciones.router, prefix="/clasificaciones", tags=["clasificaciones"]
)
