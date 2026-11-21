"""Prepara los recursos de las pruebas de extremo a extremo en `tests/e2e/.recursos/`.

En el CI no existen `models/` ni `data/`, así que se entrena un modelo **real pero diminuto**
con el mismo código del proyecto (`clasificador_ml.entrenamiento`): un SVM plano sobre un
dataset sintético de 2 dominios y 4 áreas. La API lo carga igual que al modelo activo de verdad.

Genera:
    modelos/          artefactos del SVM y `activo.json`
    datos/            `categorias.json` y las particiones preprocesadas
    articulo-<navegador>.pdf  un artículo de visión por computador con su «Abstract», uno por
                              navegador: la API reutiliza los documentos con el mismo
                              contenido (hash), así que cada navegador sube uno distinto
    e2e.db            se borra para que cada ejecución empiece con el historial vacío

Uso (lo ejecuta Playwright antes de levantar la API):
    python tests/e2e/preparar.py
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pymupdf

from clasificador_ml.artefactos import publicar_activo
from clasificador_ml.configuracion import cargar_configuracion
from clasificador_ml.entrenamiento import entrenar
from clasificador_ml.preprocesamiento import Preprocesador
from clasificador_ml.rutas import CONFIGURACIONES

RECURSOS = Path(__file__).parent / ".recursos"
NAVEGADORES = ("chromium", "firefox")  # los proyectos de playwright.config.ts
VERSION = "e2e"

# (id_dominio, dominio, id_area, área) → vocabulario propio del área, separado por espacios.
AREAS = {
    (0, "Computer Science", 0, "Computer vision"): (
        "image pixel camera segmentation detection object video scene"
    ),
    (0, "Computer Science", 1, "Machine learning"): (
        "classifier regression kernel gradient ensemble feature dataset optimization"
    ),
    (1, "Medical", 2, "Cancer"): (
        "tumor cancer chemotherapy oncology metastasis biopsy carcinoma radiotherapy"
    ),
    (1, "Medical", 3, "Cardiology"): (
        "heart cardiac artery blood pressure hypertension valve coronary"
    ),
}
PLANTILLAS = [
    "This study examines {} and {} in a large cohort.",
    "We propose a method that combines {} with {}.",
    "Results show that {} improves {} significantly.",
    "The analysis of {} reveals new evidence about {}.",
]

RESUMEN_PDF = (
    "Object detection and semantic segmentation are central problems in image analysis. "
    "We present a camera based method that processes every video frame and every pixel of "
    "the scene to improve detection of each object. The segmentation network labels pixel "
    "regions in the image, and the detection stage locates every object in the scene. "
    "Experiments on video recorded with a camera show better segmentation and detection "
    "than previous image methods, with accurate pixel level results for each scene."
)


def _documentos(por_area: int, semilla: int) -> pd.DataFrame:
    generador = np.random.default_rng(semilla)
    filas = []
    for (id_dominio, dominio, id_area, area), vocabulario in AREAS.items():
        palabras = vocabulario.split()
        for _ in range(por_area):
            oraciones = [
                plantilla.format(*generador.choice(palabras, 2, replace=False))
                for plantilla in generador.choice(PLANTILLAS, 4)
            ]
            filas.append(
                {
                    "id_documento": len(filas),
                    "texto": " ".join(oraciones),
                    "palabras_clave": "",
                    "id_dominio": id_dominio,
                    "dominio": dominio,
                    "id_area": id_area,
                    "area": area,
                    "y_original": id_area,
                }
            )
    return pd.DataFrame(filas)


def _categorias() -> dict:
    dominios: dict[int, dict] = {}
    for id_dominio, dominio, id_area, area in AREAS:
        dominios.setdefault(
            id_dominio, {"id": id_dominio, "codigo": dominio, "nombre": dominio, "areas": []}
        )["areas"].append({"id": id_area, "nombre": area})
    return {"dominios": list(dominios.values())}


def titulo_pdf(navegador: str) -> str:
    return f"Camera based object detection and segmentation in video ({navegador})"


def _guardar_pdf(ruta: Path, titulo: str) -> None:
    documento = pymupdf.open()
    pagina = documento.new_page()
    texto = (
        f"{titulo}\n\n"
        f"Abstract\n{RESUMEN_PDF}\n\n"
        "Keywords: image, segmentation, detection\n\n"
        "1. Introduction\nVisual recognition has a long history in computer science."
    )
    pagina.insert_textbox(pymupdf.Rect(50, 50, 550, 800), texto, fontsize=11)
    documento.save(ruta)


def preparar(destino: Path = RECURSOS) -> None:
    shutil.rmtree(destino, ignore_errors=True)
    datos = destino / "datos"
    preprocesado = datos / "preprocesado"
    preprocesado.mkdir(parents=True)

    config = cargar_configuracion(CONFIGURACIONES / "svm.yaml")
    # Con tan pocos documentos, los filtros de frecuencia del vocabulario real lo vaciarían.
    config["tfidf"] = {**config["tfidf"], "min_df": 1, "max_df": 1.0}
    preprocesador = Preprocesador.desde_configuracion(config)

    for nombre, por_area, semilla in [("train", 30, 0), ("val", 10, 1), ("test", 10, 2)]:
        particion = _documentos(por_area, semilla)
        particion.to_parquet(datos / f"{nombre}.parquet", index=False)
        particion["texto_procesado"] = preprocesador.transform(particion["texto"].tolist())
        particion.to_parquet(preprocesado / f"{nombre}.parquet", index=False)
    (datos / "categorias.json").write_text(json.dumps(_categorias(), indent=2), encoding="utf-8")

    modelos = destino / "modelos"
    entrenar(
        config,
        tipos=("plano",),
        version=VERSION,
        origen=preprocesado,
        destino=modelos,
        n_jobs=1,
        docs_tiempo=5,
    )
    publicar_activo(
        "linear_svc",
        VERSION,
        "plano",
        umbrales={"umbral_dominio": 0.65, "umbral_conjunta": 0.5},
        directorio=modelos,
    )
    for navegador in NAVEGADORES:
        _guardar_pdf(destino / f"articulo-{navegador}.pdf", titulo_pdf(navegador))
    print(f"Recursos de e2e listos en {destino}")


if __name__ == "__main__":
    preparar()
