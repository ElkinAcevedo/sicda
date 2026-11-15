"""Localización del resumen (*Abstract*) y de las palabras clave dentro del texto."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum

# Palabras que se toman del inicio cuando no hay sección de resumen.
PALABRAS_RESPALDO = 300
# Tope del resumen si no se encuentra dónde termina.
PALABRAS_MAXIMAS_RESUMEN = 500
# Un "resumen" más corto que esto probablemente es un falso positivo (p. ej. el índice).
PALABRAS_MINIMAS_RESUMEN = 25


class OrigenResumen(StrEnum):
    """Valor de `fuente_texto` en el contrato de la API (sección 7.2 del diseño)."""

    SECCION = "abstract"  # se encontró el encabezado Abstract/Resumen
    INICIO = "inicio"  # no hay encabezado: se usan los primeros 300 términos
    COMPLETO = "texto_completo"  # el texto es corto (p. ej. un resumen pegado): se usa entero


@dataclass
class ResumenLocalizado:
    texto: str
    origen: OrigenResumen
    palabras_clave: list[str] = field(default_factory=list)


# "Abstract", "A B S T R A C T" (Elsevier), "Summary", "Resumen", "Resumo".
_INGLES = r"a\s?b\s?s\s?t\s?r\s?a\s?c\s?t|summary"
_OTROS = r"resumen|resumo|r[ée]sum[ée]"
_ENCABEZADO = re.compile(
    rf"^[ \t]*(?:\d+\.?\s*)?(?P<titulo>{_INGLES}|{_OTROS})\b[ \t]*(?P<sep>[:.\-–—]?)[ \t]*"
    r"(?P<resto>.*)$",
    re.IGNORECASE | re.MULTILINE,
)
_PALABRAS_CLAVE = r"key\s?words|index\s+terms|palabras[\s-]+clave|descriptores"
# Líneas que marcan el final del resumen.
_FIN = re.compile(
    rf"^[ \t]*(?:"
    rf"(?:{_PALABRAS_CLAVE})\b"
    r"|(?:\d+|[IVX]+)?\.?\s*(?:introduction|introducci[óo]n|background|antecedentes)\b"
    r"|(?:©|\(c\)|copyright)"
    r"|(?:jel\s+classification|abbreviations|highlights|article\s+info)\b"
    rf"|(?:{_OTROS}|abstract)\b"
    r")",
    re.IGNORECASE | re.MULTILINE,
)
_LINEA_PALABRAS_CLAVE = re.compile(
    rf"^[ \t]*(?:{_PALABRAS_CLAVE})[ \t]*[:.\-–—]?[ \t]*(?P<lista>.+(?:\n(?!\n).+)*)",
    re.IGNORECASE | re.MULTILINE,
)
_SEPARADORES_PALABRAS_CLAVE = re.compile(r"\s*[;,·•]\s*")
# Entrada de un índice: "Summary ........ 3".
_ENTRADA_INDICE = re.compile(r"^[.\s·…_-]*\d+$")


def _palabras(texto: str) -> int:
    return len(texto.split())


def _cortar(texto: str, maximo: int) -> str:
    palabras = texto.split()
    return " ".join(palabras[:maximo])


def extraer_palabras_clave(texto: str) -> list[str]:
    """Busca una línea `Keywords:` / `Palabras clave:` y separa sus términos."""
    coincidencia = _LINEA_PALABRAS_CLAVE.search(texto)
    if not coincidencia:
        return []
    lineas = coincidencia["lista"].split("\n")
    # La lista termina en la siguiente sección (p. ej. «1. Introduction») aunque no haya
    # una línea en blanco de por medio.
    fin = next((i for i, ln in enumerate(lineas[1:], 1) if _FIN.match(ln)), len(lineas))
    lista = " ".join(lineas[:fin])
    terminos = (t.strip(" .") for t in _SEPARADORES_PALABRAS_CLAVE.split(lista))
    return [t for t in terminos if t and _palabras(t) <= 6][:15]


def _es_encabezado(encabezado: re.Match) -> bool:
    """Descarta líneas de índice y frases que solo empiezan con la palabra («Summary of…»)."""
    resto = encabezado["resto"]
    if not resto:
        return True
    if _ENTRADA_INDICE.match(resto):
        return False
    return bool(encabezado["sep"]) or resto[0].isupper()


def _texto_de_seccion(texto: str, encabezado: re.Match) -> str:
    inicio = encabezado.start("resto")
    fin = _FIN.search(texto, encabezado.end())
    seccion = texto[inicio : fin.start() if fin else len(texto)]
    return _cortar(seccion, PALABRAS_MAXIMAS_RESUMEN)


def detectar_titulo(texto: str) -> str | None:
    """Toma como título la primera línea «de frase» antes del resumen (máx. 10 líneas)."""
    primer_encabezado = next((e for e in _ENCABEZADO.finditer(texto) if _es_encabezado(e)), None)
    cabecera = texto[: primer_encabezado.start()] if primer_encabezado else texto
    for linea in [ln for ln in cabecera.split("\n") if ln.strip()][:10]:
        palabras = linea.split()
        if 3 <= len(palabras) <= 30 and "@" not in linea and any(c.isalpha() for c in linea):
            return linea.strip()
    return None


def localizar_resumen(texto: str) -> ResumenLocalizado:
    """Devuelve el resumen del documento y de dónde se obtuvo.

    Si hay varios encabezados (p. ej. *Resumen* y *Abstract*), se prefiere el inglés porque
    el modelo se entrenó con resúmenes en inglés.
    """
    palabras_clave = extraer_palabras_clave(texto)
    candidatos = []
    for encabezado in _ENCABEZADO.finditer(texto):
        if not _es_encabezado(encabezado):
            continue
        seccion = _texto_de_seccion(texto, encabezado)
        if _palabras(seccion) >= PALABRAS_MINIMAS_RESUMEN:
            es_ingles = re.fullmatch(_INGLES, encabezado["titulo"], re.IGNORECASE) is not None
            candidatos.append((not es_ingles, encabezado.start(), seccion))
    if candidatos:
        _, _, seccion = min(candidatos)
        return ResumenLocalizado(" ".join(seccion.split()), OrigenResumen.SECCION, palabras_clave)

    if _palabras(texto) <= PALABRAS_RESPALDO:
        return ResumenLocalizado(" ".join(texto.split()), OrigenResumen.COMPLETO, palabras_clave)
    return ResumenLocalizado(
        _cortar(texto, PALABRAS_RESPALDO), OrigenResumen.INICIO, palabras_clave
    )
