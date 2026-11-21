"""Pruebas de la evaluación con artículos externos. No usan la red: los buscadores se simulan."""

import json

import pandas as pd
import pytest

from clasificador_ml import externos
from clasificador_ml.externos import (
    BUSQUEDAS,
    Busqueda,
    cargar_revision,
    descargar,
    evaluar_externos,
    guardar_articulos,
    leer_arxiv,
    leer_pubmed,
)

CATEGORIAS = {
    "dominios": [
        {
            "id": 0,
            "nombre": "Computer Science",
            "areas": [{"id": 0, "nombre": "Computer vision"}, {"id": 1, "nombre": "Cryptography"}],
        },
        {"id": 5, "nombre": "Medical Sciences", "areas": [{"id": 76, "nombre": "Asthma"}]},
    ]
}

ARXIV = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2401.01234v2</id>
    <published>2024-01-03T10:00:00Z</published>
    <title>Object  recognition
      in video</title>
    <summary>  We study object recognition.  </summary>
  </entry>
</feed>"""

PUBMED = b"""<?xml version="1.0"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>38000001</PMID>
      <Article>
        <ArticleTitle>Asthma in <i>adults</i>.</ArticleTitle>
        <Abstract>
          <AbstractText Label="BACKGROUND">Asthma is common.</AbstractText>
          <AbstractText Label="RESULTS">Inhalers <sup>help</sup>.</AbstractText>
        </Abstract>
        <ArticleDate><Year>2023</Year></ArticleDate>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>"""


def _articulo(identificador, palabras=60, fuente="arxiv"):
    return {
        "fuente": fuente,
        "identificador": identificador,
        "titulo": f"Artículo {identificador}",
        "resumen": " ".join(["image"] * palabras),
        "anio": 2024,
        "url": f"https://ejemplo.org/{identificador}",
    }


def test_las_busquedas_cubren_5_dominios_con_6_areas():
    conteo = pd.Series([b.dominio for b in BUSQUEDAS]).value_counts()
    assert len(conteo) == 5
    assert (conteo == 6).all()
    assert len({(b.dominio, b.area) for b in BUSQUEDAS}) == 30


def test_las_busquedas_usan_areas_del_catalogo_real():
    ruta = externos.DATOS_PROCESADOS / "categorias.json"
    if not ruta.is_file():
        pytest.skip("Sin data/processed/categorias.json (por ejemplo, en el CI)")
    categorias = json.loads(ruta.read_text(encoding="utf-8"))
    validas = {(d["nombre"], a["nombre"]) for d in categorias["dominios"] for a in d["areas"]}
    assert {(b.dominio, b.area) for b in BUSQUEDAS} <= validas


def test_leer_arxiv():
    (articulo,) = leer_arxiv(ARXIV)
    assert articulo == {
        "fuente": "arxiv",
        "identificador": "2401.01234v2",
        "titulo": "Object recognition in video",
        "resumen": "We study object recognition.",
        "anio": 2024,
        "url": "http://arxiv.org/abs/2401.01234v2",
    }


def test_leer_pubmed_une_secciones_y_etiquetas():
    (articulo,) = leer_pubmed(PUBMED)
    assert articulo["identificador"] == "38000001"
    assert articulo["titulo"] == "Asthma in adults."
    assert articulo["resumen"] == "Asthma is common. Inhalers help."
    assert articulo["anio"] == 2023
    assert articulo["url"] == "https://pubmed.ncbi.nlm.nih.gov/38000001/"


def test_descargar_incluye_el_primero_y_deja_reservas():
    respuestas = {
        "q1": [_articulo("a"), _articulo("corto", palabras=10), _articulo("b"), _articulo("c")],
        # "a" ya salió en otra área: no se repite.
        "q2": [_articulo("a"), _articulo("d")],
        "q3": [],
    }
    busquedas = [
        Busqueda("arxiv", "q1", "Computer Science", "Computer vision"),
        Busqueda("arxiv", "q2", "Computer Science", "Cryptography"),
        Busqueda("arxiv", "q3", "Computer Science", "Cryptography"),
    ]
    tabla = descargar(
        busquedas,
        por_area=2,
        buscadores={"arxiv": lambda consulta, cantidad: respuestas[consulta]},
        pausas={},
    )
    assert tabla["identificador"].tolist() == ["a", "b", "d"]
    assert tabla["incluir"].tolist() == ["si", "reserva", "si"]
    assert tabla["area"].tolist() == ["Computer vision", "Computer vision", "Cryptography"]
    assert list(tabla.columns) == externos.COLUMNAS


def _revision(tmp_path, filas):
    tabla = pd.DataFrame(
        [{**_articulo(str(i)), "revisado": "si", "notas": "", **f} for i, f in enumerate(filas)],
        columns=externos.COLUMNAS,
    )
    return guardar_articulos(tabla, tmp_path / "articulos.xlsx")


def test_cargar_revision_solo_los_incluidos_con_sus_ids(tmp_path):
    ruta = _revision(
        tmp_path,
        [
            {"incluir": "si", "dominio": "Computer Science", "area": "Cryptography"},
            {"incluir": "reserva", "dominio": "Computer Science", "area": "Computer vision"},
            {"incluir": " SI ", "dominio": "Medical Sciences", "area": "Asthma"},
            {"incluir": "no", "dominio": "Medical Sciences", "area": "Asthma"},
        ],
    )
    articulos = cargar_revision(ruta, CATEGORIAS)
    assert articulos["identificador"].tolist() == ["0", "2"]
    assert articulos["id_dominio"].tolist() == [0, 5]
    assert articulos["id_area"].tolist() == [1, 76]


def test_cargar_revision_rechaza_categorias_inexistentes(tmp_path):
    ruta = _revision(
        tmp_path,
        [
            {"incluir": "si", "dominio": "Computer Science", "area": "Asthma"},
            {"incluir": "si", "dominio": "Química", "area": "Enzimas"},
        ],
    )
    with pytest.raises(ValueError, match="no existen") as error:
        cargar_revision(ruta, CATEGORIAS)
    assert "Computer Science / Asthma" in str(error.value)
    assert "Química / Enzimas" in str(error.value)


def test_cargar_revision_sin_incluidos(tmp_path):
    ruta = _revision(tmp_path, [{"incluir": "no", "dominio": "Medical Sciences", "area": "Asthma"}])
    with pytest.raises(ValueError, match="Ningún artículo"):
        cargar_revision(ruta, CATEGORIAS)


class ModeloFalso:
    """Predice siempre Computer Science / Computer vision; el último con poca confianza."""

    def predecir_niveles(self, textos):
        n = len(textos)
        return pd.DataFrame(
            {
                "dominio_pred": [0] * n,
                "area_pred": [0] * n,
                "confianza_dominio": [0.9] * (n - 1) + [0.3],
                "confianza_area": [0.8] * n,
                "confianza_conjunta": [0.72] * (n - 1) + [0.24],
                "requiere_revision": [False] * (n - 1) + [True],
            }
        )


def test_evaluar_externos(tmp_path):
    ruta = _revision(
        tmp_path,
        [
            {"incluir": "si", "dominio": "Computer Science", "area": "Computer vision"},
            {"incluir": "si", "dominio": "Computer Science", "area": "Cryptography"},
            {"incluir": "si", "dominio": "Medical Sciences", "area": "Asthma"},
        ],
    )
    tabla, metricas = evaluar_externos(cargar_revision(ruta, CATEGORIAS), ModeloFalso(), CATEGORIAS)

    assert tabla["acierto_dominio"].tolist() == [True, True, False]
    assert tabla["acierto_area"].tolist() == [True, False, False]
    assert tabla["area_pred"].tolist() == ["Computer vision"] * 3
    assert metricas["articulos"] == 3
    assert metricas["dominio"]["accuracy"] == pytest.approx(2 / 3)
    assert metricas["jerarquico"]["accuracy"] == pytest.approx(1 / 3)
    assert metricas["revision"]["porcentaje_revision"] == pytest.approx(1 / 3)
    assert metricas["revision"]["accuracy_jerarquica_aceptados"] == pytest.approx(1 / 2)
    assert metricas["por_dominio"]["Medical Sciences"] == {
        "articulos": 1,
        "accuracy_dominio": 0.0,
        "accuracy_area": 0.0,
    }


def test_main_no_sobrescribe_una_revision(tmp_path, monkeypatch):
    destino = tmp_path / "articulos.xlsx"
    destino.write_text("revisión del usuario")
    monkeypatch.setattr(externos, "descargar", lambda **_: pytest.fail("no debe descargar"))
    with pytest.raises(SystemExit):
        externos.main(["descargar", "--destino", str(destino)])
    assert destino.read_text() == "revisión del usuario"


def test_main_descargar(tmp_path, monkeypatch):
    tabla = pd.DataFrame(
        [
            {
                **_articulo("a"),
                "incluir": "si",
                "dominio": "Computer Science",
                "area": "Cryptography",
            }
        ],
        columns=externos.COLUMNAS,
    )
    monkeypatch.setattr(externos, "descargar", lambda **_: tabla)
    destino = tmp_path / "nuevo" / "articulos.xlsx"
    externos.main(["descargar", "--destino", str(destino)])
    assert pd.read_excel(destino, dtype=str)["identificador"].tolist() == ["a"]


def test_main_evaluar(tmp_path, monkeypatch, capsys):
    ruta = _revision(
        tmp_path,
        [
            {"incluir": "si", "dominio": "Computer Science", "area": "Computer vision"},
            {"incluir": "si", "dominio": "Medical Sciences", "area": "Asthma"},
        ],
    )
    categorias = tmp_path / "categorias.json"
    categorias.write_text(json.dumps(CATEGORIAS), encoding="utf-8")
    info = {"algoritmo": "linear_svc", "version": "v1"}
    monkeypatch.setattr("clasificador_ml.artefactos.cargar_activo", lambda _: (ModeloFalso(), info))

    externos.main(["evaluar", "--articulos", str(ruta), "--categorias", str(categorias)])

    metricas = json.loads((tmp_path / "metricas.json").read_text(encoding="utf-8"))
    assert metricas["modelo"] == info
    assert metricas["articulos"] == 2
    assert len(pd.read_excel(tmp_path / "evaluacion.xlsx")) == 2
    assert "2 artículos externos" in capsys.readouterr().out


def test_buscar_arxiv_filtra_por_fecha(monkeypatch):
    llamadas = []
    monkeypatch.setattr(externos, "_get", lambda url, p: llamadas.append(p) or ARXIV)
    (articulo,) = externos.buscar_arxiv("cat:cs.CV", 3)
    assert articulo["identificador"] == "2401.01234v2"
    assert llamadas[0]["search_query"].startswith("(cat:cs.CV) AND submittedDate:[2020")
    assert llamadas[0]["max_results"] == 3


def test_buscar_pubmed_busca_y_descarga(monkeypatch):
    llamadas = []

    def _get(url, parametros):
        llamadas.append((url, parametros))
        if url.endswith("esearch.fcgi"):
            return json.dumps({"esearchresult": {"idlist": ["38000001"]}}).encode()
        return PUBMED

    monkeypatch.setattr(externos, "_get", _get)
    monkeypatch.setattr(externos.time, "sleep", lambda _: None)
    (articulo,) = externos.buscar_pubmed('"Asthma"[majr]', 4)

    assert articulo["titulo"] == "Asthma in adults."
    termino = llamadas[0][1]["term"]
    assert termino.startswith('("Asthma"[majr]) AND 2020:3000[dp]')
    assert "NOT review[pt]" in termino
    assert "email" not in llamadas[0][1]  # no se envían datos personales
    assert llamadas[1][1]["id"] == "38000001"


def test_buscar_pubmed_sin_resultados(monkeypatch):
    respuesta = json.dumps({"esearchresult": {"idlist": []}}).encode()
    monkeypatch.setattr(externos, "_get", lambda url, p: respuesta)
    assert externos.buscar_pubmed("nada", 2) == []


def test_get_reintenta_y_luego_falla(monkeypatch):
    intentos = []

    def _urlopen(solicitud, timeout):
        intentos.append(solicitud.get_header("User-agent"))
        raise OSError("503")

    monkeypatch.setattr(externos.urllib.request, "urlopen", _urlopen)
    monkeypatch.setattr(externos.time, "sleep", lambda _: None)
    with pytest.raises(OSError):
        externos._get("https://ejemplo.org", {"q": 1}, intentos=2)
    assert intentos == [externos.AGENTE] * 2
