"""GET /api/v1/categorias, /modelos y /modelos/{id}/metricas (RF-11)."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencias import exigir_catalogo, obtener_calculadora
from app.api.errores import documentar_errores
from app.clasificacion import Catalogo
from app.clasificacion.registro import CalculadoraMetricas
from app.db import repositorios as repo
from app.db.sesion import obtener_sesion
from app.schemas.modelos import RespuestaCategorias, RespuestaMetricas, RespuestaModelo

router = APIRouter()

Sesion = Annotated[Session, Depends(obtener_sesion)]


@router.get(
    "/categorias",
    response_model=RespuestaCategorias,
    summary="Dominios y áreas",
    tags=["categorías"],
    responses=documentar_errores(503),
)
def listar_categorias(catalogo: Annotated[Catalogo, Depends(exigir_catalogo)]):
    """Los 7 dominios y sus áreas (136), con los documentos de cada una en WOS-46985."""
    return RespuestaCategorias.desde_categorias(catalogo.categorias)


@router.get(
    "/modelos",
    response_model=list[RespuestaModelo],
    summary="Modelos entrenados",
    tags=["modelos"],
)
def listar_modelos(sesion: Sesion):
    """Primero el activo y luego los demás, con sus métricas resumidas."""
    return [RespuestaModelo.desde_registro(m) for m in repo.listar_modelos(sesion)]


@router.get(
    "/modelos/{modelo_id}/metricas",
    response_model=RespuestaMetricas,
    summary="Métricas detalladas de un modelo",
    tags=["modelos"],
    responses=documentar_errores(400, 404, 503),
)
def obtener_metricas(
    modelo_id: int,
    sesion: Sesion,
    calculadora: Annotated[CalculadoraMetricas, Depends(obtener_calculadora)],
    particion: Annotated[
        Literal["validacion", "prueba"] | None,
        Query(description="Por defecto, prueba si el modelo se evaluó en test"),
    ] = None,
):
    """Métricas por clase y matrices de confusión de dominio y de área por dominio."""
    modelo = repo.obtener_modelo(sesion, modelo_id)
    return RespuestaMetricas.desde_calculo(modelo, calculadora.calcular(modelo, particion))
