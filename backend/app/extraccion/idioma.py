"""Detección del idioma del texto con langdetect."""

from __future__ import annotations

from langdetect import DetectorFactory, LangDetectException, detect_langs

DetectorFactory.seed = 0  # langdetect es aleatorio; la semilla lo hace reproducible

IDIOMA_DESCONOCIDO = "desconocido"


def detectar_idioma(texto: str) -> tuple[str, float]:
    """Devuelve el código ISO 639-1 más probable (p. ej. `en`, `es`) y su probabilidad."""
    try:
        mejor = detect_langs(texto)[0]
    except LangDetectException:
        return IDIOMA_DESCONOCIDO, 0.0
    return mejor.lang, round(mejor.prob, 3)
