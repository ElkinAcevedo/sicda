"""Servicio de extracción: texto de PDF, DOCX y TXT, localización del resumen e idioma.

Responsable de RF-01 a RF-04 (sección 6.1 del documento de diseño).
"""

from app.extraccion.errores import (
    ArchivoDanado,
    ArchivoDemasiadoGrande,
    ErrorExtraccion,
    FormatoNoSoportado,
    TextoInsuficiente,
)
from app.extraccion.resumen import OrigenResumen
from app.extraccion.servicio import (
    Advertencia,
    ResultadoExtraccion,
    extraer_documento,
    extraer_texto_pegado,
)

__all__ = [
    "Advertencia",
    "ArchivoDanado",
    "ArchivoDemasiadoGrande",
    "ErrorExtraccion",
    "FormatoNoSoportado",
    "OrigenResumen",
    "ResultadoExtraccion",
    "TextoInsuficiente",
    "extraer_documento",
    "extraer_texto_pegado",
]
