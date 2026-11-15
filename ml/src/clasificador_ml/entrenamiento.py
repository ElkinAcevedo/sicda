"""Entrenamiento de los modelos clásicos: Complement NB y SVM lineal (secciones 6.4 y 6.6).

Para cada algoritmo se entrena el clasificador jerárquico (1 modelo de dominio + 1 de área por
dominio) y el plano (todas las áreas), se evalúan en **validación** y se guardan en
`models/<algoritmo>/<version>/`:

- `jerarquico.joblib`, `plano.joblib`: modelos listos para la API (incluyen el
  `Preprocesador`, así reciben texto crudo).
- `predicciones_val_<tipo>.parquet`: predicciones y confianzas en validación (para comparar
  modelos y calibrar los umbrales en el notebook 05).
- `metadatos.json`: versión, configuración, mejores hiperparámetros de cada submodelo,
  métricas de validación y tiempos (RNF-08).

Cada submodelo es un `Pipeline(TF-IDF, clasificador)` propio. Sus hiperparámetros se eligen
con `GridSearchCV` (CV estratificada de 5 particiones sobre train, F1-macro). En el SVM la
búsqueda se hace sin calibrar y solo el mejor `C` se calibra con `CalibratedClassifierCV`.

El conjunto de prueba **no** se usa aquí: se evalúa una sola vez en el notebook 05.

Uso:
    python -m clasificador_ml.entrenamiento --config ml/configs/svm.yaml
    python -m clasificador_ml.entrenamiento --config ml/configs/naive_bayes.yaml --muestra 0.1
"""

from __future__ import annotations

import argparse
import shutil
import tempfile
import time
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin, clone
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import GridSearchCV, StratifiedKFold
from sklearn.naive_bayes import ComplementNB
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC
from sklearn.utils.validation import check_is_fitted

from clasificador_ml.configuracion import cargar_configuracion
from clasificador_ml.evaluacion import evaluar, guardar_json
from clasificador_ml.jerarquico import ClasificadorJerarquico, ClasificadorPlano
from clasificador_ml.preprocesamiento import Preprocesador
from clasificador_ml.rutas import DATOS_PROCESADOS, MODELOS

TIPOS = {"jerarquico": ClasificadorJerarquico, "plano": ClasificadorPlano}
COLUMNA_TEXTO = "texto_procesado"


# --------------------------------------------------------------------------------------------
# Búsqueda de hiperparámetros + calibración
# --------------------------------------------------------------------------------------------


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


def construir_estimador(config: dict[str, Any], n_jobs: int | None = None) -> BusquedaYCalibracion:
    """Crea la plantilla `Pipeline(TF-IDF, clasificador)` + búsqueda a partir del YAML.

    En `hiperparametros`, los valores en lista forman la rejilla y los escalares se fijan.
    """
    tfidf = dict(config.get("tfidf", {}))
    if "ngram_range" in tfidf:
        tfidf["ngram_range"] = tuple(tfidf["ngram_range"])
    semilla = config.get("semilla", 42)
    algoritmo = config.get("modelo")
    hiperparametros = config.get("hiperparametros", {})
    fijos = {k: v for k, v in hiperparametros.items() if not isinstance(v, list)}
    rejilla = {f"clf__{k}": v for k, v in hiperparametros.items() if isinstance(v, list)}

    if algoritmo == "complement_nb":
        clasificador = ComplementNB(**fijos)
    elif algoritmo == "linear_svc":
        clasificador = LinearSVC(random_state=semilla, **fijos)
    else:
        raise ValueError(f"Algoritmo no soportado: {algoritmo!r}")

    pipeline = Pipeline([("tfidf", TfidfVectorizer(**tfidf)), ("clf", clasificador)])
    return BusquedaYCalibracion(
        pipeline,
        rejilla,
        calibrar=bool(config.get("calibrar_probabilidades", False)),
        particiones=config.get("validacion_cruzada", {}).get("particiones", 5),
        semilla=semilla,
        n_jobs=n_jobs,
    )


# --------------------------------------------------------------------------------------------
# Datos
# --------------------------------------------------------------------------------------------


