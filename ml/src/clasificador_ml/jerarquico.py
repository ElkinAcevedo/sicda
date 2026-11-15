"""Clasificador jerárquico: 1 modelo de dominio + 1 modelo de área por dominio (sección 6.5).

También se define `ClasificadorPlano` (un solo modelo de todas las áreas), con la misma
interfaz, para compararlos. Ambos son estimadores de scikit-learn: `fit(textos, id_area)` y
`predict(textos) -> id_area`; el dominio se deduce del área con `area_a_dominio`.

Decodificación (igual para los dos):
1. Dominio = el de mayor `P(dominio)`.
2. Área = la de mayor `P(área | dominio)` **dentro del dominio elegido**, así el par siempre
   es coherente.
3. Confianza conjunta = `P(dominio) · P(área | dominio)`.
4. «Requiere revisión» si `P(dominio) < umbral_dominio` o la conjunta `< umbral_conjunta`.

En el plano, `P(dominio)` es la suma de las probabilidades de sus áreas y
`P(área | dominio) = P(área) / P(dominio)`. Lo mismo sirve para DistilBERT (notebook 04).

Explicabilidad (RF-08): los términos clave son los de mayor peso TF-IDF × coeficiente de la
clase predicha en el modelo de área (o de dominio si el dominio tiene una sola área).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin, clone
from sklearn.dummy import DummyClassifier
from sklearn.pipeline import Pipeline
from sklearn.utils.validation import check_is_fitted

TOP_ALTERNATIVAS = 3
NUM_TERMINOS_CLAVE = 10


# --------------------------------------------------------------------------------------------
# Funciones sobre matrices de probabilidad (las usan ambos clasificadores y DistilBERT)
# --------------------------------------------------------------------------------------------


def condicional_desde_plano(
    p_area: np.ndarray, dominio_de_area: np.ndarray, n_dominios: int
) -> tuple[np.ndarray, np.ndarray]:
    """Convierte `P(área)` en `P(dominio)` y `P(área | dominio)`.

    Args:
        p_area: matriz `(n, áreas)` que suma 1 por fila.
        dominio_de_area: índice (columna de `P(dominio)`) del dominio de cada área.
        n_dominios: número de dominios.
    """
    p_dominio = p_area @ np.eye(n_dominios)[dominio_de_area]
    denominador = p_dominio[:, dominio_de_area]
    p_condicional = np.divide(
        p_area, denominador, out=np.zeros_like(p_area, dtype=float), where=denominador > 0
    )
    return p_dominio, p_condicional


def decodificar(
    p_dominio: np.ndarray, p_condicional: np.ndarray, dominio_de_area: np.ndarray
) -> dict[str, np.ndarray]:
    """Elige el dominio y, dentro de él, el área. Devuelve índices de columna y confianzas."""
    filas = np.arange(p_dominio.shape[0])
    dominio = p_dominio.argmax(axis=1)
    dentro = dominio_de_area[None, :] == dominio[:, None]
    area = np.where(dentro, p_condicional, -1.0).argmax(axis=1)
    confianza_dominio = p_dominio[filas, dominio]
    confianza_area = p_condicional[filas, area]
    return {
        "dominio": dominio,
        "area": area,
        "confianza_dominio": confianza_dominio,
        "confianza_area": confianza_area,
        "confianza_conjunta": confianza_dominio * confianza_area,
    }


def requiere_revision(
    confianza_dominio: np.ndarray,
    confianza_conjunta: np.ndarray,
    umbral_dominio: float,
    umbral_conjunta: float,
) -> np.ndarray:
    """`True` cuando alguna de las dos confianzas queda por debajo de su umbral."""
    return (np.asarray(confianza_dominio) < umbral_dominio) | (
        np.asarray(confianza_conjunta) < umbral_conjunta
    )


# --------------------------------------------------------------------------------------------
# Explicabilidad
# --------------------------------------------------------------------------------------------


def _estimador_final(modelo: Any) -> Any:
    """Quita las envolturas de búsqueda (`estimador_` o `best_estimator_`)."""
    for atributo in ("estimador_", "best_estimator_"):
        if hasattr(modelo, atributo):
            return _estimador_final(getattr(modelo, atributo))
    return modelo


def matriz_pesos(clasificador: Any) -> np.ndarray | None:
    """Pesos `(clases, términos)` de un clasificador lineal; `None` si no los tiene.

    - `LinearSVC` y similares: `coef_` (en binario se agrega la fila de la clase negativa).
    - `CalibratedClassifierCV`: promedio de los `coef_` de sus estimadores internos.
    - Naive Bayes: `feature_log_prob_` centrado por término, para que destaquen los términos
      que distinguen a la clase y no los que son frecuentes en todas.
    """
    if hasattr(clasificador, "calibrated_classifiers_"):
        internos = [matriz_pesos(c.estimator) for c in clasificador.calibrated_classifiers_]
        if any(p is None for p in internos):
            return None
        return np.mean(internos, axis=0)
    if hasattr(clasificador, "coef_"):
        coef = np.asarray(
            clasificador.coef_.toarray()
            if hasattr(clasificador.coef_, "toarray")
            else clasificador.coef_
        )
        return np.vstack([-coef, coef]) if coef.shape[0] == 1 else coef
    if hasattr(clasificador, "feature_log_prob_"):
        pesos = np.asarray(clasificador.feature_log_prob_)
        return pesos - pesos.mean(axis=0, keepdims=True)
    return None


def terminos_clave(
    modelo: Any, texto: str, clase: Any, cantidad: int = NUM_TERMINOS_CLAVE
) -> list[dict[str, Any]]:
    """Términos del texto con mayor peso TF-IDF × coeficiente de `clase`.

    `modelo` debe ser un `Pipeline` cuyo último paso es el clasificador y cuyo penúltimo paso
    tiene `get_feature_names_out` (el `TfidfVectorizer`). Si no, devuelve una lista vacía.
    """
    modelo = _estimador_final(modelo)
    if not isinstance(modelo, Pipeline) or len(modelo.steps) < 2:
        return []
    clasificador = _estimador_final(modelo.steps[-1][1])
    pesos = matriz_pesos(clasificador)
    clases = list(getattr(clasificador, "classes_", []))
    if pesos is None or clase not in clases:
        return []
    transformador = modelo[:-1]
    vector = transformador.transform([texto]).tocsr()
    if vector.nnz == 0:
        return []
    contribucion = vector.data * pesos[clases.index(clase), vector.indices]
    orden = np.argsort(-contribucion)[:cantidad]
    vocabulario = modelo.steps[-2][1].get_feature_names_out()
    return [
        {"termino": str(vocabulario[vector.indices[i]]), "peso": round(float(contribucion[i]), 4)}
        for i in orden
        if contribucion[i] > 0
    ]


# --------------------------------------------------------------------------------------------
# Clasificadores
# --------------------------------------------------------------------------------------------


class _ClasificadorPorNiveles(ClassifierMixin, BaseEstimator):
    """Base común: decodificación, revisión, alternativas y términos clave.

    Las subclases definen `fit` (que debe llamar a `_preparar_etiquetas`),
    `_probabilidades(textos) -> (P(dominio), P(área | dominio))` y
    `_modelo_explicativo(indice_dominio)`.

    Si `preprocesador` no es `None`, se aplica a los textos antes de clasificar (y de
    entrenar). Para entrenar con `texto_procesado` ya calculado se deja en `None` y se asigna
    al publicar el modelo, para que la API reciba texto crudo.
    """

    def _preparar_etiquetas(self, y: Sequence[int]) -> np.ndarray:
        if not self.area_a_dominio:
            raise ValueError("Falta `area_a_dominio` (id_area -> id_dominio).")
        y = np.asarray(y)
        faltantes = set(np.unique(y)) - set(self.area_a_dominio)
        if faltantes:
            raise ValueError(f"Áreas sin dominio en `area_a_dominio`: {sorted(faltantes)}")
        self.areas_ = np.unique(y)
        self.classes_ = self.areas_
        dominios_area = np.array([self.area_a_dominio[a] for a in self.areas_])
        self.dominios_ = np.unique(dominios_area)
        self.dominio_de_area_ = np.searchsorted(self.dominios_, dominios_area)
        return np.array([self.area_a_dominio[a] for a in y])

    def _preparar_textos(self, textos: Sequence[str]) -> list[str]:
        textos = list(textos)
        if self.preprocesador is not None:
            return list(self.preprocesador.transform(textos))
        return textos

    def _alinear(self, probabilidades: np.ndarray, clases: Sequence, destino: np.ndarray):
        """Reordena las columnas de `predict_proba` según `destino` (ceros si falta alguna)."""
        resultado = np.zeros((probabilidades.shape[0], len(destino)))
        columnas = np.searchsorted(destino, np.asarray(clases))
        resultado[:, columnas] = probabilidades
        return resultado

    def _decodificar_procesados(self, textos: list[str]):
        p_dominio, p_condicional = self._probabilidades(textos)
        return (
            p_dominio,
            p_condicional,
            decodificar(p_dominio, p_condicional, self.dominio_de_area_),
        )

    # --- interfaz de scikit-learn --------------------------------------------------------

    def predict(self, textos: Sequence[str]) -> np.ndarray:
        """Área predicha (`id_area`) de cada texto."""
        check_is_fitted(self, "areas_")
        _, _, decision = self._decodificar_procesados(self._preparar_textos(textos))
        return self.areas_[decision["area"]]

    def predict_proba(self, textos: Sequence[str]) -> np.ndarray:
        """Probabilidad conjunta `P(dominio)·P(área | dominio)` de cada área (`classes_`)."""
        check_is_fitted(self, "areas_")
        p_dominio, p_condicional = self._probabilidades(self._preparar_textos(textos))
        return p_dominio[:, self.dominio_de_area_] * p_condicional

    # --- interfaz propia -----------------------------------------------------------------

    def predecir_niveles(self, textos: Sequence[str]) -> pd.DataFrame:
        """Dominio, área, confianzas y «requiere revisión» de cada texto (para evaluar)."""
        check_is_fitted(self, "areas_")
        _, _, decision = self._decodificar_procesados(self._preparar_textos(textos))
        tabla = pd.DataFrame(
            {
                "dominio_pred": self.dominios_[decision["dominio"]],
                "area_pred": self.areas_[decision["area"]],
                "confianza_dominio": decision["confianza_dominio"],
                "confianza_area": decision["confianza_area"],
                "confianza_conjunta": decision["confianza_conjunta"],
            }
        )
        tabla["requiere_revision"] = requiere_revision(
            tabla["confianza_dominio"],
            tabla["confianza_conjunta"],
            self.umbral_dominio,
            self.umbral_conjunta,
        )
        return tabla

    def predecir_detallado(
        self,
        textos: Sequence[str],
        alternativas: int = TOP_ALTERNATIVAS,
        num_terminos: int = NUM_TERMINOS_CLAVE,
    ) -> list[dict[str, Any]]:
        """Resultado completo por texto, en el formato que usa la API.

        Las alternativas de dominio están ordenadas por `P(dominio)`; las de área, por
        `P(área | dominio)` dentro del dominio predicho. La primera es siempre la elegida.
        """
        check_is_fitted(self, "areas_")
        procesados = self._preparar_textos(textos)
        p_dominio, p_condicional, decision = self._decodificar_procesados(procesados)
        resultados = []
        for i, texto in enumerate(procesados):
            d, a = decision["dominio"][i], decision["area"][i]
            areas_dominio = np.flatnonzero(self.dominio_de_area_ == d)
            orden_dominio = np.argsort(-p_dominio[i])[:alternativas]
            orden_area = areas_dominio[np.argsort(-p_condicional[i, areas_dominio])][:alternativas]
            conjunta = float(decision["confianza_conjunta"][i])
            confianza_dominio = float(decision["confianza_dominio"][i])
            area = int(self.areas_[a])
            resultados.append(
                {
                    "dominio": {
                        "id": int(self.dominios_[d]),
                        "confianza": confianza_dominio,
                        "alternativas": [
                            {"id": int(self.dominios_[j]), "confianza": float(p_dominio[i, j])}
                            for j in orden_dominio
                        ],
                    },
                    "area": {
                        "id": area,
                        "confianza": float(decision["confianza_area"][i]),
                        "alternativas": [
                            {"id": int(self.areas_[j]), "confianza": float(p_condicional[i, j])}
                            for j in orden_area
                        ],
                    },
                    "confianza_conjunta": conjunta,
                    "requiere_revision": bool(
                        requiere_revision(
                            confianza_dominio, conjunta, self.umbral_dominio, self.umbral_conjunta
                        )
                    ),
                    "terminos_clave": self._terminos(texto, d, area, num_terminos),
                }
            )
        return resultados

    def _terminos(self, texto: str, indice_dominio: int, area: int, cantidad: int):
        modelo, clase = self._modelo_explicativo(indice_dominio)
        clase = area if clase is None else clase
        return terminos_clave(modelo, texto, clase, cantidad)


class ClasificadorJerarquico(_ClasificadorPorNiveles):
    """Un modelo de dominio y, por cada dominio, un modelo de sus áreas.

    Args:
        area_a_dominio: `id_area -> id_dominio`.
        estimador: plantilla (se clona) del modelo de dominio; debe tener `predict_proba`.
        estimador_area: plantilla de los modelos de área (por defecto, `estimador`).
        preprocesador: transformador aplicado a los textos antes de clasificar.
        umbral_dominio, umbral_conjunta: umbrales de «requiere revisión».
    """

    def __init__(
        self,
        area_a_dominio: Mapping[int, int] | None = None,
        estimador: Any = None,
        estimador_area: Any = None,
        preprocesador: Any = None,
        umbral_dominio: float = 0.60,
        umbral_conjunta: float = 0.40,
    ) -> None:
        self.area_a_dominio = area_a_dominio
        self.estimador = estimador
        self.estimador_area = estimador_area
        self.preprocesador = preprocesador
        self.umbral_dominio = umbral_dominio
        self.umbral_conjunta = umbral_conjunta

    def fit(self, textos: Sequence[str], y: Sequence[int]) -> ClasificadorJerarquico:
        if self.estimador is None:
            raise ValueError("Falta `estimador`.")
        textos = np.asarray(self._preparar_textos(textos), dtype=object)
        y = np.asarray(y)
        dominios = self._preparar_etiquetas(y)
        plantilla_area = self.estimador if self.estimador_area is None else self.estimador_area

        self.modelo_dominio_ = clone(self.estimador).fit(list(textos), dominios)
        self.modelos_area_ = {}
        for dominio in self.dominios_:
            mascara = dominios == dominio
            areas = y[mascara]
            modelo = (
                DummyClassifier(strategy="most_frequent")
                if len(np.unique(areas)) == 1
                else clone(plantilla_area)
            )
            self.modelos_area_[int(dominio)] = modelo.fit(list(textos[mascara]), areas)
        return self

    def _probabilidades(self, textos: list[str]) -> tuple[np.ndarray, np.ndarray]:
        p_dominio = self._alinear(
            self.modelo_dominio_.predict_proba(textos),
            self.modelo_dominio_.classes_,
            self.dominios_,
        )
        p_condicional = np.zeros((len(textos), len(self.areas_)))
        for modelo in self.modelos_area_.values():
            p_condicional += self._alinear(
                modelo.predict_proba(textos), modelo.classes_, self.areas_
            )
        return p_dominio, p_condicional

    def _modelo_explicativo(self, indice_dominio: int):
        dominio = int(self.dominios_[indice_dominio])
        modelo = self.modelos_area_[dominio]
        if isinstance(modelo, DummyClassifier):
            return self.modelo_dominio_, dominio
        return modelo, None

    def submodelos(self) -> dict[str, Any]:
        """Modelos ajustados por nombre: `dominio` y `area_<id_dominio>`."""
        check_is_fitted(self, "modelo_dominio_")
        return {
            "dominio": self.modelo_dominio_,
            **{f"area_{d}": m for d, m in self.modelos_area_.items()},
        }


class ClasificadorPlano(_ClasificadorPorNiveles):
    """Un único modelo de todas las áreas; el dominio se deduce sumando sus áreas.

    Mismos argumentos que `ClasificadorJerarquico`, salvo `estimador_area`.
    """

    def __init__(
        self,
        area_a_dominio: Mapping[int, int] | None = None,
        estimador: Any = None,
        preprocesador: Any = None,
        umbral_dominio: float = 0.60,
        umbral_conjunta: float = 0.40,
    ) -> None:
        self.area_a_dominio = area_a_dominio
        self.estimador = estimador
        self.preprocesador = preprocesador
        self.umbral_dominio = umbral_dominio
        self.umbral_conjunta = umbral_conjunta

    def fit(self, textos: Sequence[str], y: Sequence[int]) -> ClasificadorPlano:
        if self.estimador is None:
            raise ValueError("Falta `estimador`.")
        textos = self._preparar_textos(textos)
        self._preparar_etiquetas(y)
        self.modelo_ = clone(self.estimador).fit(textos, np.asarray(y))
        return self

    def _probabilidades(self, textos: list[str]) -> tuple[np.ndarray, np.ndarray]:
        p_area = self._alinear(
            self.modelo_.predict_proba(textos), self.modelo_.classes_, self.areas_
        )
        return condicional_desde_plano(p_area, self.dominio_de_area_, len(self.dominios_))

    def _modelo_explicativo(self, indice_dominio: int):  # noqa: ARG002 - mismo modelo siempre
        return self.modelo_, None

    def submodelos(self) -> dict[str, Any]:
        check_is_fitted(self, "modelo_")
        return {"plano": self.modelo_}
