"""Modelos entrenados en `models/` y sus métricas, para el panel de métricas (RF-11).

- Al iniciar, la API registra en la tabla `modelo` la versión más reciente de cada algoritmo
  (y la activa, si es otra). Así `GET /modelos` compara NB, SVM y DistilBERT.
- Cada algoritmo puede tener dos variantes (jerárquica y plana). Se registra la del modelo
  activo o, si no es el activo, la de mayor F1-macro jerárquico en validación.
- `GET /modelos/{id}/metricas` calcula las métricas por clase y las matrices de confusión a
  partir de las predicciones guardadas al entrenar (validación) o en el notebook 05 (prueba).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import precision_recall_fscore_support
from sqlalchemy.orm import Session

from app.clasificacion.catalogo import Catalogo
from app.db import repositorios as repo
from app.db.modelos import Modelo
from clasificador_ml.artefactos import ultima_version
from clasificador_ml.evaluacion import evaluar, matrices_area_por_dominio, matriz_confusion
from clasificador_ml.jerarquico import requiere_revision
from clasificador_ml.seleccion import predicciones_desde_probabilidades

logger = logging.getLogger(__name__)

NOMBRES_ALGORITMO = {
    "linear_svc": "TF-IDF + SVM lineal",
    "complement_nb": "TF-IDF + Complement Naive Bayes",
    "distilbert": "DistilBERT",
}
# Umbrales del diseño, para los modelos que no se calibraron (los no elegidos).
UMBRALES_DISENO = {"umbral_dominio": 0.60, "umbral_conjunta": 0.40}
PARTICIONES = {"validacion": "val", "prueba": "test"}


def nombre_modelo(algoritmo: str, tipo: str) -> str:
    """Nombre legible, por ejemplo «TF-IDF + SVM lineal (plano)»."""
    return f"{NOMBRES_ALGORITMO.get(algoritmo, algoritmo)} ({tipo})"


def _seccion_tipo(metadatos: dict[str, Any], tipo: str) -> dict[str, Any]:
    """Parte de `metadatos.json` de una variante (DistilBERT guarda una sola, en la raíz)."""
    if tipo in metadatos.get("tipos", {}):
        return metadatos["tipos"][tipo]
    return metadatos if metadatos.get("tipo") == tipo else {}


def tipos_disponibles(metadatos: dict[str, Any]) -> list[str]:
    return list(metadatos.get("tipos", {})) or ([metadatos["tipo"]] if "tipo" in metadatos else [])


def resumen(metricas: dict[str, Any] | None) -> dict[str, float | None] | None:
    """Las cifras que muestra el panel: F1-macro por nivel y accuracy jerárquica."""
    if not metricas:
        return None

    def valor(nivel: str, clave: str) -> float | None:
        return (metricas.get(nivel) or {}).get(clave)

    return {
        "f1_dominio": valor("dominio", "f1_macro"),
        "f1_area": valor("area", "f1_macro"),
        "f1_jerarquico": valor("jerarquico", "f1_macro"),
        "accuracy_jerarquica": valor("jerarquico", "accuracy"),
    }


def mejor_tipo(metadatos: dict[str, Any]) -> str:
    """La variante con mayor F1-macro jerárquico en validación."""

    def puntaje(tipo: str) -> float:
        validacion = _seccion_tipo(metadatos, tipo).get("metricas_validacion") or {}
        return validacion.get("jerarquico", {}).get("f1_macro", -1.0)

    return max(tipos_disponibles(metadatos), key=puntaje)


def hiperparametros(metadatos: dict[str, Any], tipo: str) -> dict[str, Any]:
    """Mejores hiperparámetros de cada submodelo o, si no hay búsqueda, la configuración."""
    submodelos = _seccion_tipo(metadatos, tipo).get("submodelos", {})
    return {
        nombre: datos.get("mejores_parametros", {}) for nombre, datos in submodelos.items()
    } or dict(metadatos.get("configuracion", {}))


def metricas_guardadas(
    metadatos: dict[str, Any], tipo: str, info_activo: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Lo que se guarda en `modelo.metricas`.

    `info_activo` es `activo.json` si este es el modelo activo: aporta las métricas de prueba
    y los umbrales calibrados.
    """
    seccion = _seccion_tipo(metadatos, tipo)
    tiempo = seccion.get("tiempo_prediccion") or {}
    variantes = {
        t: resumen(_seccion_tipo(metadatos, t).get("metricas_validacion"))
        for t in tipos_disponibles(metadatos)
    }
    info_activo = info_activo or {}
    return {
        "tipo": tipo,
        "validacion": seccion.get("metricas_validacion"),
        "prueba": info_activo.get("metricas_prueba"),
        "umbrales": info_activo.get("umbrales"),
        "tiempo_ms": tiempo.get("media_ms"),
        "porcentaje_revision_validacion": seccion.get("porcentaje_revision_validacion"),
        "tiempo_entrenamiento_s": seccion.get("tiempo_entrenamiento_s"),
        "variantes": variantes,
    }


