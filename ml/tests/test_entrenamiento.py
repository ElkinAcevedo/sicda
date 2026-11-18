import json
import subprocess
import sys

import joblib
import numpy as np
import pandas as pd
import pytest

from clasificador_ml.busqueda import BusquedaYCalibracion
from clasificador_ml.configuracion import cargar_configuracion
from clasificador_ml.entrenamiento import (
    construir_estimador,
    entrenar,
    main,
    mapa_area_dominio,
    muestrear,
)
from clasificador_ml.jerarquico import ClasificadorJerarquico
from clasificador_ml.rutas import CONFIGURACIONES

VOCABULARIO = {
    (0, 10): ["neural", "network", "deep", "layer", "train"],
    (0, 11): ["database", "query", "index", "sql", "table"],
    (1, 20): ["patient", "tumor", "cancer", "therapy", "dose"],
    (1, 21): ["heart", "cardiac", "artery", "blood", "pressure"],
}


def _particion(por_area, semilla):
    generador = np.random.default_rng(semilla)
    filas = []
    for (dominio, area), palabras in VOCABULARIO.items():
        for _ in range(por_area):
            texto = " ".join(generador.choice(palabras, 8))
            filas.append(
                {
                    "id_documento": len(filas),
                    "texto": texto.capitalize() + ".",
                    "texto_procesado": texto,
                    "id_dominio": dominio,
                    "id_area": area,
                }
            )
    return pd.DataFrame(filas)


@pytest.fixture
def datos(tmp_path):
    origen = tmp_path / "preprocesado"
    origen.mkdir()
    _particion(15, 0).to_parquet(origen / "train.parquet")
    _particion(5, 1).to_parquet(origen / "val.parquet")
    return origen


def _config(nombre):
    config = cargar_configuracion(CONFIGURACIONES / nombre)
    config["tfidf"] = {**config["tfidf"], "min_df": 1, "max_df": 1.0}
    return config


def test_construir_estimador_svm_separa_rejilla_y_fijos():
    estimador = construir_estimador(_config("svm.yaml"))

    assert estimador.parametros == {"clf__C": [0.1, 0.5, 1.0, 2.0]}
    assert estimador.calibrar is True
    assert estimador.estimador.named_steps["clf"].class_weight == "balanced"
    assert estimador.estimador.named_steps["tfidf"].ngram_range == (1, 2)


def test_construir_estimador_nb():
    estimador = construir_estimador(_config("naive_bayes.yaml"))

    assert estimador.parametros == {"clf__alpha": [0.1, 0.3, 1.0]}
    # Se calibra porque las probabilidades de ComplementNB son casi uniformes.
    assert estimador.calibrar is True


def test_construir_estimador_rechaza_algoritmo_desconocido():
    with pytest.raises(ValueError, match="no soportado"):
        construir_estimador({"modelo": "random_forest"})


def test_busqueda_elige_parametros_y_calibra(datos):
    train = pd.read_parquet(datos / "train.parquet")
    estimador = construir_estimador(_config("svm.yaml"), n_jobs=1)

    estimador.fit(train["texto_procesado"], train["id_area"])

    resumen = estimador.resumen()
    assert resumen["mejores_parametros"]["clf__C"] in [0.1, 0.5, 1.0, 2.0]
    assert len(resumen["resultados_cv"]) == 4
    assert resumen["clases"] == 4
    probabilidades = estimador.predict_proba(train["texto_procesado"].head(3))
    assert probabilidades.sum(axis=1) == pytest.approx(np.ones(3))
    assert estimador.estimador_.memory is None


def test_busqueda_con_un_solo_valor_no_hace_cv(datos):
    train = pd.read_parquet(datos / "train.parquet")
    estimador = construir_estimador(_config("naive_bayes.yaml"))
    estimador.set_params(parametros={"clf__alpha": [0.5]})

    estimador.fit(train["texto_procesado"], train["id_area"])

    assert estimador.mejores_parametros_ == {"clf__alpha": 0.5}
    assert estimador.resultados_cv_ == []


def test_busqueda_exige_dos_documentos_por_clase():
    estimador = BusquedaYCalibracion(construir_estimador(_config("naive_bayes.yaml")).estimador)

    with pytest.raises(ValueError, match="al menos 2"):
        estimador.fit(["a b", "c d"], [0, 1])


