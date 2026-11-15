"""Orquesta la extracción: archivo o texto pegado -> resumen listo para clasificar."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.config import settings
from app.extraccion.errores import ArchivoDemasiadoGrande, TextoInsuficiente
from app.extraccion.idioma import detectar_idioma
from app.extraccion.lectores import extraer_texto, formato_de, limpiar_texto_extraido
from app.extraccion.resumen import OrigenResumen, detectar_titulo, localizar_resumen

IDIOMA_DEL_MODELO = "en"


@dataclass(frozen=True)
class Advertencia:
    """Aviso no bloqueante. `codigo` es estable (lo usa el frontend); `mensaje` es para mostrar."""

    codigo: str
    mensaje: str


@dataclass
class ResultadoExtraccion:
    """Lo que la clasificación necesita del documento, más avisos para el usuario."""

    texto: str  # resumen que se enviará al clasificador
    fuente_texto: OrigenResumen
    formato: str  # pdf, docx, txt o texto (pegado)
    idioma: str
    confianza_idioma: float
    num_terminos: int  # palabras del resumen
    palabras_documento: int
    titulo: str | None = None
    palabras_clave: list[str] = field(default_factory=list)
    nombre_archivo: str | None = None
    advertencias: list[Advertencia] = field(default_factory=list)


def extraer_documento(
    contenido: bytes,
    nombre_archivo: str,
    *,
    tamano_maximo_mb: float | None = None,
    minimo_terminos: int | None = None,
) -> ResultadoExtraccion:
    """Extrae título, resumen e idioma de un archivo PDF, DOCX o TXT (RF-01, RF-03, RF-04)."""
    formato = formato_de(nombre_archivo).lstrip(".")
    maximo = tamano_maximo_mb if tamano_maximo_mb is not None else settings.tamano_maximo_archivo_mb
    if len(contenido) > maximo * 1024 * 1024:
        raise ArchivoDemasiadoGrande(f"El archivo supera el máximo de {maximo:g} MB.")
    if not contenido:
        raise TextoInsuficiente("El archivo está vacío.")

    extraido = extraer_texto(contenido, nombre_archivo)
    if not extraido.texto:
        mensaje = "El documento no contiene texto."
        if formato == "pdf":
            mensaje = "El PDF no tiene texto seleccionable; puede ser un documento escaneado."
        raise TextoInsuficiente(mensaje)
    titulo = extraido.titulo or detectar_titulo(extraido.texto)
    return _analizar(extraido.texto, formato, titulo, nombre_archivo, minimo_terminos)


def extraer_texto_pegado(
    texto: str, titulo: str | None = None, *, minimo_terminos: int | None = None
) -> ResultadoExtraccion:
    """Procesa un título opcional y un resumen pegados en el dashboard (RF-02)."""
    texto = limpiar_texto_extraido(texto)
    if not texto:
        raise TextoInsuficiente("El texto está vacío.")
    titulo = " ".join(titulo.split()) if titulo and titulo.strip() else None
    return _analizar(texto, "texto", titulo, None, minimo_terminos)


def _analizar(
    texto: str,
    formato: str,
    titulo: str | None,
    nombre_archivo: str | None,
    minimo_terminos: int | None,
) -> ResultadoExtraccion:
    minimo = minimo_terminos if minimo_terminos is not None else settings.minimo_terminos
    resumen = localizar_resumen(texto)
    num_terminos = len(resumen.texto.split())
    if num_terminos < minimo:
        raise TextoInsuficiente(
            f"El texto tiene {num_terminos} términos; se necesitan al menos {minimo} "
            "para clasificarlo."
        )
    idioma, confianza = detectar_idioma(resumen.texto)

    advertencias = []
    if resumen.origen is OrigenResumen.INICIO:
        advertencias.append(
            Advertencia(
                "RESUMEN_NO_ENCONTRADO",
                "No se encontró una sección «Abstract» o «Resumen»; se usaron los primeros "
                "300 términos del documento.",
            )
        )
    if idioma != IDIOMA_DEL_MODELO:
        advertencias.append(
            Advertencia(
                "IDIOMA_NO_SOPORTADO",
                f"El texto parece estar en «{idioma}». El modelo se entrenó con resúmenes en "
                "inglés, así que la clasificación puede ser poco fiable.",
            )
        )

    return ResultadoExtraccion(
        texto=resumen.texto,
        fuente_texto=resumen.origen,
        formato=formato,
        idioma=idioma,
        confianza_idioma=confianza,
        num_terminos=num_terminos,
        palabras_documento=len(texto.split()),
        titulo=titulo,
        palabras_clave=resumen.palabras_clave,
        nombre_archivo=nombre_archivo,
        advertencias=advertencias,
    )
