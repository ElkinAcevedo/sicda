"""Errores de la extracción, con su código HTTP y el código del contrato (diseño, sección 7.3)."""


class ErrorExtraccion(Exception):  # noqa: N818 - nombre en español
    """Error base: el documento no se puede procesar."""

    codigo_http = 422
    codigo = "TEXTO_INSUFICIENTE"

    def __init__(self, mensaje: str) -> None:
        super().__init__(mensaje)
        self.mensaje = mensaje


class FormatoNoSoportado(ErrorExtraccion):
    codigo_http = 415
    codigo = "FORMATO_NO_SOPORTADO"


class ArchivoDemasiadoGrande(ErrorExtraccion):
    codigo_http = 413
    codigo = "ARCHIVO_MUY_GRANDE"


class ArchivoDanado(ErrorExtraccion):
    """El archivo no se puede abrir: corrupto, protegido o con un formato distinto al indicado."""

    codigo = "ARCHIVO_DANADO"


class TextoInsuficiente(ErrorExtraccion):
    """No hay texto o hay menos términos de los necesarios (p. ej. un PDF escaneado)."""

    codigo = "TEXTO_INSUFICIENTE"
