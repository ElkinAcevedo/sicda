import numpy as np
import pandas as pd
import pytest

from clasificador_ml.seleccion import (
    curva_revision,
    elegir_umbrales,
    predicciones_desde_probabilidades,
    seleccionar_modelo,
)


def test_seleccionar_modelo_gana_el_mejor_si_supera_el_margen():
    tabla = pd.DataFrame(
        {"f1_jerarquico": [0.70, 0.75], "tiempo_ms": [5, 500]}, index=["nb", "bert"]
    )

    assert seleccionar_modelo(tabla) == "bert"


def test_seleccionar_modelo_en_empate_gana_el_mas_rapido():
    tabla = pd.DataFrame(
        {"f1_jerarquico": [0.70, 0.735, 0.74], "tiempo_ms": [5, 30, 500]},
        index=["nb", "svm", "bert"],
    )

    # svm queda a menos de 2 puntos de bert y es más rápido; nb no entra en el margen.
    assert seleccionar_modelo(tabla) == "svm"


def test_seleccionar_modelo_sin_modelos_da_error():
    with pytest.raises(ValueError):
        seleccionar_modelo(pd.DataFrame(columns=["f1_jerarquico", "tiempo_ms"]))


def test_predicciones_desde_probabilidades_decodifica_jerarquicamente():
    probabilidades = pd.DataFrame(
        {
            "id_documento": [7, 8],
            # Columnas desordenadas a propósito.
            "p_2": [0.45, 0.0],
            "p_0": [0.30, 0.9],
            "p_1": [0.25, 0.1],
        }
    )
    area_a_dominio = {0: 0, 1: 0, 2: 1}

    tabla = predicciones_desde_probabilidades(probabilidades, area_a_dominio, 0.6, 0.4)

    # Documento 7: el dominio 0 suma 0,55 > 0,45, así que gana aunque el área 2 sea la mayor.
    assert tabla["dominio_pred"].tolist() == [0, 0]
    assert tabla["area_pred"].tolist() == [0, 0]
    assert tabla["confianza_dominio"].to_numpy() == pytest.approx([0.55, 1.0])
    assert tabla["confianza_conjunta"].to_numpy() == pytest.approx([0.30, 0.9])
    assert tabla["requiere_revision"].tolist() == [True, False]
    assert tabla["id_documento"].tolist() == [7, 8]


@pytest.fixture
def predicciones():
    # Los aciertos tienen confianza alta y los errores, baja.
    confianza = np.array([0.95, 0.9, 0.85, 0.8, 0.3, 0.2])
    return pd.DataFrame(
        {
            "dominio_real": [0, 0, 0, 0, 0, 0],
            "area_real": [1, 1, 1, 1, 1, 1],
            "dominio_pred": [0, 0, 0, 0, 1, 0],
            "area_pred": [1, 1, 1, 1, 5, 2],
            "confianza_dominio": confianza,
            "confianza_conjunta": confianza,
        }
    )


def test_curva_revision(predicciones):
    curva = curva_revision(predicciones, [0.5], [0.1, 0.5])

    sin_filtro = curva.iloc[0]
    assert sin_filtro["porcentaje_revision"] == pytest.approx(2 / 6)
    assert sin_filtro["accuracy_aceptados"] == 1.0
    assert sin_filtro["accuracy_revisados"] == 0.0
    assert sin_filtro["errores_detectados"] == 1.0
    assert len(curva) == 2


def test_elegir_umbrales_minimiza_revision_con_accuracy_minima(predicciones):
    curva = curva_revision(predicciones, [0.1, 0.5, 0.9], [0.1])

    elegido = elegir_umbrales(curva, accuracy_minima=0.95)

    assert elegido["umbral_dominio"] == 0.5
    assert elegido["porcentaje_revision"] == pytest.approx(2 / 6)


def test_elegir_umbrales_sin_cumplir_la_meta_devuelve_la_mejor_accuracy(predicciones):
    curva = curva_revision(predicciones, [0.1, 0.5], [0.1])

    elegido = elegir_umbrales(curva, accuracy_minima=1.01)

    assert elegido["umbral_dominio"] == 0.5