def _fecha(metadatos: dict[str, Any]) -> datetime | None:
    fecha = metadatos.get("fecha")
    return datetime.fromisoformat(fecha) if fecha else None


def _ruta_artefacto(algoritmo: str, version: str, tipo: str) -> str:
    archivo = "modelo" if algoritmo == "distilbert" else f"{tipo}.joblib"
    return f"{algoritmo}/{version}/{archivo}"


@dataclass
class ModeloDisponible:
    """Una versión de `models/` lista para registrar en la base."""

    algoritmo: str
    version: str
    tipo: str
    metadatos: dict[str, Any]
    info_activo: dict[str, Any] | None = None
    activo: bool = False

    def campos(self) -> dict[str, Any]:
        """Argumentos de `repositorios.registrar_modelo`."""
        return {
            "nombre": nombre_modelo(self.algoritmo, self.tipo),
            "algoritmo": self.algoritmo,
            "version": self.version,
            "ruta_artefacto": (self.info_activo or {}).get("archivo")
            or _ruta_artefacto(self.algoritmo, self.version, self.tipo),
            "hiperparametros": hiperparametros(self.metadatos, self.tipo),
            "metricas": metricas_guardadas(self.metadatos, self.tipo, self.info_activo),
            "entrenado_en": _fecha(self.metadatos),
        }


def descubrir_modelos(
    ruta_modelos: Path | str, info_activo: dict[str, Any] | None = None
) -> list[ModeloDisponible]:
    """La versión más reciente de cada algoritmo, más la activa si es otra."""
    ruta_modelos = Path(ruta_modelos)
    if not ruta_modelos.is_dir():
        return []
    elegidas: set[tuple[str, str]] = set()
    for carpeta in sorted(p for p in ruta_modelos.iterdir() if p.is_dir()):
        try:
            elegidas.add((carpeta.name, ultima_version(carpeta.name, ruta_modelos)))
        except FileNotFoundError:
            continue  # carpeta sin versiones entrenadas
    if info_activo:
        elegidas.add((info_activo["algoritmo"], info_activo["version"]))

    modelos = []
    for algoritmo, version in sorted(elegidas):
        archivo = ruta_modelos / algoritmo / version / "metadatos.json"
        if not archivo.is_file():
            continue
        metadatos = json.loads(archivo.read_text(encoding="utf-8"))
        es_activo = bool(
            info_activo
            and info_activo["algoritmo"] == algoritmo
            and info_activo["version"] == version
        )
        if es_activo:
            tipo = info_activo.get("tipo", "plano")
        elif tipos_disponibles(metadatos):
            tipo = mejor_tipo(metadatos)
        else:
            continue
        modelos.append(
            ModeloDisponible(
                algoritmo,
                version,
                tipo,
                metadatos,
                info_activo=info_activo if es_activo else None,
                activo=es_activo,
            )
        )
    return modelos


