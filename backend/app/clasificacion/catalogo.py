"""Catálogo de dominios y áreas (`categorias.json`, generado en la Fase I; ver ADR 0002).

Se carga aparte del modelo: el historial y las correcciones lo necesitan aunque el modelo
no esté disponible.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class Catalogo:
    """Traduce ids a nombres y valida que un área pertenezca a su dominio."""

    def __init__(self, categorias: dict[str, Any]) -> None:
        self.categorias = categorias
        self._dominios = {d["id"]: d["nombre"] for d in categorias["dominios"]}
        self._areas = {a["id"]: a["nombre"] for d in categorias["dominios"] for a in d["areas"]}
        self._areas_por_dominio = {
            d["nombre"]: {a["nombre"] for a in d["areas"]} for d in categorias["dominios"]
        }

    @classmethod
    def desde_archivo(cls, ruta: Path | str) -> Catalogo:
        return cls(json.loads(Path(ruta).read_text(encoding="utf-8")))

    def nombre_dominio(self, identificador: int) -> str:
        return self._dominios.get(int(identificador), str(identificador))

    def nombre_area(self, identificador: int) -> str:
        return self._areas.get(int(identificador), str(identificador))

    def validar(self, dominio: str, area: str | None = None) -> str | None:
        """Devuelve un mensaje de error si el dominio o el área no existen; si no, `None`."""
        if dominio not in self._areas_por_dominio:
            return f"El dominio «{dominio}» no existe."
        if area is not None and area not in self._areas_por_dominio[dominio]:
            return f"El área «{area}» no pertenece al dominio «{dominio}»."
        return None


def cargar_catalogo(ruta: Path | str) -> Catalogo | None:
    try:
        return Catalogo.desde_archivo(ruta)
    except Exception:  # archivo ausente o mal formado: la API sigue sin validar nombres
        logger.exception("No se pudo cargar el catálogo de categorías desde %s", ruta)
        return None
