import pickle

import numpy as np
import pytest
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import ComplementNB
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

from clasificador_ml.jerarquico import (
    ClasificadorJerarquico,
    ClasificadorPlano,
    condicional_desde_plano,
    decodificar,
    requiere_revision,
    terminos_clave,
)

# Dominio 0 (áreas 10 y 11), dominio 1 (áreas 20 y 21) y dominio 2 con una sola área (30).
AREA_A_DOMINIO = {10: 0, 11: 0, 20: 1, 21: 1, 30: 2}
VOCABULARIO = {
    10: ["neural", "network", "deep", "layer"],
    11: ["database", "query", "index", "sql"],
    20: ["patient", "tumor", "cancer", "therapy"],
    21: ["heart", "cardiac", "artery", "blood"],
    30: ["protein", "enzyme", "gene", "cell"],
}
COMUNES = ["study", "result", "method", "analysis"]


def _corpus(por_area=12, semilla=0):
    generador = np.random.default_rng(semilla)
    textos, areas = [], []
    for area, palabras in VOCABULARIO.items():
        for _ in range(por_area):
            tokens = list(generador.choice(palabras, 6)) + list(generador.choice(COMUNES, 3))
            textos.append(" ".join(tokens))
            areas.append(area)
    return textos, np.array(areas)


def _nb():
    return Pipeline([("tfidf", TfidfVectorizer()), ("clf", ComplementNB(alpha=0.3))])


def _svm():
    clasificador = CalibratedClassifierCV(LinearSVC(C=1.0), cv=3, ensemble=False)
    return Pipeline([("tfidf", TfidfVectorizer()), ("clf", clasificador)])


@pytest.fixture(scope="module")
def corpus():
    return _corpus()


# --- funciones sobre probabilidades --------------------------------------------------------


def test_condicional_desde_plano_suma_las_areas_de_cada_dominio():
    p_area = np.array([[0.1, 0.3, 0.6]])
    dominio_de_area = np.array([0, 0, 1])

    p_dominio, p_condicional = condicional_desde_plano(p_area, dominio_de_area, 2)

    assert p_dominio == pytest.approx(np.array([[0.4, 0.6]]))
    assert p_condicional == pytest.approx(np.array([[0.25, 0.75, 1.0]]))


def test_decodificar_elige_el_area_dentro_del_dominio_predicho():
    # El área 2 tiene la mayor P(área | dominio), pero su dominio (1) no es el predicho.
    p_dominio = np.array([[0.7, 0.3]])
    p_condicional = np.array([[0.4, 0.6, 0.99]])

    decision = decodificar(p_dominio, p_condicional, np.array([0, 0, 1]))

    assert decision["dominio"].tolist() == [0]
    assert decision["area"].tolist() == [1]
    assert decision["confianza_conjunta"] == pytest.approx([0.42])


@pytest.mark.parametrize(
    ("dominio", "conjunta", "esperado"),
    [(0.9, 0.8, False), (0.59, 0.8, True), (0.9, 0.39, True), (0.60, 0.40, False)],
)
def test_requiere_revision_por_umbrales(dominio, conjunta, esperado):
    assert bool(requiere_revision(dominio, conjunta, 0.60, 0.40)) is esperado


# --- clasificador jerárquico ---------------------------------------------------------------


@pytest.mark.parametrize("plantilla", [_nb, _svm])
def test_jerarquico_aprende_el_corpus(corpus, plantilla):
    textos, areas = corpus
    modelo = ClasificadorJerarquico(AREA_A_DOMINIO, plantilla()).fit(textos, areas)

    assert modelo.score(textos, areas) == 1.0
    assert set(modelo.submodelos()) == {"dominio", "area_0", "area_1", "area_2"}


def test_jerarquico_predict_proba_es_la_probabilidad_conjunta(corpus):
    textos, areas = corpus
    modelo = ClasificadorJerarquico(AREA_A_DOMINIO, _nb()).fit(textos, areas)

    probabilidades = modelo.predict_proba(textos[:5])

    assert probabilidades.shape == (5, len(AREA_A_DOMINIO))
    assert probabilidades.sum(axis=1) == pytest.approx(np.ones(5))
    assert (
        modelo.classes_[probabilidades.argmax(axis=1)].tolist()
        == modelo.predict(textos[:5]).tolist()
    )


def test_predecir_niveles_es_coherente(corpus):
    textos, areas = corpus
    modelo = ClasificadorJerarquico(AREA_A_DOMINIO, _nb()).fit(textos, areas)

    tabla = modelo.predecir_niveles(textos)

    assert (tabla["dominio_pred"] == tabla["area_pred"].map(AREA_A_DOMINIO)).all()
    producto = tabla["confianza_dominio"] * tabla["confianza_area"]
    assert tabla["confianza_conjunta"].to_numpy() == pytest.approx(producto.to_numpy())
    assert tabla["requiere_revision"].dtype == bool


