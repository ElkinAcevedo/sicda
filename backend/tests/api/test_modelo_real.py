"""Prueba de integración con el modelo publicado en `models/activo.json`.

Se omite si no hay modelo entrenado (por ejemplo, en un clon recién descargado).
"""

import pytest

from app.clasificacion import ServicioClasificacion
from clasificador_ml.rutas import DATOS_PROCESADOS, MODELOS

CATEGORIAS = DATOS_PROCESADOS / "categorias.json"

pytestmark = pytest.mark.skipif(
    not (MODELOS / "activo.json").is_file() or not CATEGORIAS.is_file(),
    reason="No hay modelo activo entrenado en models/",
)

CASOS = [
    (
        "Patients with major depressive disorder were randomized to receive cognitive "
        "behavioral therapy or medication. Symptoms of anxiety and depression were measured at "
        "baseline and after twelve weeks of treatment.",
        "Psychology",
    ),
    (
        "We propose a convolutional neural network for image segmentation. The network is "
        "trained end to end on a large dataset of annotated images and outperforms previous "
        "computer vision methods on standard benchmarks.",
        "Computer Science",
    ),
]


@pytest.fixture(scope="module")
def servicio():
    return ServicioClasificacion.desde_directorio(MODELOS, CATEGORIAS)


@pytest.mark.parametrize(("texto", "dominio"), CASOS)
def test_el_modelo_activo_clasifica_ejemplos_evidentes(servicio, texto, dominio):
    prediccion = servicio.clasificar(texto)
    assert prediccion.dominio.nombre == dominio
    assert len(prediccion.dominio.alternativas) == 3
    assert prediccion.area.alternativas[0].nombre == prediccion.area.nombre
    assert 0 <= prediccion.confianza_conjunta <= prediccion.dominio.confianza <= 1
    assert prediccion.terminos_clave
