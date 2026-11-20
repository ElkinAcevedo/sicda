"""Entrada y salida de `POST /clasificaciones/*` (sección 7.2 del documento de diseño)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.db.modelos import Clasificacion


class EntradaTexto(BaseModel):
    titulo: str | None = Field(default=None, max_length=500, examples=["A lightweight CNN"])
    texto: str = Field(
        min_length=1,
        max_length=100_000,
        description="Resumen (abstract) en inglés; se necesitan al menos 20 términos.",
        examples=[
            "Convolutional neural networks have become the dominant approach for image "
            "recognition. In this work we propose a lightweight architecture that reduces the "
            "number of parameters while keeping accuracy on standard benchmarks."
        ],
    )


class DocumentoClasificado(BaseModel):
    titulo: str | None
    nombre_archivo: str | None
    idioma: str
    num_terminos: int
    fuente_texto: str


class AlternativaNivel(BaseModel):
    nombre: str
    confianza: float


class NivelClasificado(BaseModel):
    nombre: str
    confianza: float
    alternativas: list[AlternativaNivel]


class TerminoClave(BaseModel):
    termino: str
    peso: float


class AdvertenciaRespuesta(BaseModel):
    codigo: str
    mensaje: str


class ModeloUsado(BaseModel):
    nombre: str
    version: str


class RespuestaClasificacion(BaseModel):
    id: int
    documento: DocumentoClasificado
    dominio: NivelClasificado
    area: NivelClasificado
    confianza_conjunta: float
    requiere_revision: bool
    terminos_clave: list[TerminoClave]
    advertencias: list[AdvertenciaRespuesta]
    modelo: ModeloUsado
    tiempo_ms: float
    creado_en: datetime

    @classmethod
    def desde_registro(cls, registro: Clasificacion) -> RespuestaClasificacion:
        """Reconstruye la respuesta a partir de lo guardado (sin volver a clasificar)."""
        documento = registro.documento
        alternativas = registro.alternativas or {}
        return cls(
            id=registro.id,
            documento=DocumentoClasificado(
                titulo=documento.titulo,
                nombre_archivo=documento.nombre_archivo,
                idioma=documento.idioma,
                num_terminos=documento.num_terminos,
                fuente_texto=documento.fuente_texto,
            ),
            dominio=NivelClasificado(
                nombre=registro.dominio,
                confianza=registro.conf_dominio,
                alternativas=alternativas.get("dominio", []),
            ),
            area=NivelClasificado(
                nombre=registro.area,
                confianza=registro.conf_area,
                alternativas=alternativas.get("area", []),
            ),
            confianza_conjunta=registro.conf_conjunta,
            requiere_revision=registro.requiere_revision,
            terminos_clave=registro.terminos_clave or [],
            advertencias=registro.advertencias or [],
            modelo=ModeloUsado(nombre=registro.modelo.nombre, version=registro.modelo.version),
            tiempo_ms=registro.tiempo_ms,
            creado_en=registro.creado_en,
        )
