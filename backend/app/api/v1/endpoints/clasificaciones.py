"""Recurso `/api/v1/clasificaciones` (sección 7.1 del documento de diseño).

- `POST /texto` y `POST /archivo`: extraer, clasificar y guardar (RF-01 a RF-09).
- `GET /` y `GET /{id}`: historial paginado y detalle (RF-10).
- `POST /{id}/correccion`: categoría correcta indicada por el usuario (RF-12).
"""

from __future__ import annotations

import time
from dataclasses import asdict
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.api.dependencias import obtener_catalogo, obtener_servicio, registrar_modelo_activo
from app.api.errores import ErrorApi, documentar_errores
from app.clasificacion import Catalogo, Nivel, ServicioClasificacion
from app.core.config import settings
from app.db import repositorios as repo
from app.db.sesion import obtener_sesion
from app.extraccion import ResultadoExtraccion, extraer_documento, extraer_texto_pegado
from app.schemas.clasificacion import (
    EntradaCorreccion,
    EntradaTexto,
    PaginaClasificaciones,
    RespuestaClasificacion,
    RespuestaDetalle,
)

router = APIRouter()

Sesion = Annotated[Session, Depends(obtener_sesion)]
Servicio = Annotated[ServicioClasificacion, Depends(obtener_servicio)]
CatalogoOpcional = Annotated[Catalogo | None, Depends(obtener_catalogo)]
# `date` primero: «2026-03-01» se lee como día completo, no como medianoche.
Fecha = date | datetime | None


@router.get(
    "",
    response_model=PaginaClasificaciones,
    summary="Historial de clasificaciones",
    responses=documentar_errores(400),
)
def listar_clasificaciones(
    sesion: Sesion,
    pagina: Annotated[int, Query(ge=1, description="Página, desde 1")] = 1,
    tamano: Annotated[int, Query(ge=1, le=100, description="Elementos por página")] = 20,
    dominio: Annotated[str | None, Query(description="Nombre exacto del dominio")] = None,
    desde: Annotated[Fecha, Query(description="Fecha (AAAA-MM-DD) o fecha y hora")] = None,
    hasta: Annotated[Fecha, Query(description="Inclusiva; sin hora cubre el día")] = None,
    requiere_revision: bool | None = None,
    busqueda: Annotated[
        str | None, Query(max_length=200, description="Texto en el título o el archivo")
    ] = None,
):
    """De la más reciente a la más antigua. Las fechas se interpretan en UTC."""
    if desde is not None and hasta is not None and _inicio(desde) > _inicio(hasta):
        raise ErrorApi("La fecha «desde» no puede ser posterior a «hasta».")
    resultado = repo.listar_clasificaciones(
        sesion,
        pagina=pagina,
        tamano=tamano,
        dominio=dominio,
        desde=desde,
        hasta=hasta,
        requiere_revision=requiere_revision,
        busqueda=busqueda,
    )
    return PaginaClasificaciones.desde_pagina(resultado)


@router.get(
    "/{clasificacion_id}",
    response_model=RespuestaDetalle,
    summary="Detalle de una clasificación",
    responses=documentar_errores(404),
)
def obtener_clasificacion(clasificacion_id: int, sesion: Sesion):
    return RespuestaDetalle.desde_registro(repo.obtener_clasificacion(sesion, clasificacion_id))


@router.post(
    "/{clasificacion_id}/correccion",
    response_model=RespuestaDetalle,
    summary="Corregir una clasificación",
    responses=documentar_errores(400, 404),
)
def corregir_clasificacion(
    clasificacion_id: int, entrada: EntradaCorreccion, sesion: Sesion, catalogo: CatalogoOpcional
):
    """Guarda la categoría correcta. Si ya había una corrección, la reemplaza."""
    if catalogo is not None:
        problema = catalogo.validar(entrada.dominio_correcto, entrada.area_correcta)
        if problema:
            raise ErrorApi(problema)
    repo.guardar_correccion(
        sesion,
        clasificacion_id,
        dominio_correcto=entrada.dominio_correcto,
        area_correcta=entrada.area_correcta,
        comentario=entrada.comentario,
    )
    sesion.commit()
    return RespuestaDetalle.desde_registro(repo.obtener_clasificacion(sesion, clasificacion_id))


def _inicio(valor: date | datetime) -> datetime:
    if isinstance(valor, datetime):
        return valor.replace(tzinfo=None)
    return datetime.combine(valor, datetime.min.time())


@router.post(
    "/texto",
    response_model=RespuestaClasificacion,
    status_code=201,
    summary="Clasificar un resumen pegado",
    responses=documentar_errores(400, 422, 503),
)
def clasificar_texto(entrada: EntradaTexto, sesion: Sesion, servicio: Servicio):
    inicio = time.perf_counter()
    extraccion = extraer_texto_pegado(entrada.texto, entrada.titulo)
    return _clasificar_y_guardar(
        sesion, servicio, extraccion, repo.calcular_hash(entrada.texto), inicio
    )


@router.post(
    "/archivo",
    response_model=RespuestaClasificacion,
    status_code=201,
    summary="Clasificar un archivo PDF, DOCX o TXT",
    responses=documentar_errores(400, 413, 415, 422, 503),
)
def clasificar_archivo(
    archivo: Annotated[UploadFile, File(description="PDF, DOCX o TXT, máximo 10 MB")],
    sesion: Sesion,
    servicio: Servicio,
):
    inicio = time.perf_counter()
    # Se lee un byte más del máximo: basta para saber si el archivo es demasiado grande
    # sin cargar en memoria uno enorme.
    limite = settings.tamano_maximo_archivo_mb * 1024 * 1024
    contenido = archivo.file.read(limite + 1)
    extraccion = extraer_documento(contenido, archivo.filename or "")
    return _clasificar_y_guardar(
        sesion, servicio, extraccion, repo.calcular_hash(contenido), inicio
    )


def _clasificar_y_guardar(
    sesion: Session,
    servicio: ServicioClasificacion,
    extraccion: ResultadoExtraccion,
    hash_sha256: str,
    inicio: float,
) -> RespuestaClasificacion:
    prediccion = servicio.clasificar(extraccion.texto)
    tiempo_ms = (time.perf_counter() - inicio) * 1000

    documento = repo.obtener_o_crear_documento(
        sesion,
        hash_sha256,
        nombre_archivo=extraccion.nombre_archivo,
        tipo=extraccion.formato,
        titulo=extraccion.titulo,
        texto_extraido=extraccion.texto,
        fuente_texto=str(extraccion.fuente_texto),
        idioma=extraccion.idioma,
        num_terminos=extraccion.num_terminos,
        palabras_clave=extraccion.palabras_clave,
    )
    clasificacion = repo.guardar_clasificacion(
        sesion,
        documento,
        registrar_modelo_activo(sesion, servicio),
        dominio=prediccion.dominio.nombre,
        conf_dominio=prediccion.dominio.confianza,
        area=prediccion.area.nombre,
        conf_area=prediccion.area.confianza,
        conf_conjunta=prediccion.confianza_conjunta,
        alternativas={
            "dominio": _alternativas(prediccion.dominio),
            "area": _alternativas(prediccion.area),
        },
        terminos_clave=prediccion.terminos_clave,
        advertencias=[asdict(a) for a in extraccion.advertencias],
        requiere_revision=prediccion.requiere_revision,
        tiempo_ms=round(tiempo_ms, 1),
    )
    sesion.commit()
    return RespuestaClasificacion.desde_registro(clasificacion)


def _alternativas(nivel: Nivel) -> list[dict]:
    return [asdict(a) for a in nivel.alternativas]
