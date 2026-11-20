"""GET /categorias, GET /modelos y GET /modelos/{id}/metricas, y el registro de modelos."""

import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.clasificacion import Catalogo
from app.clasificacion.registro import CalculadoraMetricas, descubrir_modelos, sincronizar_modelos
from app.core.config import settings
from app.db.modelos import Modelo
from tests.api.conftest import CATEGORIAS


def metricas(f1_dominio, f1_area):
    nivel = {
        "accuracy": f1_area,
        "precision_macro": f1_area,
        "recall_macro": f1_area,
        "f1_macro": f1_area,
        "precision_ponderado": f1_area,
        "recall_ponderado": f1_area,
        "f1_ponderado": f1_area,
    }
    return {"dominio": nivel | {"f1_macro": f1_dominio}, "area": nivel, "jerarquico": nivel}


def variante(f1_dominio, f1_area, tiempo=100.0):
    return {
        "metricas_validacion": metricas(f1_dominio, f1_area),
        "porcentaje_revision_validacion": 0.2,
        "tiempo_prediccion": {"media_ms": tiempo},
        "submodelos": {"plano": {"mejores_parametros": {"clf__C": 1.0}}},
    }


# 6 documentos: 4 de CS (áreas 0 y 1) y 2 de Medical (área 2).
REALES = pd.DataFrame(
    {
        "id_documento": [10, 11, 12, 13, 14, 15],
        "id_dominio": [0, 0, 0, 0, 1, 1],
        "id_area": [0, 0, 1, 1, 2, 2],
    }
)


def predicciones(dominio_pred, area_pred, confianza=0.9):
    return pd.DataFrame(
        {
            "id_documento": REALES["id_documento"],
            "dominio_real": REALES["id_dominio"],
            "area_real": REALES["id_area"],
            "dominio_pred": dominio_pred,
            "area_pred": area_pred,
            "confianza_dominio": confianza,
            "confianza_area": 0.8,
            "confianza_conjunta": confianza * 0.8,
            "requiere_revision": False,
        }
    )


@pytest.fixture
def directorio(tmp_path):
    """`models/` con NB, SVM (activo, con una versión vieja) y DistilBERT, más `data/`."""
    modelos, datos = tmp_path / "models", tmp_path / "data"
    datos.mkdir()

    def version(algoritmo, nombre, metadatos):
        carpeta = modelos / algoritmo / nombre
        carpeta.mkdir(parents=True)
        (carpeta / "metadatos.json").write_text(json.dumps(metadatos), encoding="utf-8")
        return carpeta

    nb = version(
        "complement_nb",
        "nb1",
        {
            "fecha": "2026-11-19T15:50:00",
            "tipos": {"jerarquico": variante(0.80, 0.64), "plano": variante(0.85, 0.72)},
        },
    )
    predicciones([0, 0, 0, 1, 1, 1], [0, 0, 1, 2, 2, 2]).to_parquet(
        nb / "predicciones_val_plano.parquet"
    )

    version("linear_svc", "viejo", {"fecha": "2026-11-01T00:00:00", "tipos": {}})
    svm = version(
        "linear_svc",
        "svm1",
        {
            "fecha": "2026-11-19T15:55:00",
            "tipos": {"jerarquico": variante(0.88, 0.75), "plano": variante(0.90, 0.78, 215.0)},
        },
    )
    predicciones([0, 0, 0, 0, 1, 1], [0, 0, 1, 1, 2, 2]).to_parquet(
        svm / "predicciones_val_plano.parquet"
    )
    # En prueba: un documento de CS va a Medical y otro se confunde de área.
    predicciones([0, 0, 0, 1, 1, 1], [0, 1, 1, 2, 2, 2], confianza=0.5).to_parquet(
        svm / "predicciones_test_plano.parquet"
    )

    bert = version(
        "distilbert",
        "bert1",
        {"fecha": "2026-11-20T02:10:00", "tipo": "plano", **variante(0.91, 0.77, 233.0)},
    )
    # Probabilidades por área: acierta todo menos el documento 13 (área 1 -> área 0).
    filas = {0: [1, 0, 0], 1: [0, 1, 0], 2: [0, 0, 1]}
    elegidas = [0, 0, 1, 0, 2, 2]
    probabilidades = pd.DataFrame(
        [[0.8 * f + 0.1 for f in filas[a]] for a in elegidas], columns=["p_0", "p_1", "p_2"]
    )
    probabilidades.insert(0, "id_documento", REALES["id_documento"])
    probabilidades.to_parquet(bert / "probabilidades_val.parquet")
    REALES.to_parquet(datos / "val.parquet")

    activo = {
        "algoritmo": "linear_svc",
        "version": "svm1",
        "tipo": "plano",
        "archivo": "linear_svc/svm1/plano.joblib",
        "umbrales": {"umbral_dominio": 0.65, "umbral_conjunta": 0.5},
        "metricas_prueba": metricas(0.91, 0.79),
    }
    return modelos, datos, activo


