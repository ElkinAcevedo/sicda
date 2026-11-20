"""Errores de la API con el formato del contrato: `{"error": {"codigo", "mensaje"}}` (sección 7.3).

| Código | HTTP |
| --- | --- |
| `ENTRADA_INVALIDA` | 400 |
| `NO_ENCONTRADO` | 404 |
| `ARCHIVO_MUY_GRANDE` | 413 |
| `FORMATO_NO_SOPORTADO` | 415 |
| `TEXTO_INSUFICIENTE`, `ARCHIVO_DANADO` | 422 |
| `MODELO_NO_DISPONIBLE` | 503 |
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.db.repositorios import NoEncontrado
from app.extraccion import ErrorExtraccion


class DetalleError(BaseModel):
    codigo: str
    mensaje: str


class RespuestaError(BaseModel):
    error: DetalleError


class ErrorApi(Exception):  # noqa: N818 - nombre en español
    codigo_http = 400
    codigo = "ENTRADA_INVALIDA"

    def __init__(self, mensaje: str) -> None:
        super().__init__(mensaje)
        self.mensaje = mensaje


class ModeloNoDisponible(ErrorApi):
    codigo_http = 503
    codigo = "MODELO_NO_DISPONIBLE"


def respuesta_error(codigo_http: int, codigo: str, mensaje: str) -> JSONResponse:
    contenido = RespuestaError(error=DetalleError(codigo=codigo, mensaje=mensaje))
    return JSONResponse(status_code=codigo_http, content=contenido.model_dump())


def _mensaje_validacion(error: RequestValidationError) -> str:
    detalles = []
    for problema in error.errors():
        campo = ".".join(str(p) for p in problema.get("loc", ()) if p not in ("body", "query"))
        detalles.append(f"{campo}: {problema.get('msg')}" if campo else str(problema.get("msg")))
    return "Entrada inválida. " + "; ".join(detalles)


def registrar_manejadores(aplicacion: FastAPI) -> None:
    """Traduce las excepciones conocidas al formato de error del contrato."""

    @aplicacion.exception_handler(ErrorExtraccion)
    async def _extraccion(_request: Request, error: ErrorExtraccion) -> JSONResponse:
        return respuesta_error(error.codigo_http, error.codigo, error.mensaje)

    @aplicacion.exception_handler(ErrorApi)
    async def _api(_request: Request, error: ErrorApi) -> JSONResponse:
        return respuesta_error(error.codigo_http, error.codigo, error.mensaje)

    @aplicacion.exception_handler(NoEncontrado)
    async def _no_encontrado(_request: Request, error: NoEncontrado) -> JSONResponse:
        return respuesta_error(404, "NO_ENCONTRADO", str(error))

    @aplicacion.exception_handler(RequestValidationError)
    async def _validacion(_request: Request, error: RequestValidationError) -> JSONResponse:
        return respuesta_error(400, "ENTRADA_INVALIDA", _mensaje_validacion(error))


def documentar_errores(*codigos_http: int) -> dict[int | str, dict]:
    """`responses=` para OpenAPI: así /docs muestra el formato de cada error."""
    return {codigo: {"model": RespuestaError} for codigo in codigos_http}