def sincronizar_modelos(
    sesion: Session, ruta_modelos: Path | str, info_activo: dict[str, Any] | None = None
) -> list[Modelo]:
    """Registra (o actualiza) en la tabla `modelo` los modelos de `models/`.

    Solo el activo queda con `activo = true`; los demás no cambian su estado.
    """
    registrados = []
    for disponible in descubrir_modelos(ruta_modelos, info_activo):
        registrados.append(
            repo.registrar_modelo(sesion, **disponible.campos(), activar=disponible.activo)
        )
    return registrados


# --- Métricas detalladas ------------------------------------------------------------------


@dataclass
class MetricasDetalladas:
    particion: str
    documentos: int
    metricas: dict[str, dict[str, float]]
    por_clase: dict[str, list[dict[str, Any]]]
    confusion_dominio: dict[str, Any]
    confusion_area: list[dict[str, Any]]
    revision: dict[str, Any]
    particiones_disponibles: list[str] = field(default_factory=list)


class SinPredicciones(LookupError):  # noqa: N818 - nombre en español
    """No hay predicciones guardadas para esa partición."""


class CalculadoraMetricas:
    """Calcula (y recuerda) las métricas detalladas de cada modelo registrado.

    Args:
        ruta_modelos: carpeta `models/`.
        ruta_datos: carpeta `data/processed/`; solo hace falta para DistilBERT, cuyas
            probabilidades no traen las etiquetas reales.
    """

    def __init__(
        self, ruta_modelos: Path | str, ruta_datos: Path | str, catalogo: Catalogo
    ) -> None:
        self.ruta_modelos = Path(ruta_modelos)
        self.ruta_datos = Path(ruta_datos)
        self.catalogo = catalogo
        self._cache: dict[tuple, MetricasDetalladas] = {}

    def particiones(self, modelo: Modelo) -> list[str]:
        return [p for p in PARTICIONES if self._archivo(modelo, p) is not None]

    def calcular(self, modelo: Modelo, particion: str | None = None) -> MetricasDetalladas:
        """`particion` = `validacion` o `prueba`; por defecto, prueba si existe."""
        disponibles = self.particiones(modelo)
        if not disponibles:
            raise SinPredicciones(
                f"No hay predicciones guardadas del modelo {modelo.id} en {self.ruta_modelos}."
            )
        particion = particion or ("prueba" if "prueba" in disponibles else "validacion")
        if particion not in disponibles:
            raise SinPredicciones(
                f"El modelo {modelo.id} no tiene predicciones de {particion}. "
                f"Disponibles: {', '.join(disponibles)}."
            )
        clave = (modelo.algoritmo, modelo.version, _tipo(modelo), particion)
        if clave not in self._cache:
            predicciones = self._predicciones(modelo, particion)
            umbrales = (modelo.metricas or {}).get("umbrales") or UMBRALES_DISENO
            self._cache[clave] = self._detallar(predicciones, particion, umbrales, disponibles)
        return self._cache[clave]

    # --- Lectura de predicciones ---------------------------------------------------------

    def _carpeta(self, modelo: Modelo) -> Path:
        return self.ruta_modelos / modelo.algoritmo / modelo.version

    def _archivo(self, modelo: Modelo, particion: str) -> Path | None:
        sufijo = PARTICIONES[particion]
        carpeta = self._carpeta(modelo)
        if modelo.algoritmo == "distilbert":
            # Solo la partición de prueba si el notebook 05 ya la evaluó con este modelo.
            if particion == "prueba" and not (carpeta / "evaluacion_test_plano.json").is_file():
                return None
            candidato = carpeta / f"probabilidades_{sufijo}.parquet"
            reales = self.ruta_datos / f"{sufijo}.parquet"
            return candidato if candidato.is_file() and reales.is_file() else None
        candidato = carpeta / f"predicciones_{sufijo}_{_tipo(modelo)}.parquet"
        return candidato if candidato.is_file() else None

    def _predicciones(self, modelo: Modelo, particion: str) -> pd.DataFrame:
        archivo = self._archivo(modelo, particion)
        if modelo.algoritmo != "distilbert":
            return pd.read_parquet(archivo)
        area_a_dominio = {
            a["id"]: d["id"] for d in self.catalogo.categorias["dominios"] for a in d["areas"]
        }
        prediccion = predicciones_desde_probabilidades(pd.read_parquet(archivo), area_a_dominio)
        reales = pd.read_parquet(
            self.ruta_datos / f"{PARTICIONES[particion]}.parquet",
            columns=["id_documento", "id_dominio", "id_area"],
        ).set_index("id_documento")
        reales = reales.loc[prediccion["id_documento"]]
        prediccion["dominio_real"] = reales["id_dominio"].to_numpy()
        prediccion["area_real"] = reales["id_area"].to_numpy()
        return prediccion

    # --- Cálculo -------------------------------------------------------------------------

    def _detallar(
        self,
        p: pd.DataFrame,
        particion: str,
        umbrales: dict[str, float],
        disponibles: list[str],
    ) -> MetricasDetalladas:
        catalogo = self.catalogo
        dominios = [d["id"] for d in catalogo.categorias["dominios"]]
        areas_por_dominio = {
            d["id"]: [a["id"] for a in d["areas"]] for d in catalogo.categorias["dominios"]
        }
        dominio_de_area = {a: d for d, areas in areas_por_dominio.items() for a in areas}

        matriz_dominio = matriz_confusion(p["dominio_real"], p["dominio_pred"], dominios)
        matrices_area = matrices_area_por_dominio(
            p["dominio_real"], p["dominio_pred"], p["area_real"], p["area_pred"], areas_por_dominio
        )
        revision = requiere_revision(
            p["confianza_dominio"].to_numpy(),
            p["confianza_conjunta"].to_numpy(),
            umbrales["umbral_dominio"],
            umbrales["umbral_conjunta"],
        )
        acierto = (p["dominio_pred"] == p["dominio_real"]) & (p["area_pred"] == p["area_real"])
        aceptados = ~np.asarray(revision, dtype=bool)

        return MetricasDetalladas(
            particion=particion,
            documentos=len(p),
            metricas=evaluar(p["dominio_real"], p["dominio_pred"], p["area_real"], p["area_pred"]),
            por_clase={
                "dominio": _por_clase(
                    p["dominio_real"], p["dominio_pred"], dominios, catalogo.nombre_dominio
                ),
                "area": [
                    fila | {"dominio": catalogo.nombre_dominio(dominio_de_area[fila["id"]])}
                    for fila in _por_clase(
                        p["area_real"], p["area_pred"], list(dominio_de_area), catalogo.nombre_area
                    )
                ],
            },
            confusion_dominio={
                "etiquetas": [catalogo.nombre_dominio(d) for d in dominios],
                "matriz": matriz_dominio.to_numpy().tolist(),
            },
            confusion_area=[
                {
                    "dominio": catalogo.nombre_dominio(d),
                    "etiquetas": [catalogo.nombre_area(a) for a in areas_por_dominio[d]],
                    # Columnas: las áreas del dominio y, al final, «otro dominio».
                    "columnas": [catalogo.nombre_area(a) for a in areas_por_dominio[d]]
                    + ["otro dominio"],
                    "matriz": matriz.to_numpy().tolist(),
                }
                for d, matriz in matrices_area.items()
            ],
            revision={
                "umbrales": umbrales,
                "porcentaje": float(np.mean(~aceptados)),
                "accuracy_aceptados": float(acierto[aceptados].mean()) if aceptados.any() else None,
            },
            particiones_disponibles=disponibles,
        )


def _tipo(modelo: Modelo) -> str:
    return (modelo.metricas or {}).get("tipo", "plano")


def _por_clase(real, predicho, etiquetas: list[int], nombre) -> list[dict[str, Any]]:
    """Precisión, recall, F1 y soporte de cada clase, en el orden del catálogo."""
    precision, recall, f1, soporte = precision_recall_fscore_support(
        real, predicho, labels=etiquetas, zero_division=0
    )
    return [
        {
            "id": int(e),
            "nombre": nombre(e),
            "precision": float(precision[i]),
            "recall": float(recall[i]),
            "f1": float(f1[i]),
            "soporte": int(soporte[i]),
        }
        for i, e in enumerate(etiquetas)
    ]
