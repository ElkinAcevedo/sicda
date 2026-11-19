"""Tablas del sistema (sección 5.2 del documento de diseño).

Un `Documento` tiene una o más `Clasificacion`; cada clasificación pertenece a un `Modelo`
y puede tener una `Correccion`. Solo un modelo puede tener `activo = true`.

Las fechas se guardan en UTC sin zona horaria (SQLite no la conserva).

Campos agregados respecto al diseño, necesarios para reconstruir la respuesta de
`GET /clasificaciones/{id}` sin volver a clasificar: `Documento.fuente_texto`,
`Documento.palabras_clave`, `Clasificacion.conf_conjunta` y `Clasificacion.advertencias`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

TIPOS_DOCUMENTO = ("pdf", "docx", "txt", "texto")


def ahora_utc() -> datetime:
    """Fecha y hora actual en UTC, sin zona horaria."""
    return datetime.now(UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSON, list[Any]: JSON}


class Documento(Base):
    """Lo que el usuario cargó. El hash evita guardar dos veces el mismo contenido."""

    __tablename__ = "documento"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre_archivo: Mapped[str | None] = mapped_column(String(255))
    tipo: Mapped[str] = mapped_column(String(10))  # pdf, docx, txt o texto
    titulo: Mapped[str | None] = mapped_column(String(500))
    texto_extraido: Mapped[str] = mapped_column(Text)
    fuente_texto: Mapped[str] = mapped_column(String(20))  # abstract, inicio o texto_completo
    idioma: Mapped[str] = mapped_column(String(10))
    num_terminos: Mapped[int]
    palabras_clave: Mapped[list[Any]] = mapped_column(default=list)
    hash_sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    creado_en: Mapped[datetime] = mapped_column(default=ahora_utc)

    clasificaciones: Mapped[list[Clasificacion]] = relationship(
        back_populates="documento", cascade="all, delete-orphan"
    )


class Modelo(Base):
    """Registro de un modelo entrenado. Los artefactos viven en `models/`, no en la base."""

    __tablename__ = "modelo"
    __table_args__ = (
        UniqueConstraint("algoritmo", "version", name="uq_modelo_algoritmo_version"),
        # Garantiza en la base que haya como máximo un modelo activo.
        Index(
            "ux_modelo_un_activo",
            "activo",
            unique=True,
            sqlite_where=text("activo = 1"),
            postgresql_where=text("activo"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100))
    algoritmo: Mapped[str] = mapped_column(String(50))
    version: Mapped[str] = mapped_column(String(50))
    ruta_artefacto: Mapped[str] = mapped_column(String(500))
    hiperparametros: Mapped[dict[str, Any]] = mapped_column(default=dict)
    metricas: Mapped[dict[str, Any]] = mapped_column(default=dict)
    activo: Mapped[bool] = mapped_column(default=False)
    entrenado_en: Mapped[datetime | None]

    clasificaciones: Mapped[list[Clasificacion]] = relationship(back_populates="modelo")


class Clasificacion(Base):
    """Resultado de una predicción."""

    __tablename__ = "clasificacion"

    id: Mapped[int] = mapped_column(primary_key=True)
    documento_id: Mapped[int] = mapped_column(ForeignKey("documento.id", ondelete="CASCADE"))
    modelo_id: Mapped[int] = mapped_column(ForeignKey("modelo.id"))
    dominio: Mapped[str] = mapped_column(String(100), index=True)
    conf_dominio: Mapped[float]
    area: Mapped[str] = mapped_column(String(200))
    conf_area: Mapped[float]
    conf_conjunta: Mapped[float]
    # {"dominio": [{"nombre", "confianza"}, ...], "area": [...]}
    alternativas: Mapped[dict[str, Any]] = mapped_column(default=dict)
    terminos_clave: Mapped[list[Any]] = mapped_column(default=list)
    advertencias: Mapped[list[Any]] = mapped_column(default=list)
    requiere_revision: Mapped[bool] = mapped_column(index=True)
    tiempo_ms: Mapped[float]
    creado_en: Mapped[datetime] = mapped_column(default=ahora_utc, index=True)

    documento: Mapped[Documento] = relationship(back_populates="clasificaciones")
    modelo: Mapped[Modelo] = relationship(back_populates="clasificaciones")
    correccion: Mapped[Correccion | None] = relationship(
        back_populates="clasificacion", cascade="all, delete-orphan", uselist=False
    )


class Correccion(Base):
    """Retroalimentación del usuario sobre una clasificación (RF-12)."""

    __tablename__ = "correccion"

    id: Mapped[int] = mapped_column(primary_key=True)
    clasificacion_id: Mapped[int] = mapped_column(
        ForeignKey("clasificacion.id", ondelete="CASCADE"), unique=True
    )
    dominio_correcto: Mapped[str] = mapped_column(String(100))
    area_correcta: Mapped[str | None] = mapped_column(String(200))
    comentario: Mapped[str | None] = mapped_column(Text)
    creado_en: Mapped[datetime] = mapped_column(default=ahora_utc)

    clasificacion: Mapped[Clasificacion] = relationship(back_populates="correccion")