def cargar_particiones(
    directorio: Path | str = DATOS_PROCESADOS / "preprocesado",
    nombres: Sequence[str] = ("train", "val"),
) -> dict[str, pd.DataFrame]:
    """Lee las particiones preprocesadas (con `texto_procesado`)."""
    directorio = Path(directorio)
    particiones = {}
    for nombre in nombres:
        ruta = directorio / f"{nombre}.parquet"
        if not ruta.is_file():
            raise FileNotFoundError(
                f"No existe {ruta}. Ejecuta antes: python -m clasificador_ml.preprocesamiento"
            )
        particiones[nombre] = pd.read_parquet(ruta)
    return particiones


def mapa_area_dominio(df: pd.DataFrame) -> dict[int, int]:
    """`id_area -> id_dominio` según las columnas de la partición."""
    pares = df[["id_area", "id_dominio"]].drop_duplicates()
    if pares["id_area"].duplicated().any():
        raise ValueError("Hay áreas asociadas a más de un dominio.")
    return {int(a): int(d) for a, d in pares.itertuples(index=False)}


def muestrear(df: pd.DataFrame, fraccion: float, semilla: int, minimo: int = 10) -> pd.DataFrame:
    """Muestra estratificada por área (al menos `minimo` documentos por área si los hay)."""
    if not 0 < fraccion <= 1:
        raise ValueError("La fracción de la muestra debe estar en (0, 1].")
    if fraccion == 1:
        return df
    partes = [
        grupo.sample(
            n=min(len(grupo), max(minimo, round(len(grupo) * fraccion))), random_state=semilla
        )
        for _, grupo in df.groupby("id_area")
    ]
    return pd.concat(partes).sort_index()


# --------------------------------------------------------------------------------------------
# Entrenamiento y evaluación
# --------------------------------------------------------------------------------------------


def medir_tiempo(modelo, textos: Sequence[str]) -> dict[str, float]:
    """Milisegundos por documento de `predecir_detallado`, uno a uno, con texto crudo (RNF-01)."""
    textos = list(textos)
    if not textos:
        return {}
    modelo.predecir_detallado(textos[:1])  # calentamiento (carga de spaCy)
    tiempos = []
    for texto in textos:
        inicio = time.perf_counter()
        modelo.predecir_detallado([texto])
        tiempos.append((time.perf_counter() - inicio) * 1000)
    return {
        "documentos": len(tiempos),
        "media_ms": float(np.mean(tiempos)),
        "p95_ms": float(np.percentile(tiempos, 95)),
        "max_ms": float(np.max(tiempos)),
    }


def resumen_submodelos(modelo) -> dict[str, Any]:
    return {
        nombre: submodelo.resumen()
        for nombre, submodelo in modelo.submodelos().items()
        if hasattr(submodelo, "resumen")
    }


def entrenar_tipo(
    tipo: str,
    config: dict[str, Any],
    train: pd.DataFrame,
    val: pd.DataFrame,
    area_a_dominio: dict[int, int],
    n_jobs: int | None = None,
    docs_tiempo: int = 100,
) -> tuple[Any, dict[str, Any], pd.DataFrame]:
    """Entrena un tipo (`jerarquico` o `plano`), lo evalúa en validación y mide su tiempo."""
    revision = config.get("revision", {})
    modelo = TIPOS[tipo](
        area_a_dominio=area_a_dominio,
        estimador=construir_estimador(config, n_jobs=n_jobs),
        umbral_dominio=revision.get("umbral_confianza_dominio", 0.60),
        umbral_conjunta=revision.get("umbral_confianza_conjunta", 0.40),
    )
    inicio = time.perf_counter()
    modelo.fit(train[COLUMNA_TEXTO].tolist(), train["id_area"].to_numpy())
    segundos = time.perf_counter() - inicio

    predicciones = modelo.predecir_niveles(val[COLUMNA_TEXTO].tolist())
    predicciones.insert(0, "id_documento", val["id_documento"].to_numpy())
    predicciones.insert(1, "dominio_real", val["id_dominio"].to_numpy())
    predicciones.insert(2, "area_real", val["id_area"].to_numpy())
    metricas = evaluar(
        predicciones["dominio_real"],
        predicciones["dominio_pred"],
        predicciones["area_real"],
        predicciones["area_pred"],
    )

    # El modelo publicado recibe texto crudo, igual que la API.
    modelo.preprocesador = Preprocesador.desde_configuracion(config)
    tiempo = medir_tiempo(modelo, val["texto"].head(docs_tiempo).tolist())

    informe = {
        "metricas_validacion": metricas,
        "porcentaje_revision_validacion": float(predicciones["requiere_revision"].mean()),
        "tiempo_entrenamiento_s": round(segundos, 1),
        "tiempo_prediccion": tiempo,
        "submodelos": resumen_submodelos(modelo),
    }
    return modelo, informe, predicciones


