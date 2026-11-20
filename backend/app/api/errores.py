"""Errores de la API con el formato del contrato: `{"error": {"codigo", "mensaje"}}` (sección 7.3).

| Código | HTTP |
| --- | --- |
| `ENTRADA_INVALIDA` | 400 |
| `NO_ENCONTRADO` | 404 |
| `ARCHIVO_MUY_GRANDE` | 413 |
| `FORMATO_NO_SOPORTADO` | 415 |
| `TEXTO_INSUFICIENTE`, `ARCHIVO_DANADO` | 422 |
| `MODELO_NO_DISPONIBLE`, `CATEGORIAS_NO_DISPONIBLES` | 503 |
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.clasificacion.registro import SinPredicciones
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


class CategoriasNoDisponibles(ErrorApi):
    """No se pudo leer `categorias.json` (código propio, como `ARCHIVO_DANADO`)."""

    codigo_http = 503
    codigo = "CATEGORIAS_NO_DISPONIBLES"


def respuesta_error(codigo_http: int, codigo: str, mensaje: str) -> JSONResponse:
    contenido = RespuestaError(error=DetalleError(codigo=codigo, mensaje=mensaje))
    return JSONResponse(status_code=codigo_http, content=contenido.model_dump())


# Mensajes en español para los errores de validación más comunes de Pydantic.
MENSAJES_VALIDACION = {
    "missing": "es obligatorio",
    "string_type": "debe ser texto",
    "string_too_short": "debe tener al menos {min_length} caracteres",
    "string_too_long": "debe tener como máximo {max_length} caracteres",
    "int_parsing": "debe ser un número entero",
    "int_type": "debe ser un número entero",
    "bool_parsing": "debe ser true o false",
    "greater_than_equal": "debe ser mayor o igual que {ge}",
    "less_than_equal": "debe ser menor o igual que {le}",
    "date_from_datetime_parsing": "debe ser una fecha AAAA-MM-DD o una fecha y hora",
    "datetime_from_date_parsing": "debe ser una fecha AAAA-MM-DD o una fecha y hora",
    "json_invalid": "el JSON está mal formado",
    "literal_error": "debe ser {expected}",
    "model_attributes_type": "debe ser un objeto JSON",
    "dict_type": "debe ser un objeto JSON",
}


# Partes de `loc` que no son el nombre del campo: dónde viene y, en las uniones
# (`datetime | date`), qué tipo se intentó.
_SIN_CAMPO = {"body", "query", "path", "date", "datetime"}


def _mensaje_validacion(error: RequestValidationError) -> str:
    detalles = []
    for problema in error.errors():
        tipo = problema.get("type", "")
        contexto = problema.get("ctx", {})
        if tipo == "literal_error":  # Pydantic escribe «'a' or 'b'»
            contexto = {"expected": str(contexto.get("expected", "")).replace(" or ", " o ")}
        if tipo == "string_too_short" and contexto.get("min_length") == 1:
            mensaje = "no puede estar vacío"
        elif tipo in MENSAJES_VALIDACION:
            mensaje = MENSAJES_VALIDACION[tipo].format(**contexto)
        else:
            mensaje = problema.get("msg")
        partes = [] if tipo == "json_invalid" else problema.get("loc", ())
        campo = ".".join(str(p) for p in partes if p not in _SIN_CAMPO)
        detalles.append(f"{campo}: {mensaje}" if campo else str(mensaje))
    return "Entrada inválida. " + "; ".join(dict.fromkeys(detalles))


def registrar_manejadores(aplicacion: FastAPI) -> None:
    """Traduce las excepciones conocidas al formato de error del contrato."""

    @aplicacion.exception_handler(ErrorExtraccion)
    async def _extraccion(_request: Request, error: ErrorExtraccion) -> JSONResponse:
        return respuesta_error(error.codigo_http, error.codigo, error.mensaje)

    @aplicacion.exception_handler(ErrorApi)
    async def _api(_request: Request, error: ErrorApi) -> JSONResponse:
        return respuesta_error(error.codigo_http, error.codigo, error.mensaje)

    @aplicacion.exception_handler(NoEncontrado)
    @aplicacion.exception_handler(SinPredicciones)
    async def _no_encontrado(_request: Request, error: LookupError) -> JSONResponse:
        return respuesta_error(404, "NO_ENCONTRADO", str(error))

    @aplicacion.exception_handler(RequestValidationError)
    async def _validacion(_request: Request, error: RequestValidationError) -> JSONResponse:
        return respuesta_error(400, "ENTRADA_INVALIDA", _mensaje_validacion(error))


def documentar_errores(*codigos_http: int) -> dict[int | str, dict]:
    """`responses=` para OpenAPI: así /docs muestra el formato de cada error."""
    return {codigo: {"model": RespuestaError} for codigo in codigos_http}
