"""Dependencias compartidas por los endpoints."""

from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from app.api.errores import CategoriasNoDisponibles, ModeloNoDisponible
from app.clasificacion import Catalogo, ServicioClasificacion
from app.clasificacion.registro import CalculadoraMetricas
from app.db import repositorios as repo
from app.db.modelos import Modelo


def obtener_servicio(request: Request) -> ServicioClasificacion:
    """El servicio cargado al iniciar la API; si no hay modelo, responde 503."""
    servicio = getattr(request.app.state, "servicio", None)
    if servicio is None:
        raise ModeloNoDisponible(
            "No hay un modelo de clasificación cargado. Revise que exista models/activo.json "
            "y reinicie la API."
        )
    return servicio


def obtener_catalogo(request: Request) -> Catalogo | None:
    """Catálogo de dominios y áreas; `None` si `categorias.json` no se pudo cargar."""
    return getattr(request.app.state, "catalogo", None)


def exigir_catalogo(request: Request) -> Catalogo:
    catalogo = obtener_catalogo(request)
    if catalogo is None:
        raise CategoriasNoDisponibles(
            "No se pudo leer el catálogo de categorías (categorias.json). Revise "
            "CLASIFICADOR_RUTA_CATEGORIAS y reinicie la API."
        )
    return catalogo


def obtener_calculadora(request: Request) -> CalculadoraMetricas:
    calculadora = getattr(request.app.state, "calculadora", None)
    if calculadora is None:
        exigir_catalogo(request)  # la calculadora solo falta si falta el catálogo
        raise CategoriasNoDisponibles("Las métricas detalladas no están disponibles.")
    return calculadora


def registrar_modelo_activo(sesion: Session, servicio: ServicioClasificacion) -> Modelo:
    """Asegura que el modelo cargado esté registrado en la tabla `modelo` como el activo."""
    activo = repo.obtener_modelo_activo(sesion)
    if (
        activo is not None
        and activo.algoritmo == servicio.algoritmo
        and activo.version == servicio.version
    ):
        return activo
    return repo.registrar_modelo(
        sesion,
        nombre=servicio.nombre,
        algoritmo=servicio.algoritmo,
        version=servicio.version,
        ruta_artefacto=servicio.ruta_artefacto,
        hiperparametros=servicio.hiperparametros,
        metricas=servicio.metricas,
        entrenado_en=servicio.entrenado_en,
        activar=True,
    )
