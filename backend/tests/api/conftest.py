"""Aplicación de prueba: base de datos en memoria y un modelo falso (sin cargar el SVM real)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.clasificacion import ServicioClasificacion
from app.db.sesion import crear_motor, crear_tablas, obtener_sesion
from app.main import create_app

CATEGORIAS = {
    "dominios": [
        {
            "id": 0,
            "codigo": "CS",
            "nombre": "Computer Science",
            "areas": [
                {"id": 0, "nombre": "Computer vision"},
                {"id": 1, "nombre": "Machine learning"},
            ],
        },
        {
            "id": 1,
            "codigo": "Medical",
            "nombre": "Medical Sciences",
            "areas": [{"id": 2, "nombre": "Cancer"}],
        },
    ]
}

INFO_ACTIVO = {
    "algoritmo": "linear_svc",
    "version": "v-prueba",
    "tipo": "plano",
    "archivo": "linear_svc/v-prueba/plano.joblib",
    "umbrales": {"umbral_dominio": 0.65, "umbral_conjunta": 0.5},
    "metricas_prueba": {"dominio": {"f1_macro": 0.91}, "area": {"f1_macro": 0.79}},
}

METADATOS = {
    "fecha": "2026-11-19T15:55:00",
    "tipos": {
        "plano": {
            "metricas_validacion": {"area": {"f1_macro": 0.78}},
            "submodelos": {"plano": {"mejores_parametros": {"clf__C": 1.0}}},
        }
    },
}


class ModeloFalso:
    """Imita `predecir_detallado` de `clasificador_ml`: siempre CS / Computer vision."""

    def __init__(self, confianza_dominio: float = 0.9) -> None:
        self.confianza_dominio = confianza_dominio
        self.textos: list[str] = []

    def predecir_detallado(self, textos):
        self.textos.extend(textos)
        conjunta = self.confianza_dominio * 0.8
        return [
            {
                "dominio": {
                    "id": 0,
                    "confianza": self.confianza_dominio,
                    "alternativas": [
                        {"id": 0, "confianza": self.confianza_dominio},
                        {"id": 1, "confianza": 1 - self.confianza_dominio},
                    ],
                },
                "area": {
                    "id": 0,
                    "confianza": 0.8,
                    "alternativas": [{"id": 0, "confianza": 0.8}, {"id": 1, "confianza": 0.2}],
                },
                "confianza_conjunta": conjunta,
                "requiere_revision": self.confianza_dominio < 0.65 or conjunta < 0.5,
                "terminos_clave": [{"termino": "convolutional", "peso": 0.3}],
            }
            for _ in textos
        ]


def crear_servicio(modelo=None, info=None) -> ServicioClasificacion:
    return ServicioClasificacion(
        modelo or ModeloFalso(), info or INFO_ACTIVO, CATEGORIAS, METADATOS
    )


@pytest.fixture
def fabrica_sesiones():
    motor = crear_motor("sqlite://")
    crear_tablas(motor)
    yield sessionmaker(bind=motor, autoflush=False, expire_on_commit=False)
    motor.dispose()


@pytest.fixture
def aplicacion(fabrica_sesiones):
    """App sin ciclo de vida (no carga el modelo real) con la base en memoria."""
    app = create_app()

    def _sesion():
        with fabrica_sesiones() as sesion:
            yield sesion

    app.dependency_overrides[obtener_sesion] = _sesion
    app.state.servicio = crear_servicio()
    app.state.catalogo = app.state.servicio.catalogo
    return app


@pytest.fixture
def cliente(aplicacion):
    return TestClient(aplicacion)