def entrenar(
    config: dict[str, Any],
    tipos: Sequence[str] = ("jerarquico", "plano"),
    version: str | None = None,
    muestra: float = 1.0,
    origen: Path | str = DATOS_PROCESADOS / "preprocesado",
    destino: Path | str = MODELOS,
    n_jobs: int | None = -1,
    docs_tiempo: int = 100,
) -> Path:
    """Entrena, evalúa en validación y guarda los artefactos. Devuelve la carpeta creada."""
    version = version or datetime.now().strftime("%Y%m%d-%H%M")
    semilla = config.get("semilla", 42)
    particiones = cargar_particiones(origen)
    train, val = particiones["train"], particiones["val"]
    if muestra < 1:
        train = muestrear(train, muestra, semilla)
        val = muestrear(val, muestra, semilla, minimo=1)
    area_a_dominio = mapa_area_dominio(train)

    carpeta = Path(destino) / config["modelo"] / version
    carpeta.mkdir(parents=True, exist_ok=True)
    metadatos: dict[str, Any] = {
        "algoritmo": config["modelo"],
        "version": version,
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "configuracion": config,
        "datos": {"train": len(train), "val": len(val), "muestra": muestra},
        "tipos": {},
    }
    for tipo in tipos:
        print(f"[{config['modelo']}] entrenando {tipo} con {len(train)} documentos…", flush=True)
        modelo, informe, predicciones = entrenar_tipo(
            tipo, config, train, val, area_a_dominio, n_jobs=n_jobs, docs_tiempo=docs_tiempo
        )
        joblib.dump(modelo, carpeta / f"{tipo}.joblib", compress=3)
        predicciones.to_parquet(carpeta / f"predicciones_val_{tipo}.parquet", index=False)
        informe["archivo"] = f"{tipo}.joblib"
        metadatos["tipos"][tipo] = informe
        guardar_json(metadatos, carpeta / "metadatos.json")
        _imprimir(tipo, informe)
    print(f"Artefactos en {carpeta}")
    return carpeta


def _imprimir(tipo: str, informe: dict[str, Any]) -> None:
    metricas = informe["metricas_validacion"]
    tiempo = informe["tiempo_prediccion"]
    print(
        f"  {tipo}: F1-macro dominio {metricas['dominio']['f1_macro']:.4f} · "
        f"área {metricas['area']['f1_macro']:.4f} · "
        f"jerárquico {metricas['jerarquico']['f1_macro']:.4f} · "
        f"accuracy jerárquica {metricas['jerarquico']['accuracy']:.4f} · "
        f"entrenamiento {informe['tiempo_entrenamiento_s']:.0f} s · "
        f"predicción {tiempo.get('media_ms', float('nan')):.0f} ms/doc"
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Entrena NB o SVM (Fase III).")
    parser.add_argument("--config", type=Path, required=True, help="YAML del modelo")
    parser.add_argument("--tipo", choices=[*TIPOS, "ambos"], default="ambos")
    parser.add_argument("--version", help="Nombre de la versión (por defecto, fecha y hora)")
    parser.add_argument("--muestra", type=float, default=1.0, help="Fracción de los datos (0-1]")
    parser.add_argument("--procesos", type=int, default=-1, help="Procesos de GridSearchCV")
    parser.add_argument("--docs-tiempo", type=int, default=100, help="Documentos para medir")
    parser.add_argument("--origen", type=Path, default=DATOS_PROCESADOS / "preprocesado")
    parser.add_argument("--destino", type=Path, default=MODELOS)
    args = parser.parse_args(argv)

    tipos = list(TIPOS) if args.tipo == "ambos" else [args.tipo]
    entrenar(
        cargar_configuracion(args.config),
        tipos=tipos,
        version=args.version,
        muestra=args.muestra,
        origen=args.origen,
        destino=args.destino,
        n_jobs=args.procesos,
        docs_tiempo=args.docs_tiempo,
    )


if __name__ == "__main__":
    main()
