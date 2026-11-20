"""POST /api/v1/clasificaciones/texto y /archivo: extraer, clasificar y guardar (RF-01 a RF-09)."""

from __future__ import annotations

import time
from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.api.dependencias import obtener_servicio, registrar_modelo_activo
from app.api.errores import documentar_errores
from app.clasificacion import Nivel, ServicioClasificacion
from app.core.config import settings
from app.db import repositorios as repo
from app.db.sesion import obtener_sesion
from app.extraccion import ResultadoExtraccion, extraer_documento, extraer_texto_pegado
from app.schemas.clasificacion import EntradaTexto, RespuestaClasificacion

router = APIRouter()

Sesion = Annotated[Session, Depends(obtener_sesion)]
Servicio = Annotated[ServicioClasificacion, Depends(obtener_servicio)]


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
