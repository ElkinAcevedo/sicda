"""Punto de entrada de la API.

Ejecutar en desarrollo:
    uvicorn app.main:app --reload
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.dependencias import registrar_modelo_activo
from app.api.errores import registrar_manejadores
from app.api.v1.router import api_router
from app.clasificacion import cargar_catalogo, cargar_servicio
from app.core.config import settings
from app.db.sesion import SesionLocal, crear_tablas


@asynccontextmanager
async def ciclo_de_vida(aplicacion: FastAPI) -> AsyncIterator[None]:
    """Al iniciar: crea las tablas que falten y carga el modelo activo una sola vez.

    El catálogo de categorías se carga aunque el modelo falle: lo usan las correcciones.

    Si el modelo no se puede cargar, la API arranca igual y los endpoints de clasificación
    responden `503 MODELO_NO_DISPONIBLE`.
    """
    crear_tablas()
    servicio = cargar_servicio(settings.ruta_modelos, settings.ruta_categorias)
    if servicio is not None:
        with SesionLocal() as sesion:
            registrar_modelo_activo(sesion, servicio)
            sesion.commit()
    aplicacion.state.servicio = servicio
    aplicacion.state.catalogo = (
        servicio.catalogo if servicio is not None else cargar_catalogo(settings.ruta_categorias)
    )
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
    registrar_manejadores(aplicacion)
    aplicacion.include_router(api_router, prefix="/api/v1")
    return aplicacion


app = create_app()
