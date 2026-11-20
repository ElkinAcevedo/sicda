"""Punto de entrada de la API.

Ejecutar en desarrollo:
    uvicorn app.main:app --reload
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.dependencias import registrar_modelo_activo
from app.api.errores import registrar_manejadores
from app.api.v1.router import api_router
from app.clasificacion import cargar_catalogo, cargar_servicio
from app.clasificacion.registro import CalculadoraMetricas, sincronizar_modelos
from app.core.config import settings
from app.db.sesion import SesionLocal, crear_tablas

logger = logging.getLogger(__name__)


@asynccontextmanager
async def ciclo_de_vida(aplicacion: FastAPI) -> AsyncIterator[None]:
    """Al iniciar: crea las tablas que falten y carga el modelo activo una sola vez.

    El catálogo de categorías se carga aunque el modelo falle: lo usan las correcciones.

    Si el modelo no se puede cargar, la API arranca igual y los endpoints de clasificación
    responden `503 MODELO_NO_DISPONIBLE`.
    """
    crear_tablas()
    servicio = cargar_servicio(settings.ruta_modelos, settings.ruta_categorias)
    _registrar_modelos(servicio)
    catalogo = (
        servicio.catalogo if servicio is not None else cargar_catalogo(settings.ruta_categorias)
    )
    aplicacion.state.servicio = servicio
    aplicacion.state.catalogo = catalogo
    aplicacion.state.calculadora = (
        CalculadoraMetricas(settings.ruta_modelos, settings.ruta_datos, catalogo)
        if catalogo is not None
        else None
    )
    yield


def _registrar_modelos(servicio) -> None:
    """Registra en la tabla `modelo` los modelos de `models/` y deja activo el cargado."""
    with SesionLocal() as sesion:
        try:
            info_activo = servicio.info if servicio is not None else None
            sincronizar_modelos(sesion, settings.ruta_modelos, info_activo)
            if servicio is not None:
                registrar_modelo_activo(sesion, servicio)
            sesion.commit()
        except Exception:  # un metadatos.json roto no debe impedir que la API arranque
            sesion.rollback()
            logger.exception("No se pudieron registrar los modelos de %s", settings.ruta_modelos)


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