def test_mapa_area_dominio_y_error_si_un_area_tiene_dos_dominios():
    df = pd.DataFrame({"id_area": [1, 1, 2], "id_dominio": [0, 0, 1]})

    assert mapa_area_dominio(df) == {1: 0, 2: 1}
    with pytest.raises(ValueError, match="más de un dominio"):
        mapa_area_dominio(pd.DataFrame({"id_area": [1, 1], "id_dominio": [0, 1]}))


def test_muestrear_conserva_todas_las_areas():
    df = _particion(40, 0)

    muestra = muestrear(df, 0.1, semilla=42, minimo=10)

    assert muestra.groupby("id_area").size().tolist() == [10, 10, 10, 10]
    assert muestrear(df, 1.0, 42) is df
    with pytest.raises(ValueError):
        muestrear(df, 0, 42)


@pytest.mark.parametrize("nombre", ["naive_bayes.yaml", "svm.yaml"])
def test_entrenar_guarda_modelos_predicciones_y_metadatos(datos, tmp_path, nombre):
    config = _config(nombre)

    carpeta = entrenar(
        config, version="prueba", origen=datos, destino=tmp_path / "models", n_jobs=1, docs_tiempo=3
    )

    assert carpeta == tmp_path / "models" / config["modelo"] / "prueba"
    metadatos = json.loads((carpeta / "metadatos.json").read_text(encoding="utf-8"))
    assert set(metadatos["tipos"]) == {"jerarquico", "plano"}
    jerarquico = metadatos["tipos"]["jerarquico"]
    assert set(jerarquico["submodelos"]) == {"dominio", "area_0", "area_1"}
    assert jerarquico["metricas_validacion"]["jerarquico"]["f1_macro"] > 0.9
    assert jerarquico["tiempo_prediccion"]["documentos"] == 3

    predicciones = pd.read_parquet(carpeta / "predicciones_val_jerarquico.parquet")
    assert len(predicciones) == 20
    assert {"dominio_real", "area_real", "dominio_pred", "area_pred", "requiere_revision"} <= set(
        predicciones.columns
    )

    # El modelo publicado incluye el preprocesador: recibe texto crudo.
    modelo = joblib.load(carpeta / "jerarquico.joblib")
    assert isinstance(modelo, ClasificadorJerarquico)
    assert modelo.predict(["The patients received a tumor therapy dose."]).tolist() == [20]


def test_main_entrena_solo_el_tipo_pedido(datos, tmp_path):
    main(
        [
            "--config",
            str(CONFIGURACIONES / "naive_bayes.yaml"),
            "--tipo",
            "plano",
            "--version",
            "cli",
            "--origen",
            str(datos),
            "--destino",
            str(tmp_path),
            "--procesos",
            "1",
            "--docs-tiempo",
            "1",
        ]
    )

    carpeta = tmp_path / "complement_nb" / "cli"
    assert (carpeta / "plano.joblib").is_file()
    assert not (carpeta / "jerarquico.joblib").exists()


def test_entrenar_sin_datos_da_error_claro(tmp_path):
    with pytest.raises(FileNotFoundError, match="preprocesamiento"):
        entrenar(_config("naive_bayes.yaml"), origen=tmp_path, destino=tmp_path)


def test_modelo_entrenado_con_python_m_se_carga_desde_otro_proceso(datos, tmp_path):
    # Si alguna clase quedara registrada como `__main__`, la API no podría cargar el modelo.
    comando = [
        sys.executable,
        "-m",
        "clasificador_ml.entrenamiento",
        "--config",
        str(CONFIGURACIONES / "naive_bayes.yaml"),
        "--tipo",
        "jerarquico",
        "--version",
        "proceso",
        "--origen",
        str(datos),
        "--destino",
        str(tmp_path),
        "--procesos",
        "1",
        "--docs-tiempo",
        "1",
    ]
    subprocess.run(comando, check=True, capture_output=True)

    modelo = joblib.load(tmp_path / "complement_nb" / "proceso" / "jerarquico.joblib")

    assert modelo.predict(["The heart artery blood pressure."]).tolist() == [21]
