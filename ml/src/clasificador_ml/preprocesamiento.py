"""Limpieza y normalización de texto en inglés (Fase II).

Pasos:
1. Unicode NFKD sin tildes y minúsculas.
2. Quitar URL, correos, números y puntuación (solo quedan letras a-z).
3. Lematizar con spaCy (`en_core_web_sm`, sin parser ni NER).
4. Quitar *stopwords* de NLTK y tokens cortos.

Se lematiza antes de quitar las *stopwords* para que el etiquetador de spaCy vea la frase
completa; las *stopwords* se comparan tanto con la palabra como con su lema.

`Preprocesador` es un transformador de scikit-learn: se guarda dentro del pipeline del modelo
(`joblib`), así la API procesa el texto exactamente igual que el entrenamiento.

Uso (genera `data/processed/preprocesado/{train,val,test}.parquet`):
    python -m clasificador_ml.preprocesamiento --procesos 4
"""

from __future__ import annotations

import argparse
import re
import time
import unicodedata
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin

from clasificador_ml.configuracion import cargar_configuracion
from clasificador_ml.rutas import DATOS_PROCESADOS

MODELO_SPACY = "en_core_web_sm"
# Componentes de spaCy que no hacen falta para lematizar (ahorran ~60 % del tiempo).
COMPONENTES_DESACTIVADOS = ["parser", "ner"]

_URL = re.compile(r"https?://\S+|www\.\S+")
_CORREO = re.compile(r"\S+@\S+\.\S+")
_NO_LETRAS = re.compile(r"[^a-z]+")


@lru_cache(maxsize=1)
def _stopwords() -> frozenset[str]:
    try:
        from nltk.corpus import stopwords

        return frozenset(stopwords.words("english"))
    except LookupError as error:
        raise RuntimeError(
            "Faltan las stopwords de NLTK. Ejecuta: python -m nltk.downloader stopwords"
        ) from error


@lru_cache(maxsize=1)
def _spacy():
    import spacy

    try:
        return spacy.load(MODELO_SPACY, disable=COMPONENTES_DESACTIVADOS)
    except OSError as error:
        raise RuntimeError(
            f"Falta el modelo de spaCy '{MODELO_SPACY}'. Ejecuta scripts/configurar_entorno.sh"
        ) from error


def normalizar(texto: str) -> str:
    """Pasos 1 y 2: minúsculas, sin tildes, sin URL/correos/números/puntuación."""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c)).lower()
    texto = _URL.sub(" ", texto)
    texto = _CORREO.sub(" ", texto)
    return _NO_LETRAS.sub(" ", texto).strip()


class Preprocesador(BaseEstimator, TransformerMixin):
    """Transforma una lista de textos en textos limpios, listos para TF-IDF.

    Args:
        lematizar: aplicar lematización con spaCy.
        quitar_stopwords: quitar las *stopwords* en inglés de NLTK.
        longitud_minima_token: descarta tokens más cortos (p. ej. letras sueltas).
        procesos: procesos de spaCy al transformar lotes grandes.
        tamano_lote: textos por lote de spaCy.
    """

    def __init__(
        self,
        lematizar: bool = True,
        quitar_stopwords: bool = True,
        longitud_minima_token: int = 2,
        procesos: int = 1,
        tamano_lote: int = 256,
    ) -> None:
        self.lematizar = lematizar
        self.quitar_stopwords = quitar_stopwords
        self.longitud_minima_token = longitud_minima_token
        self.procesos = procesos
        self.tamano_lote = tamano_lote

    @classmethod
    def desde_configuracion(cls, config: dict[str, Any] | None = None, **extra) -> Preprocesador:
        """Crea el preprocesador con la sección `preprocesamiento` de `base.yaml`."""
        config = config or cargar_configuracion()
        return cls(**{**config.get("preprocesamiento", {}), **extra})

    def fit(self, textos=None, y=None) -> Preprocesador:  # noqa: ARG002 - interfaz sklearn
        return self

    def transform(self, textos: Iterable[str]) -> list[str]:
        normalizados = [normalizar(t) if isinstance(t, str) else "" for t in textos]
        if self.lematizar:
            documentos = _spacy().pipe(
                normalizados, n_process=self.procesos, batch_size=self.tamano_lote
            )
            tokens = ([(t.text, t.lemma_.lower()) for t in doc] for doc in documentos)
        else:
            tokens = ([(p, p) for p in texto.split()] for texto in normalizados)
        return [self._filtrar(pares) for pares in tokens]

    def __call__(self, texto: str) -> str:
        """Procesa un solo texto (atajo para la API)."""
        return self.transform([texto])[0]

    def _filtrar(self, pares: list[tuple[str, str]]) -> str:
        vacias = _stopwords() if self.quitar_stopwords else frozenset()
        conservados = [
            lema
            for palabra, lema in pares
            if len(lema) >= self.longitud_minima_token
            and lema.isalpha()
            and palabra not in vacias
            and lema not in vacias
        ]
        return " ".join(conservados)


def preprocesar(texto: str) -> str:
    """Procesa un texto con la configuración de `base.yaml`."""
    return _preprocesador_por_defecto()(texto)


@lru_cache(maxsize=1)
def _preprocesador_por_defecto() -> Preprocesador:
    return Preprocesador.desde_configuracion()


def preprocesar_particiones(
    origen: Path | str = DATOS_PROCESADOS,
    destino: Path | str = DATOS_PROCESADOS / "preprocesado",
    procesos: int = 1,
) -> dict[str, pd.DataFrame]:
    """Agrega la columna `texto_procesado` a cada partición y la guarda en `destino`."""
    origen, destino = Path(origen), Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    preprocesador = Preprocesador.desde_configuracion(procesos=procesos)
    resultado = {}
    for nombre in ("train", "val", "test"):
        ruta = origen / f"{nombre}.parquet"
        if not ruta.is_file():
            raise FileNotFoundError(
                f"No existe {ruta}. Ejecuta antes: python -m clasificador_ml.datos"
            )
        df = pd.read_parquet(ruta)
        inicio = time.perf_counter()
        df["texto_procesado"] = preprocesador.transform(df["texto"].tolist())
        print(f"{nombre}: {len(df)} documentos en {time.perf_counter() - inicio:.0f} s")
        df.to_parquet(destino / f"{nombre}.parquet", index=False)
        resultado[nombre] = df
    return resultado


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Preprocesa las particiones (Fase II).")
    parser.add_argument("--origen", type=Path, default=DATOS_PROCESADOS)
    parser.add_argument("--destino", type=Path, default=DATOS_PROCESADOS / "preprocesado")
    parser.add_argument("--procesos", type=int, default=1, help="Procesos de spaCy")
    args = parser.parse_args(argv)
    preprocesar_particiones(args.origen, args.destino, args.procesos)


if __name__ == "__main__":
    main()
