"""Catálogo de dominios y áreas."""

import json

from fastapi.testclient import TestClient

from app.clasificacion import Catalogo, cargar_catalogo
from tests.api.conftest import CATEGORIAS


def test_traduce_ids_y_usa_el_numero_si_no_existe():
    catalogo = Catalogo(CATEGORIAS)
    assert catalogo.nombre_dominio(1) == "Medical Sciences"
    assert catalogo.nombre_area(2) == "Cancer"
    assert catalogo.nombre_area(77) == "77"


def test_valida_dominio_y_area():
    catalogo = Catalogo(CATEGORIAS)
    assert catalogo.validar("Computer Science") is None
    assert catalogo.validar("Computer Science", "Machine learning") is None
    assert "no existe" in catalogo.validar("Física")
    assert "no pertenece" in catalogo.validar("Computer Science", "Cancer")


def test_cargar_catalogo(tmp_path):
    ruta = tmp_path / "categorias.json"
    ruta.write_text(json.dumps(CATEGORIAS), encoding="utf-8")
    assert cargar_catalogo(ruta).validar("Medical Sciences", "Cancer") is None
    assert cargar_catalogo(tmp_path / "no-existe.json") is None


def test_sin_modelo_el_catalogo_se_carga_igual(monkeypatch):
    import app.main as principal

    catalogo = Catalogo(CATEGORIAS)
    monkeypatch.setattr(principal, "crear_tablas", lambda: None)
    monkeypatch.setattr(principal, "cargar_servicio", lambda *_: None)
    monkeypatch.setattr(principal, "cargar_catalogo", lambda _ruta: catalogo)

    aplicacion = principal.create_app()
    with TestClient(aplicacion):
        assert aplicacion.state.catalogo is catalogo