@pytest.fixture
def registrados(directorio, fabrica_sesiones):
    modelos, _datos, activo = directorio
    with fabrica_sesiones() as sesion:
        sincronizar_modelos(sesion, modelos, activo)
        sesion.commit()
        return {m.algoritmo: m.id for m in sesion.scalars(select(Modelo))}


@pytest.fixture
def cliente_modelos(aplicacion, directorio, registrados):
    modelos, datos, _activo = directorio
    aplicacion.state.calculadora = CalculadoraMetricas(modelos, datos, Catalogo(CATEGORIAS))
    return TestClient(aplicacion)


# --- Descubrimiento y registro ------------------------------------------------------------


def test_descubre_la_ultima_version_de_cada_algoritmo(directorio):
    modelos, _datos, activo = directorio
    encontrados = {m.algoritmo: m for m in descubrir_modelos(modelos, activo)}

    assert {a: m.version for a, m in encontrados.items()} == {
        "complement_nb": "nb1",
        "distilbert": "bert1",
        "linear_svc": "svm1",
    }
    assert encontrados["complement_nb"].tipo == "plano"  # mejor F1 jerárquico
    assert encontrados["linear_svc"].activo
    assert not encontrados["distilbert"].activo


def test_sin_carpeta_de_modelos_no_hay_nada(tmp_path):
    assert descubrir_modelos(tmp_path / "no-existe") == []


def test_sincronizar_registra_y_no_duplica(directorio, fabrica_sesiones):
    modelos, _datos, activo = directorio
    with fabrica_sesiones() as sesion:
        sincronizar_modelos(sesion, modelos, activo)
        sincronizar_modelos(sesion, modelos, activo)
        sesion.commit()
        registrados = sesion.scalars(select(Modelo)).all()

    assert len(registrados) == 3
    assert [m.algoritmo for m in registrados if m.activo] == ["linear_svc"]
    svm = next(m for m in registrados if m.algoritmo == "linear_svc")
    assert svm.nombre == "TF-IDF + SVM lineal (plano)"
    assert svm.ruta_artefacto == "linear_svc/svm1/plano.joblib"
    assert svm.metricas["umbrales"] == {"umbral_dominio": 0.65, "umbral_conjunta": 0.5}
    bert = next(m for m in registrados if m.algoritmo == "distilbert")
    assert bert.ruta_artefacto == "distilbert/bert1/modelo"
    assert bert.metricas["prueba"] is None


# --- Categorías ---------------------------------------------------------------------------


def test_categorias(cliente):
    datos = cliente.get("/api/v1/categorias").json()
    assert (datos["total_dominios"], datos["total_areas"]) == (2, 3)
    assert datos["dominios"][0]["codigo"] == "CS"
    assert [a["nombre"] for a in datos["dominios"][0]["areas"]] == [
        "Computer vision",
        "Machine learning",
    ]


def test_categorias_sin_catalogo_responde_503(cliente, aplicacion):
    aplicacion.state.catalogo = None
    respuesta = cliente.get("/api/v1/categorias")
    assert respuesta.status_code == 503
    assert respuesta.json()["error"]["codigo"] == "CATEGORIAS_NO_DISPONIBLES"


# --- Modelos ------------------------------------------------------------------------------