def test_dominio_con_una_sola_area_tiene_confianza_de_area_uno(corpus):
    textos, areas = corpus
    modelo = ClasificadorJerarquico(AREA_A_DOMINIO, _nb()).fit(textos, areas)

    resultado = modelo.predecir_detallado(["protein enzyme gene cell study"])[0]

    assert resultado["area"]["id"] == 30
    assert resultado["area"]["confianza"] == pytest.approx(1.0)
    # Los términos salen del modelo de dominio, porque el de área es constante.
    assert {t["termino"] for t in resultado["terminos_clave"]} & {"protein", "enzyme"}


def test_predecir_detallado_formato_api(corpus):
    textos, areas = corpus
    modelo = ClasificadorJerarquico(AREA_A_DOMINIO, _svm()).fit(textos, areas)

    resultado = modelo.predecir_detallado(["deep neural network layer"], num_terminos=3)[0]

    assert resultado["dominio"]["id"] == 0
    assert resultado["area"]["id"] == 10
    assert len(resultado["dominio"]["alternativas"]) == 3
    assert resultado["dominio"]["alternativas"][0]["id"] == 0
    # Las alternativas de área son del dominio predicho (aquí solo hay dos).
    assert [a["id"] for a in resultado["area"]["alternativas"]] == [10, 11]
    assert resultado["confianza_conjunta"] == pytest.approx(
        resultado["dominio"]["confianza"] * resultado["area"]["confianza"]
    )
    assert isinstance(resultado["requiere_revision"], bool)
    assert 0 < len(resultado["terminos_clave"]) <= 3
    assert {t["termino"] for t in resultado["terminos_clave"]} <= {
        "deep",
        "neural",
        "network",
        "layer",
    }


def test_umbrales_altos_marcan_revision(corpus):
    textos, areas = corpus
    modelo = ClasificadorJerarquico(
        AREA_A_DOMINIO, _nb(), umbral_dominio=1.01, umbral_conjunta=0.0
    ).fit(textos, areas)

    assert modelo.predecir_niveles(textos)["requiere_revision"].all()


def test_preprocesador_se_aplica_antes_de_clasificar(corpus):
    class Minusculas:
        def transform(self, textos):
            return [t.lower() for t in textos]

    textos, areas = corpus
    modelo = ClasificadorJerarquico(AREA_A_DOMINIO, _nb()).fit(textos, areas)
    modelo.preprocesador = Minusculas()

    assert modelo.predict(["DEEP NEURAL NETWORK"]).tolist() == [10]


def test_area_sin_dominio_da_error(corpus):
    textos, areas = corpus

    with pytest.raises(ValueError, match="sin dominio"):
        ClasificadorJerarquico({10: 0}, _nb()).fit(textos, areas)


def test_jerarquico_se_puede_serializar(corpus):
    textos, areas = corpus
    modelo = ClasificadorJerarquico(AREA_A_DOMINIO, _nb()).fit(textos, areas)

    copia = pickle.loads(pickle.dumps(modelo))

    assert copia.predict(textos).tolist() == modelo.predict(textos).tolist()


# --- clasificador plano --------------------------------------------------------------------


@pytest.mark.parametrize("plantilla", [_nb, _svm])
def test_plano_aprende_el_corpus_y_deduce_el_dominio(corpus, plantilla):
    textos, areas = corpus
    modelo = ClasificadorPlano(AREA_A_DOMINIO, plantilla()).fit(textos, areas)

    tabla = modelo.predecir_niveles(textos)

    assert modelo.score(textos, areas) == 1.0
    assert (tabla["dominio_pred"] == tabla["area_pred"].map(AREA_A_DOMINIO)).all()
    assert modelo.predict_proba(textos).sum(axis=1) == pytest.approx(np.ones(len(textos)))


def test_plano_devuelve_terminos_clave(corpus):
    textos, areas = corpus
    modelo = ClasificadorPlano(AREA_A_DOMINIO, _nb()).fit(textos, areas)

    resultado = modelo.predecir_detallado(["database sql query index"])[0]

    assert resultado["area"]["id"] == 11
    assert resultado["terminos_clave"]


# --- términos clave ------------------------------------------------------------------------


def test_terminos_clave_sin_terminos_conocidos_devuelve_vacio(corpus):
    textos, areas = corpus
    pipeline = _nb().fit(textos, areas)

    assert terminos_clave(pipeline, "palabras desconocidas", 10) == []
    assert terminos_clave(pipeline, "deep neural", 999) == []


def test_terminos_clave_en_modelo_binario(corpus):
    textos, areas = corpus
    mascara = np.isin(areas, [10, 11])
    pipeline = Pipeline([("tfidf", TfidfVectorizer()), ("clf", LinearSVC())]).fit(
        np.array(textos)[mascara], areas[mascara]
    )

    positivos = {t["termino"] for t in terminos_clave(pipeline, "deep sql", 10)}
    negativos = {t["termino"] for t in terminos_clave(pipeline, "deep sql", 11)}

    assert positivos == {"deep"}
    assert negativos == {"sql"}
