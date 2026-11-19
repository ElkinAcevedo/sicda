"""Operaciones de lectura y escritura sobre las tablas, sin lógica HTTP.

Cada función recibe la `Session` y no hace commit salvo que se indique: el que llama
decide cuándo confirmar la transacción (normalmente, una vez por solicitud).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session, joinedload

from app.db.modelos import Clasificacion, Correccion, Documento, Modelo, ahora_utc


class NoEncontrado(LookupError):  # noqa: N818 - nombre en español (código NO_ENCONTRADO)
    """La clasificación o el modelo pedido no existe."""


# --- Documentos ---------------------------------------------------------------------------


def calcular_hash(contenido: bytes | str) -> str:
    """SHA-256 en hexadecimal. El texto pegado se normaliza (espacios) antes de calcularlo."""
    if isinstance(contenido, str):
        contenido = " ".join(contenido.split()).encode("utf-8")
    return hashlib.sha256(contenido).hexdigest()


def buscar_documento_por_hash(sesion: Session, hash_sha256: str) -> Documento | None:
    return sesion.scalar(select(Documento).where(Documento.hash_sha256 == hash_sha256))


def obtener_o_crear_documento(sesion: Session, hash_sha256: str, **campos: Any) -> Documento:
    """Devuelve el documento con ese hash o lo crea con `campos` (no reprocesa duplicados)."""
    existente = buscar_documento_por_hash(sesion, hash_sha256)
    if existente is not None:
        return existente
    documento = Documento(hash_sha256=hash_sha256, **campos)
    sesion.add(documento)
    sesion.flush()
    return documento


# --- Modelos ------------------------------------------------------------------------------


def registrar_modelo(
    sesion: Session,
    *,
    nombre: str,
    algoritmo: str,
    version: str,
    ruta_artefacto: str,
    hiperparametros: dict[str, Any] | None = None,
    metricas: dict[str, Any] | None = None,
    entrenado_en: datetime | None = None,
    activar: bool = False,
) -> Modelo:
    """Crea o actualiza el registro de (`algoritmo`, `version`). Con `activar`, lo deja activo."""
    modelo = sesion.scalar(
        select(Modelo).where(Modelo.algoritmo == algoritmo, Modelo.version == version)
    )
    if modelo is None:
        modelo = Modelo(algoritmo=algoritmo, version=version)
        sesion.add(modelo)
    modelo.nombre = nombre
    modelo.ruta_artefacto = ruta_artefacto
    modelo.hiperparametros = hiperparametros or {}
    modelo.metricas = metricas or {}
    modelo.entrenado_en = entrenado_en
    sesion.flush()
    if activar:
        activar_modelo(sesion, modelo.id)
    return modelo


def activar_modelo(sesion: Session, modelo_id: int) -> Modelo:
    """Deja `modelo_id` como único modelo activo."""
    modelo = obtener_modelo(sesion, modelo_id)
    # Primero se desactivan todos para no violar el índice único parcial.
    sesion.execute(update(Modelo).where(Modelo.activo.is_(True)).values(activo=False))
    sesion.flush()
    modelo.activo = True
    sesion.flush()
    sesion.refresh(modelo)
    return modelo


def obtener_modelo(sesion: Session, modelo_id: int) -> Modelo:
    modelo = sesion.get(Modelo, modelo_id)
    if modelo is None:
        raise NoEncontrado(f"No existe el modelo {modelo_id}.")
    return modelo


def obtener_modelo_activo(sesion: Session) -> Modelo | None:
    return sesion.scalar(select(Modelo).where(Modelo.activo.is_(True)))


def listar_modelos(sesion: Session) -> list[Modelo]:
    """Modelos registrados: primero el activo y luego los más recientes."""
    consulta = select(Modelo).order_by(Modelo.activo.desc(), Modelo.id.desc())
    return list(sesion.scalars(consulta))


# --- Clasificaciones ----------------------------------------------------------------------


def guardar_clasificacion(
    sesion: Session, documento: Documento, modelo: Modelo, **campos: Any
) -> Clasificacion:
    clasificacion = Clasificacion(documento=documento, modelo=modelo, **campos)
    sesion.add(clasificacion)
    sesion.flush()
    return clasificacion


def obtener_clasificacion(sesion: Session, clasificacion_id: int) -> Clasificacion:
    """Clasificación con su documento, modelo y corrección ya cargados."""
    consulta = (
        select(Clasificacion)
        .where(Clasificacion.id == clasificacion_id)
        .options(
            joinedload(Clasificacion.documento),
            joinedload(Clasificacion.modelo),
            joinedload(Clasificacion.correccion),
        )
    )
    clasificacion = sesion.scalar(consulta)
    if clasificacion is None:
        raise NoEncontrado(f"No existe la clasificación {clasificacion_id}.")
    return clasificacion


@dataclass
class Pagina:
    elementos: list[Clasificacion]
    total: int
    pagina: int
    tamano: int

    @property
    def paginas(self) -> int:
        return max(1, -(-self.total // self.tamano))


def _a_utc_sin_zona(valor: datetime) -> datetime:
    return valor.astimezone(UTC).replace(tzinfo=None) if valor.tzinfo else valor


def listar_clasificaciones(
    sesion: Session,
    *,
    pagina: int = 1,
    tamano: int = 20,
    dominio: str | None = None,
    desde: date | datetime | None = None,
    hasta: date | datetime | None = None,
    requiere_revision: bool | None = None,
    busqueda: str | None = None,
) -> Pagina:
    """Historial paginado, de la más reciente a la más antigua (RF-10).

    Args:
        desde, hasta: límites inclusivos. Una fecha sin hora en `hasta` cubre el día completo.
        busqueda: texto a buscar en el título o el nombre del archivo (sin distinguir mayúsculas).
    """
    if pagina < 1 or tamano < 1:
        raise ValueError("La página y el tamaño deben ser mayores que cero.")

    filtros = []
    if dominio:
        filtros.append(Clasificacion.dominio == dominio)
    if requiere_revision is not None:
        filtros.append(Clasificacion.requiere_revision.is_(requiere_revision))
    if desde is not None:
        if not isinstance(desde, datetime):
            desde = datetime.combine(desde, time.min)
        filtros.append(Clasificacion.creado_en >= _a_utc_sin_zona(desde))
    if hasta is not None:
        if isinstance(hasta, datetime):
            filtros.append(Clasificacion.creado_en <= _a_utc_sin_zona(hasta))
        else:
            dia_siguiente = datetime.combine(hasta + timedelta(days=1), time.min)
            filtros.append(Clasificacion.creado_en < dia_siguiente)
    if busqueda and busqueda.strip():
        patron = f"%{busqueda.strip()}%"
        filtros.append(
            Clasificacion.documento.has(
                or_(Documento.titulo.ilike(patron), Documento.nombre_archivo.ilike(patron))
            )
        )

    total = sesion.scalar(select(func.count(Clasificacion.id)).where(*filtros)) or 0
    consulta = (
        select(Clasificacion)
        .where(*filtros)
        .options(joinedload(Clasificacion.documento), joinedload(Clasificacion.correccion))
        .order_by(Clasificacion.creado_en.desc(), Clasificacion.id.desc())
        .offset((pagina - 1) * tamano)
        .limit(tamano)
    )
    elementos = list(sesion.scalars(consulta).unique())
    return Pagina(elementos=elementos, total=total, pagina=pagina, tamano=tamano)


def ultimas_clasificaciones(sesion: Session, cantidad: int = 5) -> list[Clasificacion]:
    """Las más recientes, para la vista Clasificar."""
    return listar_clasificaciones(sesion, pagina=1, tamano=cantidad).elementos


# --- Correcciones -------------------------------------------------------------------------


def guardar_correccion(
    sesion: Session,
    clasificacion_id: int,
    *,
    dominio_correcto: str,
    area_correcta: str | None = None,
    comentario: str | None = None,
) -> Correccion:
    """Registra la corrección del usuario (RF-12). Si ya había una, la reemplaza."""
    clasificacion = obtener_clasificacion(sesion, clasificacion_id)
    correccion = clasificacion.correccion
    if correccion is None:
        correccion = Correccion(clasificacion=clasificacion)
        sesion.add(correccion)
    correccion.dominio_correcto = dominio_correcto
    correccion.area_correcta = area_correcta
    correccion.comentario = comentario
    correccion.creado_en = ahora_utc()
    sesion.flush()
    return correccion
