"""Búsqueda de hiperparámetros con `GridSearchCV` y calibración del mejor modelo.

Está en un módulo propio (y no en `entrenamiento.py`) para que los `.joblib` guarden la
referencia `clasificador_ml.busqueda.BusquedaYCalibracion`: si la clase viviera en el módulo
que se ejecuta con `python -m`, quedaría registrada como `__main__` y la API no podría cargarla.
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Sequence
from typing import Any

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin, clone
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import GridSearchCV, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.utils.validation import check_is_fitted


class BusquedaYCalibracion(ClassifierMixin, BaseEstimator):
    """Elige hiperparámetros con `GridSearchCV` y reentrena el mejor sobre todos los datos.

    Args:
        estimador: `Pipeline` cuyo último paso se llama `clf`.
        parametros: rejilla de `GridSearchCV` (p. ej. `{"clf__C": [0.1, 1.0]}`).
        calibrar: envolver el mejor clasificador en `CalibratedClassifierCV` (sigmoide).
        particiones: particiones de la CV estratificada (se reducen si alguna clase tiene
            menos documentos).
        metrica: métrica de `GridSearchCV`.
        semilla: semilla de las particiones.
        n_jobs: procesos de `GridSearchCV`.
        cache: guardar en disco el TF-IDF de cada partición para no recalcularlo con cada
            valor de la rejilla.
    """

    def __init__(
        self,
        estimador: Pipeline | None = None,
        parametros: dict[str, Sequence] | None = None,
        calibrar: bool = False,
        particiones: int = 5,
        metrica: str = "f1_macro",
        semilla: int = 42,
        n_jobs: int | None = None,
        cache: bool = True,
    ) -> None:
        self.estimador = estimador
        self.parametros = parametros
        self.calibrar = calibrar
        self.particiones = particiones
        self.metrica = metrica
        self.semilla = semilla
        self.n_jobs = n_jobs
        self.cache = cache

    def fit(self, textos: Sequence[str], y: Sequence) -> BusquedaYCalibracion:
        y = np.asarray(y)
        _, conteos = np.unique(y, return_counts=True)
        particiones = int(min(self.particiones, conteos.min()))
        if particiones < 2:
            raise ValueError(
                "Cada clase necesita al menos 2 documentos para la validación cruzada."
            )
        rejilla = {k: list(v) for k, v in (self.parametros or {}).items()}
        combinaciones = int(np.prod([len(v) for v in rejilla.values()])) if rejilla else 1

        self.mejores_parametros_ = {k: v[0] for k, v in rejilla.items()}
        self.resultados_cv_: list[dict[str, Any]] = []
        self.mejor_puntaje_cv_ = None
        if combinaciones > 1:
            self._buscar(textos, y, rejilla, particiones)

        final = clone(self.estimador).set_params(memory=None, **self.mejores_parametros_)
        if self.calibrar:
            final.set_params(
                clf=CalibratedClassifierCV(
                    final.named_steps["clf"], method="sigmoid", cv=particiones, ensemble=False
                )
            )
        self.estimador_ = final.fit(list(textos), y)
        self.classes_ = self.estimador_.classes_
        return self

    def _buscar(self, textos, y, rejilla, particiones) -> None:
        carpeta = tempfile.mkdtemp(prefix="sicda-tfidf-") if self.cache else None
        try:
            busqueda = GridSearchCV(
                clone(self.estimador).set_params(memory=carpeta),
                rejilla,
                scoring=self.metrica,
                cv=StratifiedKFold(particiones, shuffle=True, random_state=self.semilla),
                n_jobs=self.n_jobs,
                refit=False,
            ).fit(list(textos), y)
        finally:
            if carpeta:
                shutil.rmtree(carpeta, ignore_errors=True)
        resultados = busqueda.cv_results_
        self.mejores_parametros_ = dict(busqueda.best_params_)
        self.mejor_puntaje_cv_ = float(busqueda.best_score_)
        self.resultados_cv_ = [
            {
                "parametros": dict(p),
                "media": float(m),
                "desviacion": float(d),
            }
            for p, m, d in zip(
                resultados["params"],
                resultados["mean_test_score"],
                resultados["std_test_score"],
                strict=True,
            )
        ]

    def predict(self, textos: Sequence[str]) -> np.ndarray:
        check_is_fitted(self, "estimador_")
        return self.estimador_.predict(list(textos))

    def predict_proba(self, textos: Sequence[str]) -> np.ndarray:
        check_is_fitted(self, "estimador_")
        return self.estimador_.predict_proba(list(textos))

    def resumen(self) -> dict[str, Any]:
        """Mejores hiperparámetros y resultados de la CV (para `metadatos.json`)."""
        check_is_fitted(self, "estimador_")
        return {
            "mejores_parametros": self.mejores_parametros_,
            "f1_macro_cv": self.mejor_puntaje_cv_,
            "resultados_cv": self.resultados_cv_,
            "clases": len(self.classes_),
            "terminos": len(self.estimador_.named_steps["tfidf"].vocabulary_),
        }
