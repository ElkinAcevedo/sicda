"""Punto de entrada de la API.

Ejecutar en desarrollo:
    uvicorn app.main:app --reload
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.v1.router import api_router
from app.core.config import settings
from app.db.sesion import crear_tablas


@asynccontextmanager
async def ciclo_de_vida(_aplicacion: FastAPI) -> AsyncIterator[None]:
    """Al iniciar: crea las tablas que falten en la base de datos."""
    crear_tablas()
    yield


def create_app() -> FastAPI:
    """Construye la aplicación FastAPI con su configuración y rutas."""
    aplicacion = FastAPI(
        title="SICDA · Sistema Inteligente de Clasificación de Documentos Académicos",
        description="Clasifica documentos académicos por dominio y área temática (WOS-46985).",
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=ciclo_de_vida,
    )
    aplicacion.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origenes_cors,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    aplicacion.include_router(api_router, prefix="/api/v1")
    return aplicacion


app = create_app()
