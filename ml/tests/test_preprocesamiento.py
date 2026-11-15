import pickle

import pandas as pd
import pytest

from clasificador_ml.preprocesamiento import (
    Preprocesador,
    normalizar,
    preprocesar,
    preprocesar_particiones,
)


def test_normalizar_quita_urls_correos_numeros_y_puntuacion():
    texto = "See https://x.org/a?b=1 or mail me@uni.edu: 42 Naïve, (2+1)-dimensional!"

    assert normalizar(texto) == "see or mail naive dimensional"


def test_preprocesar_lematiza_y_quita_stopwords():
    resultado = preprocesar("The studies were analyzing the running networks in 2017.").split()

    assert "the" not in resultado and "were" not in resultado and "in" not in resultado
    assert "study" in resultado
    assert "analyze" in resultado
    assert "network" in resultado
    assert "run" in resultado


def test_texto_vacio_o_no_texto_devuelve_cadena_vacia():
    assert Preprocesador().transform(["", "   ", None, "123 !!"]) == ["", "", "", ""]


def test_lote_igual_a_textos_individuales():
    textos = ["Deep neural networks classify images.", "Patients with chronic pain."]
    preprocesador = Preprocesador()

    assert preprocesador.transform(textos) == [preprocesador(t) for t in textos]


def test_sin_lematizar_conserva_las_palabras():
    resultado = Preprocesador(lematizar=False)("The studies of mice")

    assert resultado == "studies mice"


def test_opciones_desactivables():
    resultado = Preprocesador(lematizar=False, quitar_stopwords=False, longitud_minima_token=1)(
        "a study of x"
    )

    assert resultado == "a study of x"


def test_se_puede_serializar_con_el_modelo():
    preprocesador = Preprocesador()
    copia = pickle.loads(pickle.dumps(preprocesador))

    assert copia("Running studies") == preprocesador("Running studies")


def test_desde_configuracion_lee_base_yaml():
    preprocesador = Preprocesador.desde_configuracion(procesos=2)

    assert preprocesador.lematizar is True
    assert preprocesador.procesos == 2


def test_preprocesar_particiones(tmp_path):
    for nombre in ("train", "val", "test"):
        pd.DataFrame({"id_documento": [1], "texto": ["Studies of networks."]}).to_parquet(
            tmp_path / f"{nombre}.parquet"
        )

    resultado = preprocesar_particiones(tmp_path, tmp_path / "salida")

    guardado = pd.read_parquet(tmp_path / "salida" / "train.parquet")
    assert guardado["texto_procesado"].iloc[0] == "study network"
    assert set(resultado) == {"train", "val", "test"}


def test_preprocesar_particiones_sin_datos(tmp_path):
    with pytest.raises(FileNotFoundError, match="clasificador_ml.datos"):
        preprocesar_particiones(tmp_path, tmp_path / "salida")