def test_listar_modelos_primero_el_activo(cliente_modelos):
    datos = cliente_modelos.get("/api/v1/modelos").json()

    assert [m["algoritmo"] for m in datos][0] == "linear_svc"
    activo = datos[0]
    assert activo["activo"] is True
    assert activo["tipo"] == "plano"
    assert activo["validacion"]["f1_area"] == pytest.approx(0.78)
    assert activo["prueba"]["f1_dominio"] == pytest.approx(0.91)
    assert activo["umbrales"] == {"umbral_dominio": 0.65, "umbral_conjunta": 0.5}
    assert activo["tiempo_ms"] == 215.0
    assert activo["hiperparametros"] == {"plano": {"clf__C": 1.0}}
    assert set(activo["variantes"]) == {"jerarquico", "plano"}
    assert all(m["activo"] is False and m["prueba"] is None for m in datos[1:])


def test_listar_modelos_vacio(cliente):
    assert cliente.get("/api/v1/modelos").json() == []


def test_metricas_del_activo_usan_prueba(cliente_modelos, registrados):
    respuesta = cliente_modelos.get(f"/api/v1/modelos/{registrados['linear_svc']}/metricas")

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["particion"] == "prueba"
    assert datos["particiones_disponibles"] == ["validacion", "prueba"]
    assert datos["documentos"] == 6
    assert datos["modelo"]["nombre"] == "TF-IDF + SVM lineal (plano)"

    dominio = datos["confusion"]["dominio"]
    assert dominio["etiquetas"] == ["Computer Science", "Medical Sciences"]
    assert dominio["matriz"] == [[3, 1], [0, 2]]

    cs = datos["confusion"]["area_por_dominio"][0]
    assert cs["dominio"] == "Computer Science"
    assert cs["columnas"] == ["Computer vision", "Machine learning", "otro dominio"]
    assert cs["matriz"] == [[1, 1, 0], [0, 1, 1]]

    areas = {c["nombre"]: c for c in datos["por_clase"]["area"]}
    assert areas["Cancer"]["dominio"] == "Medical Sciences"
    assert areas["Cancer"]["soporte"] == 2
    assert areas["Machine learning"]["recall"] == pytest.approx(0.5)

    # Con confianza 0,5 y los umbrales calibrados (0,65) todo va a revisión.
    assert datos["revision"]["porcentaje"] == 1.0
    assert datos["revision"]["accuracy_aceptados"] is None


def test_metricas_de_validacion_bajo_pedido(cliente_modelos, registrados):
    url = f"/api/v1/modelos/{registrados['linear_svc']}/metricas"
    datos = cliente_modelos.get(url, params={"particion": "validacion"}).json()
    assert datos["particion"] == "validacion"
    assert datos["metricas"]["jerarquico"]["accuracy"] == 1.0
    assert datos["revision"] == {
        "umbrales": {"umbral_dominio": 0.65, "umbral_conjunta": 0.5},
        "porcentaje": 0.0,
        "accuracy_aceptados": 1.0,
    }


def test_metricas_de_un_modelo_no_elegido_usan_validacion(cliente_modelos, registrados):
    datos = cliente_modelos.get(f"/api/v1/modelos/{registrados['complement_nb']}/metricas").json()
    assert datos["particion"] == "validacion"
    assert datos["particiones_disponibles"] == ["validacion"]
    assert datos["revision"]["umbrales"] == {"umbral_dominio": 0.60, "umbral_conjunta": 0.40}
    assert datos["confusion"]["dominio"]["matriz"] == [[3, 1], [0, 2]]


def test_metricas_de_distilbert_decodifican_sus_probabilidades(cliente_modelos, registrados):
    datos = cliente_modelos.get(f"/api/v1/modelos/{registrados['distilbert']}/metricas").json()
    assert datos["particion"] == "validacion"
    assert datos["confusion"]["dominio"]["matriz"] == [[4, 0], [0, 2]]
    assert datos["confusion"]["area_por_dominio"][0]["matriz"] == [[2, 0, 0], [1, 1, 0]]


def test_metricas_se_calculan_una_sola_vez(cliente_modelos, registrados, monkeypatch):
    url = f"/api/v1/modelos/{registrados['linear_svc']}/metricas"
    cliente_modelos.get(url)

    def no_leer(*_args, **_kwargs):
        raise AssertionError("debería usar la caché")

    monkeypatch.setattr(pd, "read_parquet", no_leer)
    assert cliente_modelos.get(url).status_code == 200


