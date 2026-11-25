"""Pruebas del script de rendimiento, sin API real: `httpx.MockTransport` hace de servidor."""

import json

import httpx
import pandas as pd
import pymupdf
import pytest
from rendimiento import (
    PAGINAS_PDF,
    cargar_resumenes,
    crear_pdf,
    ejecutar,
    informe,
    main,
    percentil,
    resumir,
)

from app.extraccion import extraer_documento


def resumen(i: int, palabras: int = 60) -> str:
    # Palabras únicas: la extracción quita las líneas repetidas entre páginas (encabezados).
    return " ".join(f"term{i}x{j}" for j in range(palabras)) + f" doc{i}"


class ApiFalsa:
    """Responde como la API y guarda lo que recibe."""

    def __init__(self, estado: int = 201) -> None:
        self.estado = estado
        self.textos: list[dict] = []
        self.archivos: list[bytes] = []

    def __call__(self, peticion: httpx.Request) -> httpx.Response:
        if peticion.url.path == "/api/v1/salud":
            return httpx.Response(200, json={"estado": "ok"})
        if peticion.url.path.endswith("/texto"):
            self.textos.append(json.loads(peticion.content))
        else:
            self.archivos.append(peticion.content)
        return httpx.Response(self.estado, json={"tiempo_ms": 12.5})

    def cliente(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self), base_url="http://api")


def test_percentil_interpola_como_numpy():
    valores = list(range(1, 101))
    assert percentil(valores, 50) == pytest.approx(50.5)
    assert percentil(valores, 95) == pytest.approx(95.05)
    assert percentil([7.0], 95) == 7.0
    with pytest.raises(ValueError):
        percentil([], 95)


def test_resumir_compara_el_p95_con_la_meta():
    rapido = resumir("texto", [100.0] * 19 + [1900.0], [10.0] * 20)
    lento = resumir("pdf", [1000.0] * 18 + [6000.0, 7000.0], [10.0] * 20)
    assert rapido.cumple and rapido.limite == 2000
    assert not lento.cumple and lento.limite == 5000
    assert lento.p95 > 5000


def test_el_pdf_tiene_20_paginas_y_la_api_encuentra_el_resumen():
    texto = resumen(1)
    contenido = crear_pdf("Performance test document", texto, [resumen(i) for i in range(10, 15)])

    with pymupdf.open(stream=contenido, filetype="pdf") as documento:
        assert documento.page_count == PAGINAS_PDF
        assert all(len(pagina.get_text().split()) > 200 for pagina in documento)
    extraccion = extraer_documento(contenido, "prueba.pdf")
    assert extraccion.fuente_texto == "abstract"
    assert extraccion.titulo == "Performance test document"
    assert extraccion.texto.split()[-1] == "doc1"


def test_ejecutar_calienta_y_mide_cada_tipo():
    api = ApiFalsa()
    resumenes = [resumen(i) for i in range(6)]
    with api.cliente() as cliente:
        resultados = ejecutar(cliente, resumenes, repeticiones=5)

    assert [r.tipo for r in resultados] == ["texto", "pdf"]
    assert all(r.n == 5 and r.cumple for r in resultados)
    assert all(r.servidor_p95 == 12.5 for r in resultados)
    # 1 de calentamiento + 5 medidos, cada uno con un resumen distinto.
    assert [t["texto"] for t in api.textos] == resumenes
    assert len(api.archivos) == 6
    assert len(set(api.archivos)) == 6


def test_ejecutar_exige_resumenes_suficientes():
    with ApiFalsa().cliente() as cliente, pytest.raises(ValueError):
        ejecutar(cliente, [resumen(0)] * 3, repeticiones=5)


def test_un_error_de_la_api_detiene_la_prueba():
    with ApiFalsa(estado=503).cliente() as cliente, pytest.raises(RuntimeError, match="503"):
        ejecutar(cliente, [resumen(i) for i in range(3)], repeticiones=2)


def test_informe_en_markdown():
    tabla = informe([resumir("texto", [100.0, 200.0], [50.0, 60.0])])
    assert "| Texto pegado | 2 |" in tabla
    assert "< 2 s | ✅ |" in tabla


def test_cargar_resumenes_descarta_los_cortos(tmp_path):
    ruta = tmp_path / "test.parquet"
    pd.DataFrame({"texto": [resumen(i) for i in range(4)] + ["muy corto"]}).to_parquet(ruta)

    elegidos = cargar_resumenes(4, ruta)
    assert sorted(elegidos) == sorted(resumen(i) for i in range(4))
    with pytest.raises(ValueError):
        cargar_resumenes(5, ruta)
    with pytest.raises(FileNotFoundError):
        cargar_resumenes(1, tmp_path / "no-existe.parquet")


def test_main_guarda_json_y_devuelve_el_codigo(tmp_path, monkeypatch):
    ruta = tmp_path / "test.parquet"
    pd.DataFrame({"texto": [resumen(i) for i in range(4)]}).to_parquet(ruta)
    api = ApiFalsa()
    original = httpx.Client
    monkeypatch.setattr(
        "rendimiento.httpx.Client",
        lambda **kw: original(transport=httpx.MockTransport(api), base_url=kw["base_url"]),
    )
    salida = tmp_path / "resultados.json"

    codigo = main(["--repeticiones", "3", "--datos", str(ruta), "--salida", str(salida)])

    assert codigo == 0
    guardado = json.loads(salida.read_text(encoding="utf-8"))
    assert [r["tipo"] for r in guardado["resultados"]] == ["texto", "pdf"]
    assert all(r["n"] == 3 for r in guardado["resultados"])
