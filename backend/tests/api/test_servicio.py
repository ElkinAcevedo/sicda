"""Carga del modelo activo, traducción de ids a nombres y registro en la base."""

import json

import joblib
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencias import registrar_modelo_activo
from app.clasificacion import ServicioClasificacion, cargar_servicio
from app.db.modelos import Modelo
from app.db.sesion import crear_motor, crear_tablas
from tests.api.conftest import CATEGORIAS, INFO_ACTIVO, METADATOS, ModeloFalso, crear_servicio
from tests.extraccion.conftest import RESUMEN_EN


@pytest.fixture
def directorio_modelos(tmp_path):
    """Una carpeta `models/` mínima con `activo.json`, el `.joblib` y sus metadatos."""
    carpeta = tmp_path / "models" / "linear_svc" / "v-prueba"
    carpeta.mkdir(parents=True)
    joblib.dump(ModeloFalso(), carpeta / "plano.joblib")
    (carpeta / "metadatos.json").write_text(json.dumps(METADATOS), encoding="utf-8")
    (tmp_path / "models" / "activo.json").write_text(json.dumps(INFO_ACTIVO), encoding="utf-8")
    categorias = tmp_path / "categorias.json"
    categorias.write_text(json.dumps(CATEGORIAS), encoding="utf-8")
    return tmp_path / "models", categorias


@pytest.fixture
def sesion():
    motor = crear_motor("sqlite://")
    crear_tablas(motor)
    with Session(motor, expire_on_commit=False) as s:
        yield s
    motor.dispose()


def test_carga_desde_directorio(directorio_modelos):
    servicio = ServicioClasificacion.desde_directorio(*directorio_modelos)

    assert (servicio.algoritmo, servicio.version, servicio.tipo) == (
        "linear_svc",
        "v-prueba",
        "plano",
    )
    assert servicio.nombre == "TF-IDF + SVM lineal (plano)"
    # `cargar_activo` copia al modelo los umbrales calibrados de activo.json.
    assert servicio.modelo.umbral_dominio == 0.65
    assert servicio.modelo.umbral_conjunta == 0.5
    assert servicio.hiperparametros == {"plano": {"clf__C": 1.0}}
    assert servicio.metricas["validacion"] == {"area": {"f1_macro": 0.78}}
    assert servicio.entrenado_en.isoformat() == "2026-11-19T15:55:00"


def test_cargar_servicio_calienta_el_modelo(directorio_modelos):
    servicio = cargar_servicio(*directorio_modelos)
    assert servicio is not None
    assert len(servicio.modelo.textos) == 1


def test_cargar_servicio_sin_modelo_devuelve_none(tmp_path):
    assert cargar_servicio(tmp_path / "no-existe", tmp_path / "categorias.json") is None


def test_cargar_servicio_con_modelo_que_falla_devuelve_none(directorio_modelos, monkeypatch):
    def fallar(_self, _textos):
        raise RuntimeError("roto")

    monkeypatch.setattr(ModeloFalso, "predecir_detallado", fallar)
    assert cargar_servicio(*directorio_modelos) is None


def test_traduce_ids_a_nombres():
    prediccion = crear_servicio().clasificar(RESUMEN_EN)
    assert prediccion.dominio.nombre == "Computer Science"
    assert prediccion.area.nombre == "Computer vision"
    assert [a.nombre for a in prediccion.area.alternativas] == [
        "Computer vision",
        "Machine learning",
    ]


def test_id_desconocido_usa_el_numero_como_nombre():
    servicio = ServicioClasificacion(ModeloFalso(), INFO_ACTIVO, {"dominios": []})
    assert servicio.clasificar(RESUMEN_EN).dominio.nombre == "0"


def test_sin_metadatos_usa_valores_por_defecto():
    servicio = ServicioClasificacion(ModeloFalso(), INFO_ACTIVO, CATEGORIAS)
    assert servicio.hiperparametros == {}
    assert servicio.entrenado_en is None
    assert servicio.metricas["prueba"] == INFO_ACTIVO["metricas_prueba"]


def test_registrar_modelo_activo_no_duplica(sesion):
    servicio = crear_servicio()
    primero = registrar_modelo_activo(sesion, servicio)
    segundo = registrar_modelo_activo(sesion, servicio)
    assert primero.id == segundo.id
    assert len(sesion.scalars(select(Modelo)).all()) == 1


def test_registrar_otra_version_la_deja_activa(sesion):
    registrar_modelo_activo(sesion, crear_servicio())
    nuevo = registrar_modelo_activo(sesion, crear_servicio(info=INFO_ACTIVO | {"version": "v2"}))
    activos = sesion.scalars(select(Modelo).where(Modelo.activo.is_(True))).all()
    assert [m.id for m in activos] == [nuevo.id]
    assert len(sesion.scalars(select(Modelo)).all()) == 2


def test_al_iniciar_carga_y_registra_el_modelo(monkeypatch, fabrica_sesiones):
    import app.main as principal

    monkeypatch.setattr(principal, "crear_tablas", lambda: None)
    monkeypatch.setattr(principal, "SesionLocal", fabrica_sesiones)
    monkeypatch.setattr(principal, "cargar_servicio", lambda *_: crear_servicio())

    with TestClient(principal.create_app()) as cliente:
        salud = cliente.get("/api/v1/salud").json()

    assert salud["modelo_activo"] == "TF-IDF + SVM lineal (plano) v-prueba"
    with fabrica_sesiones() as s:
        assert s.scalars(select(Modelo)).one().activo


def test_al_iniciar_sin_modelo_la_api_arranca(monkeypatch):
    import app.main as principal

    monkeypatch.setattr(principal, "crear_tablas", lambda: None)
    monkeypatch.setattr(principal, "cargar_servicio", lambda *_: None)

    with TestClient(principal.create_app()) as cliente:
        assert cliente.get("/api/v1/salud").json()["modelo_activo"] is None
