"""Salida de `/categorias` y `/modelos` (RF-11, sección 7.1 del documento de diseño)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.clasificacion.registro import MetricasDetalladas, resumen
from app.db.modelos import Modelo

# --- Categorías ---------------------------------------------------------------------------


class AreaCategoria(BaseModel):
    id: int
    nombre: str
    documentos: int | None = None


class DominioCategoria(BaseModel):
    id: int
    codigo: str
    nombre: str
    nombre_es: str | None = None
    documentos: int | None = None
    areas: list[AreaCategoria]


class RespuestaCategorias(BaseModel):
    total_dominios: int
    total_areas: int
    dominios: list[DominioCategoria]

    @classmethod
    def desde_categorias(cls, categorias: dict[str, Any]) -> RespuestaCategorias:
        dominios = [DominioCategoria.model_validate(d) for d in categorias["dominios"]]
        return cls(
            total_dominios=len(dominios),
            total_areas=sum(len(d.areas) for d in dominios),
            dominios=dominios,
        )


# --- Modelos ------------------------------------------------------------------------------


class ResumenMetricas(BaseModel):
    """Cifras clave por nivel (F1-macro) y accuracy jerárquica."""

    f1_dominio: float | None
    f1_area: float | None
    f1_jerarquico: float | None
    accuracy_jerarquica: float | None


class RespuestaModelo(BaseModel):
    id: int
    nombre: str
    algoritmo: str
    tipo: str
    version: str
    activo: bool
    entrenado_en: datetime | None
    hiperparametros: dict[str, Any]
    validacion: ResumenMetricas | None
    prueba: ResumenMetricas | None
    umbrales: dict[str, float] | None
    tiempo_ms: float | None
    porcentaje_revision_validacion: float | None
    variantes: dict[str, ResumenMetricas | None]

    @classmethod
    def desde_registro(cls, modelo: Modelo) -> RespuestaModelo:
        metricas = modelo.metricas or {}
        return cls(
            id=modelo.id,
            nombre=modelo.nombre,
            algoritmo=modelo.algoritmo,
            tipo=metricas.get("tipo", "plano"),
            version=modelo.version,
            activo=modelo.activo,
            entrenado_en=modelo.entrenado_en,
            hiperparametros=modelo.hiperparametros or {},
            validacion=resumen(metricas.get("validacion")),
            prueba=resumen(metricas.get("prueba")),
            umbrales=metricas.get("umbrales"),
            tiempo_ms=metricas.get("tiempo_ms"),
            porcentaje_revision_validacion=metricas.get("porcentaje_revision_validacion"),
            variantes=metricas.get("variantes") or {},
        )


class MetricasNivel(BaseModel):
    accuracy: float
    precision_macro: float
    recall_macro: float
    f1_macro: float
    precision_ponderado: float
    recall_ponderado: float
    f1_ponderado: float


class MetricaClase(BaseModel):
    id: int
    nombre: str
    precision: float
    recall: float
    f1: float
    soporte: int
    dominio: str | None = None  # solo en las áreas


class MetricasPorClase(BaseModel):
    dominio: list[MetricaClase]
    area: list[MetricaClase]


class MatrizConfusion(BaseModel):
    """Filas = clase real (`etiquetas`), columnas = clase predicha (`columnas`)."""

    etiquetas: list[str]
    columnas: list[str]
    matriz: list[list[int]]


class MatrizArea(MatrizConfusion):
    dominio: str


class Confusion(BaseModel):
    dominio: MatrizConfusion
    area_por_dominio: list[MatrizArea]


class Revision(BaseModel):
    umbrales: dict[str, float]
    porcentaje: float
    accuracy_aceptados: float | None


class ModeloResumido(BaseModel):
    id: int
    nombre: str
    version: str
    tipo: str


class RespuestaMetricas(BaseModel):
    modelo: ModeloResumido
    particion: str
    particiones_disponibles: list[str]
    documentos: int
    metricas: dict[str, MetricasNivel]
    por_clase: MetricasPorClase
    confusion: Confusion
    revision: Revision

    @classmethod
    def desde_calculo(cls, modelo: Modelo, detalle: MetricasDetalladas) -> RespuestaMetricas:
        dominio = detalle.confusion_dominio
        return cls(
            modelo=ModeloResumido(
                id=modelo.id,
                nombre=modelo.nombre,
                version=modelo.version,
                tipo=(modelo.metricas or {}).get("tipo", "plano"),
            ),
            particion=detalle.particion,
            particiones_disponibles=detalle.particiones_disponibles,
            documentos=detalle.documentos,
            metricas=detalle.metricas,
            por_clase=detalle.por_clase,
            confusion=Confusion(
                dominio=MatrizConfusion(
                    etiquetas=dominio["etiquetas"],
                    columnas=dominio["etiquetas"],
                    matriz=dominio["matriz"],
                ),
                area_por_dominio=detalle.confusion_area,
            ),
            revision=detalle.revision,
        )
