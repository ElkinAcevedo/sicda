"""Servicio de clasificación: carga el modelo activo y aplica la jerarquía dominio -> área.

Usa el preprocesamiento compartido de `clasificador_ml` (sección 6 del documento de diseño).
"""

from app.clasificacion.catalogo import Catalogo, cargar_catalogo
from app.clasificacion.servicio import (
    Alternativa,
    Nivel,
    Prediccion,
    ServicioClasificacion,
    cargar_servicio,
)

__all__ = [
    "Alternativa",
    "Catalogo",
    "Nivel",
    "Prediccion",
    "ServicioClasificacion",
    "cargar_catalogo",
    "cargar_servicio",
]
