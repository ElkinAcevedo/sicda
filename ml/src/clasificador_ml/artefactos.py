"""Lectura de los artefactos de `models/` y publicación del modelo activo (RNF-08).

Estructura:

    models/
    ├── activo.json                       # modelo que carga la API
    ├── complement_nb/<version>/          # generado por `entrenamiento.py`
    ├── linear_svc/<version>/
    └── distilbert/<version>/             # generado en Colab (notebook 04)

Cada versión tiene un `metadatos.json` con al menos `version` y `fecha`.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from clasificador_ml.evaluacion import guardar_json
from clasificador_ml.rutas import MODELOS

ARCHIVO_ACTIVO = "activo.json"


def versiones(algoritmo: str, directorio: Path | str = MODELOS) -> list[str]:
    """Versiones de un algoritmo, de la más antigua a la más reciente (según `fecha`)."""
    carpeta = Path(directorio) / algoritmo
    if not carpeta.is_dir():
        return []
    encontradas = []
    for ruta in carpeta.iterdir():
        archivo = ruta / "metadatos.json"
        if archivo.is_file():
            fecha = json.loads(archivo.read_text(encoding="utf-8")).get("fecha", "")
            encontradas.append((fecha, ruta.name))
    return [nombre for _, nombre in sorted(encontradas)]


def ultima_version(algoritmo: str, directorio: Path | str = MODELOS) -> str:
    disponibles = versiones(algoritmo, directorio)
    if not disponibles:
        raise FileNotFoundError(
            f"No hay versiones de '{algoritmo}' en {directorio}. Entrena primero el modelo."
        )
    return disponibles[-1]


def carpeta_version(
    algoritmo: str, version: str | None = None, directorio: Path | str = MODELOS
) -> Path:
    """Carpeta de una versión (la más reciente si `version` es `None`)."""
    version = version or ultima_version(algoritmo, directorio)
    carpeta = Path(directorio) / algoritmo / version
    if not (carpeta / "metadatos.json").is_file():
        raise FileNotFoundError(f"No existe {carpeta / 'metadatos.json'}")
    return carpeta


def cargar_metadatos(
    algoritmo: str, version: str | None = None, directorio: Path | str = MODELOS
) -> dict[str, Any]:
    carpeta = carpeta_version(algoritmo, version, directorio)
    return json.loads((carpeta / "metadatos.json").read_text(encoding="utf-8"))


def cargar_predicciones(
    algoritmo: str,
    tipo: str,
    version: str | None = None,
    directorio: Path | str = MODELOS,
) -> pd.DataFrame:
    """Predicciones de validación que guardó `entrenamiento.py` (`predicciones_val_<tipo>`)."""
    carpeta = carpeta_version(algoritmo, version, directorio)
    return pd.read_parquet(carpeta / f"predicciones_val_{tipo}.parquet")


def cargar_probabilidades(
    algoritmo: str,
    particion: str,
    version: str | None = None,
    directorio: Path | str = MODELOS,
) -> pd.DataFrame:
    """Probabilidades por área exportadas desde Colab (`probabilidades_<particion>.parquet`).

    Columnas: `id_documento` y una columna `p_<id_area>` por área.
    """
    carpeta = carpeta_version(algoritmo, version, directorio)
    return pd.read_parquet(carpeta / f"probabilidades_{particion}.parquet")


def cargar_modelo(
    algoritmo: str, tipo: str, version: str | None = None, directorio: Path | str = MODELOS
):
    carpeta = carpeta_version(algoritmo, version, directorio)
    return joblib.load(carpeta / f"{tipo}.joblib")


def publicar_activo(
    algoritmo: str,
    version: str,
    tipo: str,
    umbrales: dict[str, float],
    metricas_prueba: dict[str, Any] | None = None,
    directorio: Path | str = MODELOS,
    **extra: Any,
) -> Path:
    """Escribe `models/activo.json`: el modelo que la API carga al iniciar.

    Args:
        umbrales: `umbral_dominio` y `umbral_conjunta` calibrados en validación.
        metricas_prueba: métricas en test (se calculan una sola vez, en el notebook 05).
    """
    carpeta = carpeta_version(algoritmo, version, directorio)
    archivo = f"{tipo}.joblib"
    if not (carpeta / archivo).is_file():
        raise FileNotFoundError(f"No existe {carpeta / archivo}")
    faltan = {"umbral_dominio", "umbral_conjunta"} - set(umbrales)
    if faltan:
        raise ValueError(f"Faltan umbrales: {sorted(faltan)}")
    activo = {
        "algoritmo": algoritmo,
        "version": version,
        "tipo": tipo,
        "archivo": f"{algoritmo}/{version}/{archivo}",
        "umbrales": {k: float(v) for k, v in umbrales.items()},
        "metricas_prueba": metricas_prueba,
        "publicado": datetime.now().isoformat(timespec="seconds"),
        **extra,
    }
    return guardar_json(activo, Path(directorio) / ARCHIVO_ACTIVO)


def cargar_activo(directorio: Path | str = MODELOS) -> tuple[Any, dict[str, Any]]:
    """Carga el modelo activo con sus umbrales. Devuelve `(modelo, información)`."""
    ruta = Path(directorio) / ARCHIVO_ACTIVO
    if not ruta.is_file():
        raise FileNotFoundError(f"No hay modelo activo: falta {ruta}")
    info = json.loads(ruta.read_text(encoding="utf-8"))
    modelo = joblib.load(Path(directorio) / info["archivo"])
    for nombre, valor in info.get("umbrales", {}).items():
        setattr(modelo, nombre, valor)
    return modelo, info
