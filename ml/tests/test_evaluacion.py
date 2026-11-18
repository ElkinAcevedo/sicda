import json

import numpy as np
import pytest

from clasificador_ml.evaluacion import (
    FUERA_DEL_DOMINIO,
    area_jerarquica,
    evaluar,
    guardar_json,
    matrices_area_por_dominio,
    matriz_confusion,
    metricas_nivel,
    reporte_por_clase,
    tabla_metricas,
)

# Dos dominios: el 0 con las áreas 0 y 1, el 1 con las áreas 2 y 3.
DOMINIO_REAL = [0, 0, 0, 1, 1, 1]
AREA_REAL = [0, 0, 1, 2, 3, 3]
DOMINIO_PRED = [0, 0, 1, 1, 1, 1]
AREA_PRED = [0, 1, 2, 2, 3, 2]


def test_metricas_nivel_perfectas():
    metricas = metricas_nivel([0, 1, 2], [0, 1, 2])

    assert metricas == pytest.approx(
        {
            "accuracy": 1.0,
            "precision_macro": 1.0,
            "recall_macro": 1.0,
            "f1_macro": 1.0,
            "precision_ponderado": 1.0,
            "recall_ponderado": 1.0,
            "f1_ponderado": 1.0,
        }
    )


def test_metricas_nivel_promedia_solo_las_clases_reales():
    # La predicción -1 es un error, pero no agrega una cuarta clase al promedio.
    metricas = metricas_nivel([0, 1, 2], [0, 1, -1])

    assert metricas["accuracy"] == pytest.approx(2 / 3)
    assert metricas["recall_macro"] == pytest.approx(2 / 3)
    assert metricas["precision_macro"] == pytest.approx(2 / 3)


def test_area_jerarquica_solo_anula_aciertos_con_dominio_incorrecto():
    resultado = area_jerarquica([0, 1, 1], [0, 0, 0], [5, 6, 7], [5, 6, 3])

    # El tercero se deja: es un error que cuenta como falso positivo del área 3.
    assert resultado.tolist() == [5, FUERA_DEL_DOMINIO, 3]


def test_evaluar_jerarquico_coincide_con_area_si_el_modelo_es_coherente():
    informe = evaluar(DOMINIO_REAL, DOMINIO_PRED, AREA_REAL, AREA_PRED)

    assert informe["jerarquico"] == pytest.approx(informe["area"])


def test_evaluar_calcula_los_tres_niveles():
    informe = evaluar(DOMINIO_REAL, DOMINIO_PRED, AREA_REAL, AREA_PRED)

    assert set(informe) == {"dominio", "area", "jerarquico"}
    assert informe["dominio"]["accuracy"] == pytest.approx(5 / 6)
    assert informe["area"]["accuracy"] == pytest.approx(3 / 6)
    # Ambos niveles correctos: documentos 0, 3 y 4.
    assert informe["jerarquico"]["accuracy"] == pytest.approx(3 / 6)


def test_evaluar_jerarquico_penaliza_area_correcta_con_dominio_incorrecto():
    # Caso artificial: el área es correcta, pero el dominio predicho no.
    informe = evaluar([0, 1], [0, 0], [0, 2], [0, 2])

    assert informe["area"]["accuracy"] == 1.0
    assert informe["jerarquico"]["accuracy"] == 0.5


def test_tabla_metricas_indexa_por_modelo_y_nivel():
    informe = evaluar(DOMINIO_REAL, DOMINIO_PRED, AREA_REAL, AREA_PRED)

    tabla = tabla_metricas({"svm": informe, "nb": informe})

    assert tabla.shape == (6, 7)
    assert tabla.loc[("svm", "dominio"), "accuracy"] == pytest.approx(5 / 6)


def test_reporte_por_clase_ordena_de_peor_a_mejor():
    tabla = reporte_por_clase([0, 0, 1, 1], [0, 0, 0, 1], nombres={0: "a", 1: "b"})

    assert tabla.index.tolist() == [1, 0]
    assert tabla["nombre"].tolist() == ["b", "a"]
    assert tabla.loc[0, "soporte"] == 2


def test_matriz_confusion_usa_nombres():
    matriz = matriz_confusion([0, 1, 1], [0, 0, 1], [0, 1], {0: "a", 1: "b"})

    assert matriz.loc["b", "a"] == 1
    assert matriz.loc["b", "b"] == 1
    assert matriz.to_numpy().sum() == 3


def test_matrices_area_por_dominio_cuenta_los_enviados_a_otro_dominio():
    matrices = matrices_area_por_dominio(
        DOMINIO_REAL, DOMINIO_PRED, AREA_REAL, AREA_PRED, {0: [0, 1], 1: [2, 3]}
    )

    assert set(matrices) == {0, 1}
    assert matrices[0].columns.tolist() == [0, 1, "otro dominio"]
    assert matrices[0].loc[1, "otro dominio"] == 1
    assert matrices[0].to_numpy().sum() == 3
    assert matrices[1].loc[3, 2] == 1


def test_guardar_json_convierte_tipos_de_numpy(tmp_path):
    ruta = guardar_json(
        {"a": np.int64(3), "b": np.float32(0.5), "c": np.arange(2)}, tmp_path / "x/m.json"
    )

    assert json.loads(ruta.read_text(encoding="utf-8")) == {"a": 3, "b": 0.5, "c": [0, 1]}
