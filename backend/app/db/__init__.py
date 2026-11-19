"""Persistencia con SQLAlchemy: documento, clasificacion, correccion y modelo (sección 5.2)."""

from app.db.modelos import Base, Clasificacion, Correccion, Documento, Modelo
from app.db.sesion import SesionLocal, crear_tablas, obtener_sesion

__all__ = [
    "Base",
    "Clasificacion",
    "Correccion",
    "Documento",
    "Modelo",
    "SesionLocal",
    "crear_tablas",
    "obtener_sesion",
]
