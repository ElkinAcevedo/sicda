"""Métricas por nivel: accuracy, precisión, recall, F1 (macro y ponderado) y matriz de confusión
(sección 6.6 del diseño).

Niveles que se reportan:
- `dominio`: las 7 clases de `Y1`.
- `area`: las 136 áreas (`id_area`, único en todo el dataset).
- `jerarquico`: el documento cuenta como acierto solo si el dominio **y** el área son
  correctos. El F1-macro jerárquico es el criterio de selección de modelos.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
)

# Etiqueta que se asigna al área cuando el dominio predicho es incorrecto.
FUERA_DEL_DOMINIO = -1


def metricas_nivel(y_real: Sequence, y_pred: Sequence, etiquetas: Sequence | None = None) -> dict:
    """Accuracy, precisión, recall y F1 macro y ponderados de un nivel.

    Args:
        y_real: etiquetas verdaderas.
        y_pred: etiquetas predichas.
        etiquetas: clases sobre las que se promedia. Por defecto, las de `y_real`; así una
            predicción que no corresponde a ninguna clase real cuenta como error sin agregar
            una clase nueva al promedio.
    """
    y_real, y_pred = np.asarray(y_real), np.asarray(y_pred)
    if etiquetas is None:
        etiquetas = np.unique(y_real)
    resultado = {"accuracy": float(accuracy_score(y_real, y_pred))}
    for promedio in ("macro", "weighted"):
        precision, recall, f1, _ = precision_recall_fscore_support(
            y_real, y_pred, labels=etiquetas, average=promedio, zero_division=0
        )
        sufijo = "macro" if promedio == "macro" else "ponderado"
        resultado[f"precision_{sufijo}"] = float(precision)
        resultado[f"recall_{sufijo}"] = float(recall)
        resultado[f"f1_{sufijo}"] = float(f1)
    return resultado


def area_jerarquica(
    dominio_real: Sequence, dominio_pred: Sequence, area_pred: Sequence
) -> np.ndarray:
    """Área predicha, reemplazada por `FUERA_DEL_DOMINIO` cuando el dominio está mal."""
    dominio_real, dominio_pred = np.asarray(dominio_real), np.asarray(dominio_pred)
    return np.where(dominio_real == dominio_pred, np.asarray(area_pred), FUERA_DEL_DOMINIO)


def evaluar(
    dominio_real: Sequence,
    dominio_pred: Sequence,
    area_real: Sequence,
    area_pred: Sequence,
) -> dict[str, dict[str, float]]:
    """Métricas de los tres niveles: `dominio`, `area` y `jerarquico`."""
    area_real = np.asarray(area_real)
    jerarquica = area_jerarquica(dominio_real, dominio_pred, area_pred)
    return {
        "dominio": metricas_nivel(dominio_real, dominio_pred),
        "area": metricas_nivel(area_real, area_pred),
        "jerarquico": metricas_nivel(area_real, jerarquica, etiquetas=np.unique(area_real)),
    }


def tabla_metricas(informes: dict[str, dict[str, dict[str, float]]]) -> pd.DataFrame:
    """Une varios resultados de `evaluar` en una tabla (fila = modelo y nivel)."""
    filas = [
        {"modelo": modelo, "nivel": nivel, **metricas}
        for modelo, niveles in informes.items()
        for nivel, metricas in niveles.items()
    ]
    return pd.DataFrame(filas).set_index(["modelo", "nivel"])


def reporte_por_clase(
    y_real: Sequence, y_pred: Sequence, nombres: dict[int, str] | None = None
) -> pd.DataFrame:
    """Precisión, recall, F1 y soporte de cada clase, ordenado de peor a mejor F1."""
    etiquetas = np.unique(y_real)
    reporte = classification_report(
        y_real, y_pred, labels=etiquetas, output_dict=True, zero_division=0
    )
    filas = {int(e): reporte[str(e)] for e in etiquetas}
    tabla = pd.DataFrame.from_dict(filas, orient="index").rename(
        columns={"f1-score": "f1", "support": "soporte"}
    )
    tabla["soporte"] = tabla["soporte"].astype(int)
    if nombres:
        tabla.insert(0, "nombre", [nombres.get(i, str(i)) for i in tabla.index])
    return tabla.sort_values("f1")


def matriz_confusion(
    y_real: Sequence,
    y_pred: Sequence,
    etiquetas: Sequence,
    nombres: dict[Any, str] | None = None,
) -> pd.DataFrame:
    """Matriz de confusión con filas = clase real y columnas = clase predicha."""
    matriz = confusion_matrix(y_real, y_pred, labels=list(etiquetas))
    rotulos = [nombres.get(e, e) if nombres else e for e in etiquetas]
    tabla = pd.DataFrame(matriz, index=rotulos, columns=rotulos)
    tabla.index.name, tabla.columns.name = "real", "predicho"
    return tabla


def matrices_area_por_dominio(
    dominio_real: Sequence,
    dominio_pred: Sequence,
    area_real: Sequence,
    area_pred: Sequence,
    areas_por_dominio: dict[int, Sequence[int]],
    nombres_area: dict[int, str] | None = None,
) -> dict[int, pd.DataFrame]:
    """Una matriz de áreas por dominio real.

    Incluye solo los documentos cuyo dominio real es el de la matriz. Los que se enviaron a
    otro dominio aparecen en la columna `otro dominio`.
    """
    dominio_real = np.asarray(dominio_real)
    area_real = np.asarray(area_real)
    jerarquica = area_jerarquica(dominio_real, dominio_pred, area_pred)
    nombres = {**(nombres_area or {}), FUERA_DEL_DOMINIO: "otro dominio"}
    matrices = {}
    for dominio, areas in areas_por_dominio.items():
        mascara = dominio_real == dominio
        etiquetas = [*areas, FUERA_DEL_DOMINIO]
        matriz = matriz_confusion(area_real[mascara], jerarquica[mascara], etiquetas, nombres)
        # La fila «otro dominio» siempre está vacía: el área real pertenece al dominio.
        matrices[dominio] = matriz.drop(index=nombres[FUERA_DEL_DOMINIO])
    return matrices


def guardar_json(datos: dict, ruta: Path | str) -> Path:
    """Guarda un diccionario como JSON legible (UTF-8, con sangría)."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(
        json.dumps(datos, ensure_ascii=False, indent=2, default=_a_json), encoding="utf-8"
    )
    return ruta


def _a_json(valor: Any) -> Any:
    if isinstance(valor, np.integer):
        return int(valor)
    if isinstance(valor, np.floating):
        return float(valor)
    if isinstance(valor, np.ndarray | tuple):
        return list(valor)
    raise TypeError(f"Tipo no serializable a JSON: {type(valor).__name__}")
