"""Entrada y salida de `/clasificaciones` (secciones 7.1 y 7.2 del documento de diseño)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.db.modelos import Clasificacion, Correccion
from app.db.repositorios import Pagina


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


class EntradaCorreccion(BaseModel):
    dominio_correcto: str = Field(min_length=1, max_length=100, examples=["Computer Science"])
    area_correcta: str | None = Field(
        default=None, min_length=1, max_length=200, examples=["Computer vision"]
    )
    comentario: str | None = Field(default=None, max_length=2000)


class CorreccionRespuesta(BaseModel):
    dominio_correcto: str
    area_correcta: str | None
    comentario: str | None
    creado_en: datetime

    @classmethod
    def desde_registro(cls, registro: Correccion | None) -> CorreccionRespuesta | None:
        if registro is None:
            return None
        return cls(
            dominio_correcto=registro.dominio_correcto,
            area_correcta=registro.area_correcta,
            comentario=registro.comentario,
            creado_en=registro.creado_en,
        )


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
    correccion: CorreccionRespuesta | None = None

    @classmethod
    def desde_registro(cls, registro: Clasificacion) -> RespuestaClasificacion:
        """Reconstruye la respuesta a partir de lo guardado (sin volver a clasificar)."""
        return cls(documento=_documento(registro), **_campos_comunes(registro))


class DocumentoDetalle(DocumentoClasificado):
    tipo: str
    texto_extraido: str
    palabras_clave: list[str]


class RespuestaDetalle(RespuestaClasificacion):
    """`GET /clasificaciones/{id}`: la clasificación con el texto que se clasificó."""

    documento: DocumentoDetalle

    @classmethod
    def desde_registro(cls, registro: Clasificacion) -> RespuestaDetalle:
        documento = registro.documento
        detalle = DocumentoDetalle(
            **_documento(registro).model_dump(),
            tipo=documento.tipo,
            texto_extraido=documento.texto_extraido,
            palabras_clave=documento.palabras_clave or [],
        )
        return cls(documento=detalle, **_campos_comunes(registro))


class DocumentoResumido(BaseModel):
    titulo: str | None
    nombre_archivo: str | None
    tipo: str


class ResumenClasificacion(BaseModel):
    """Una fila del historial (fecha, documento, dominio, área, confianza y estado)."""

    id: int
    creado_en: datetime
    documento: DocumentoResumido
    dominio: str
    area: str
    confianza_dominio: float
    confianza_conjunta: float
    requiere_revision: bool
    correccion: CorreccionRespuesta | None

    @classmethod
    def desde_registro(cls, registro: Clasificacion) -> ResumenClasificacion:
        documento = registro.documento
        return cls(
            id=registro.id,
            creado_en=registro.creado_en,
            documento=DocumentoResumido(
                titulo=documento.titulo,
                nombre_archivo=documento.nombre_archivo,
                tipo=documento.tipo,
            ),
            dominio=registro.dominio,
            area=registro.area,
            confianza_dominio=registro.conf_dominio,
            confianza_conjunta=registro.conf_conjunta,
            requiere_revision=registro.requiere_revision,
            correccion=CorreccionRespuesta.desde_registro(registro.correccion),
        )


class PaginaClasificaciones(BaseModel):
    elementos: list[ResumenClasificacion]
    total: int
    pagina: int
    tamano: int
    paginas: int

    @classmethod
    def desde_pagina(cls, pagina: Pagina) -> PaginaClasificaciones:
        return cls(
            elementos=[ResumenClasificacion.desde_registro(c) for c in pagina.elementos],
            total=pagina.total,
            pagina=pagina.pagina,
            tamano=pagina.tamano,
            paginas=pagina.paginas,
        )


def _documento(registro: Clasificacion) -> DocumentoClasificado:
    documento = registro.documento
    return DocumentoClasificado(
        titulo=documento.titulo,
        nombre_archivo=documento.nombre_archivo,
        idioma=documento.idioma,
        num_terminos=documento.num_terminos,
        fuente_texto=documento.fuente_texto,
    )


def _campos_comunes(registro: Clasificacion) -> dict:
    """Todo lo de la respuesta salvo `documento`, que cambia entre el resumen y el detalle."""
    alternativas = registro.alternativas or {}
    return dict(
        id=registro.id,
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
        correccion=CorreccionRespuesta.desde_registro(registro.correccion),
    )
