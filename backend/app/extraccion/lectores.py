"""Lectura de texto desde PDF, DOCX y TXT (sección 6.1 del diseño)."""

from __future__ import annotations

import io
import re
import unicodedata
import zipfile
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import PurePath

from app.extraccion.errores import ArchivoDanado, FormatoNoSoportado

# El resumen está en las primeras páginas; leer todo un libro no aporta y es lento.
PAGINAS_MAXIMAS_PDF = 30
# Líneas del borde de cada página donde se buscan encabezados y pies repetidos.
LINEAS_BORDE = 3

_GUION_FIN_DE_LINEA = re.compile(r"(\w)-\n(\w)")
_ESPACIOS = re.compile(r"[ \t\f\v ]+")
_LINEAS_VACIAS = re.compile(r"\n{3,}")
_DIGITOS = re.compile(r"\d+")


@dataclass
class TextoExtraido:
    texto: str
    titulo: str | None = None  # título de los metadatos del archivo, si lo tiene


def _clave_linea(linea: str) -> str:
    """«Page 3 of 23» y «Page 4 of 23» cuentan como la misma línea."""
    return _DIGITOS.sub("#", linea.strip().lower())


def quitar_encabezados_y_pies(paginas: list[str]) -> list[str]:
    """Quita las líneas del borde que se repiten en al menos la mitad de las páginas."""
    if len(paginas) < 3:
        return paginas
    lineas_por_pagina = [[ln for ln in p.split("\n") if ln.strip()] for p in paginas]
    conteo = Counter()
    for lineas in lineas_por_pagina:
        borde = lineas[:LINEAS_BORDE] + lineas[-LINEAS_BORDE:]
        conteo.update({_clave_linea(ln) for ln in borde})
    repetidas = {clave for clave, n in conteo.items() if n >= len(paginas) / 2}
    return [
        "\n".join(ln for ln in lineas if _clave_linea(ln) not in repetidas)
        for lineas in lineas_por_pagina
    ]


def leer_pdf(contenido: bytes) -> TextoExtraido:
    import pymupdf

    if not contenido.startswith(b"%PDF"):
        raise ArchivoDanado("El archivo no es un PDF válido.")
    try:
        documento = pymupdf.open(stream=contenido, filetype="pdf")
    except Exception as error:  # PyMuPDF lanza varios tipos según el daño
        raise ArchivoDanado("No se pudo abrir el PDF; puede estar dañado.") from error
    with documento:
        if documento.needs_pass:
            raise ArchivoDanado("El PDF está protegido con contraseña.")
        # Sin `sort`: el orden del propio PDF lee cada columna completa; ordenar por altura
        # mezclaría las columnas de los artículos a dos columnas.
        paginas = [
            documento[i].get_text("text") for i in range(min(len(documento), PAGINAS_MAXIMAS_PDF))
        ]
        titulo = (documento.metadata or {}).get("title") or None
    return TextoExtraido("\n".join(quitar_encabezados_y_pies(paginas)), titulo)


def leer_docx(contenido: bytes) -> TextoExtraido:
    import docx

    try:
        documento = docx.Document(io.BytesIO(contenido))
    except (zipfile.BadZipFile, KeyError, ValueError) as error:
        raise ArchivoDanado("No se pudo abrir el DOCX; puede estar dañado.") from error
    # Solo párrafos en orden, sin tablas ni imágenes.
    texto = "\n".join(parrafo.text for parrafo in documento.paragraphs)
    return TextoExtraido(texto, documento.core_properties.title or None)


def leer_txt(contenido: bytes) -> TextoExtraido:
    for codificacion in ("utf-8-sig", "cp1252"):
        try:
            return TextoExtraido(contenido.decode(codificacion))
        except UnicodeDecodeError:
            continue
    return TextoExtraido(contenido.decode("latin-1"))  # nunca falla


LECTORES: dict[str, Callable[[bytes], TextoExtraido]] = {
    ".pdf": leer_pdf,
    ".docx": leer_docx,
    ".txt": leer_txt,
}


def formato_de(nombre_archivo: str) -> str:
    """Devuelve la extensión (`.pdf`, `.docx`, `.txt`) o lanza `FormatoNoSoportado`."""
    extension = PurePath(nombre_archivo).suffix.lower()
    if extension not in LECTORES:
        soportados = ", ".join(e.lstrip(".").upper() for e in LECTORES)
        raise FormatoNoSoportado(
            f"Formato '{extension or 'sin extensión'}' no soportado. Usa {soportados}."
        )
    return extension


def limpiar_texto_extraido(texto: str) -> str:
    """Une palabras cortadas con guion al final de línea y normaliza espacios.

    Conserva los saltos de línea porque la localización del resumen depende de ellos.
    """
    texto = unicodedata.normalize("NFKC", texto)  # ligaduras: «ﬁ» -> «fi»
    texto = texto.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    texto = _GUION_FIN_DE_LINEA.sub(r"\1\2", texto)
    lineas = (_ESPACIOS.sub(" ", linea).strip() for linea in texto.split("\n"))
    return _LINEAS_VACIAS.sub("\n\n", "\n".join(lineas)).strip()


def extraer_texto(contenido: bytes, nombre_archivo: str) -> TextoExtraido:
    """Lee el archivo según su extensión y devuelve el texto limpio."""
    extraido = LECTORES[formato_de(nombre_archivo)](contenido)
    titulo = extraido.titulo.strip() if extraido.titulo else None
    return TextoExtraido(limpiar_texto_extraido(extraido.texto), titulo or None)