@pytest.mark.parametrize(
    ("ruta", "params", "esperado"),
    [
        ("/api/v1/modelos/999/metricas", {}, (404, "NO_ENCONTRADO")),
        ("complement_nb", {"particion": "prueba"}, (404, "NO_ENCONTRADO")),
        ("linear_svc", {"particion": "entrenamiento"}, (400, "ENTRADA_INVALIDA")),
    ],
)
def test_metricas_errores(cliente_modelos, registrados, ruta, params, esperado):
    if not ruta.startswith("/"):
        ruta = f"/api/v1/modelos/{registrados[ruta]}/metricas"
    respuesta = cliente_modelos.get(ruta, params=params)
    assert (respuesta.status_code, respuesta.json()["error"]["codigo"]) == esperado


def test_particion_invalida_explica_las_opciones(cliente_modelos, registrados):
    url = f"/api/v1/modelos/{registrados['linear_svc']}/metricas"
    mensaje = cliente_modelos.get(url, params={"particion": "x"}).json()["error"]["mensaje"]
    assert mensaje == "Entrada inválida. particion: debe ser 'validacion' o 'prueba'"


def test_modelo_sin_predicciones_responde_404(cliente_modelos, registrados, directorio):
    modelos, _datos, _activo = directorio
    (modelos / "complement_nb" / "nb1" / "predicciones_val_plano.parquet").unlink()
    respuesta = cliente_modelos.get(f"/api/v1/modelos/{registrados['complement_nb']}/metricas")
    assert respuesta.status_code == 404
    assert "No hay predicciones" in respuesta.json()["error"]["mensaje"]


def test_metricas_sin_catalogo_responden_503(cliente_modelos, aplicacion, registrados):
    aplicacion.state.calculadora = None
    aplicacion.state.catalogo = None
    respuesta = cliente_modelos.get(f"/api/v1/modelos/{registrados['linear_svc']}/metricas")
    assert respuesta.json()["error"]["codigo"] == "CATEGORIAS_NO_DISPONIBLES"


# --- Arranque -----------------------------------------------------------------------------


def test_al_iniciar_registra_todos_los_modelos(monkeypatch, fabrica_sesiones, directorio):
    import app.main as principal

    modelos, datos, _activo = directorio
    monkeypatch.setattr(settings, "ruta_modelos", modelos)
    monkeypatch.setattr(settings, "ruta_datos", datos)
    monkeypatch.setattr(principal, "crear_tablas", lambda: None)
    monkeypatch.setattr(principal, "SesionLocal", fabrica_sesiones)
    monkeypatch.setattr("app.db.sesion.SesionLocal", fabrica_sesiones)
    monkeypatch.setattr(principal, "cargar_servicio", lambda *_: None)
    monkeypatch.setattr(principal, "cargar_catalogo", lambda _ruta: Catalogo(CATEGORIAS))

    aplicacion = principal.create_app()
    with TestClient(aplicacion) as cliente:
        nombres = [m["nombre"] for m in cliente.get("/api/v1/modelos").json()]
        assert aplicacion.state.calculadora.ruta_datos == datos

    assert len(nombres) == 3


def test_metadatos_roto_no_impide_arrancar(monkeypatch, fabrica_sesiones, directorio):
    import app.main as principal

    modelos, _datos, _activo = directorio
    roto = {"fecha": "no es fecha", "tipo": "plano"}
    (modelos / "distilbert" / "bert1" / "metadatos.json").write_text(json.dumps(roto))
    monkeypatch.setattr(settings, "ruta_modelos", modelos)
    monkeypatch.setattr(principal, "crear_tablas", lambda: None)
    monkeypatch.setattr(principal, "SesionLocal", fabrica_sesiones)
    monkeypatch.setattr(principal, "cargar_servicio", lambda *_: None)
    monkeypatch.setattr(principal, "cargar_catalogo", lambda _ruta: None)

    aplicacion = principal.create_app()
    with TestClient(aplicacion) as cliente:
        assert cliente.get("/api/v1/salud").status_code == 200
    assert aplicacion.state.calculadora is None
