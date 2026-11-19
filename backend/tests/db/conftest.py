"""Base de datos SQLite en memoria, nueva para cada prueba."""

import pytest
from sqlalchemy.orm import Session

from app.db import repositorios as repo
from app.db.sesion import crear_motor, crear_tablas


@pytest.fixture
def sesion():
    motor = crear_motor("sqlite://")
    crear_tablas(motor)
    with Session(motor, expire_on_commit=False) as s:
        yield s
    motor.dispose()


@pytest.fixture
def modelo(sesion):
    return repo.registrar_modelo(
        sesion,
        nombre="TF-IDF + SVM",
        algoritmo="svm",
        version="v1",
        ruta_artefacto="svm/v1/plano.joblib",
        hiperparametros={"C": 1.0},
        metricas={"f1_macro_area": 0.7},
        activar=True,
    )


def crear_documento(sesion, texto="Deep learning for images.", **campos):
    valores = {
        "nombre_archivo": "articulo.pdf",
        "tipo": "pdf",
        "titulo": "Un artículo",
        "texto_extraido": texto,
        "fuente_texto": "abstract",
        "idioma": "en",
        "num_terminos": 40,
    } | campos
    return repo.obtener_o_crear_documento(sesion, repo.calcular_hash(texto), **valores)


def crear_clasificacion(sesion, documento, modelo, **campos):
    valores = {
        "dominio": "CS",
        "conf_dominio": 0.9,
        "area": "Machine learning",
        "conf_area": 0.8,
        "conf_conjunta": 0.72,
        "alternativas": {"dominio": [{"nombre": "CS", "confianza": 0.9}], "area": []},
        "terminos_clave": [{"termino": "network", "peso": 0.3}],
        "advertencias": [],
        "requiere_revision": False,
        "tiempo_ms": 12.5,
    } | campos
    return repo.guardar_clasificacion(sesion, documento, modelo, **valores)
