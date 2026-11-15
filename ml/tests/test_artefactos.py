import joblib
import pytest

from clasificador_ml.artefactos import (
    cargar_activo,
    cargar_metadatos,
    cargar_modelo,
    publicar_activo,
    ultima_version,
    versiones,
)
from clasificador_ml.evaluacion import guardar_json


class ModeloFalso:
    umbral_dominio = 0.6
    umbral_conjunta = 0.4


@pytest.fixture
def modelos(tmp_path):
    for version, fecha in [("b", "2026-01-02T00:00:00"), ("a", "2026-01-03T00:00:00")]:
        carpeta = tmp_path / "linear_svc" / version
        guardar_json({"version": version, "fecha": fecha}, carpeta / "metadatos.json")
        joblib.dump(ModeloFalso(), carpeta / "jerarquico.joblib")
    (tmp_path / "linear_svc" / "incompleta").mkdir()
    return tmp_path


def test_versiones_ordenadas_por_fecha_e_ignora_carpetas_sin_metadatos(modelos):
    assert versiones("linear_svc", modelos) == ["b", "a"]
    assert ultima_version("linear_svc", modelos) == "a"
    assert versiones("no_existe", modelos) == []


def test_ultima_version_sin_versiones_da_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="Entrena"):
        ultima_version("linear_svc", tmp_path)


def test_cargar_metadatos_y_modelo(modelos):
    assert cargar_metadatos("linear_svc", directorio=modelos)["version"] == "a"
    assert cargar_metadatos("linear_svc", "b", modelos)["version"] == "b"
    assert isinstance(cargar_modelo("linear_svc", "jerarquico", "b", modelos), ModeloFalso)


def test_publicar_y_cargar_activo_aplica_umbrales(modelos):
    umbrales = {"umbral_dominio": 0.5, "umbral_conjunta": 0.3}

    publicar_activo("linear_svc", "a", "jerarquico", umbrales, {"f1": 0.9}, modelos)
    modelo, info = cargar_activo(modelos)

    assert info["archivo"] == "linear_svc/a/jerarquico.joblib"
    assert info["metricas_prueba"] == {"f1": 0.9}
    assert (modelo.umbral_dominio, modelo.umbral_conjunta) == (0.5, 0.3)


def test_publicar_activo_valida_archivo_y_umbrales(modelos):
    with pytest.raises(FileNotFoundError):
        publicar_activo(
            "linear_svc",
            "a",
            "plano",
            {"umbral_dominio": 1, "umbral_conjunta": 1},
            directorio=modelos,
        )
    with pytest.raises(ValueError, match="umbral_conjunta"):
        publicar_activo("linear_svc", "a", "jerarquico", {"umbral_dominio": 1}, directorio=modelos)


def test_cargar_activo_sin_publicar_da_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="activo"):
        cargar_activo(tmp_path)
