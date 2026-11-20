"""Dependencias compartidas por los endpoints."""

from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from app.api.errores import ModeloNoDisponible
from app.clasificacion import ServicioClasificacion
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
