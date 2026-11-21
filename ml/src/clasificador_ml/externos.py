"""Evaluación con artículos reales externos a WOS (plan de pruebas, sección 6.6 del diseño).

El modelo se evaluó en test, que viene del mismo dataset con que se entrenó. Aquí se mide con
**30 artículos reales** de arXiv y PubMed publicados desde 2020, que no pueden estar en
WOS-46985. Se cubren 5 de los 7 dominios (6 artículos por dominio); Ingeniería Civil e
Ingeniería Mecánica y Aeroespacial casi no tienen artículos en esas fuentes.

Flujo:

1. ``python -m clasificador_ml.externos descargar``: busca 2 candidatos por área y los guarda
   en ``data/external/articulos.xlsx``. El primero queda con ``incluir = si`` y el segundo
   con ``incluir = reserva``.
2. **Revisión humana:** leer título y resumen de cada artículo con ``incluir = si``. Si la
   categoría no corresponde, corregir ``dominio``/``area`` o cambiarlo por la reserva (poner
   ``no`` en uno y ``si`` en el otro). Anotar ``revisado = si``.
3. ``python -m clasificador_ml.externos evaluar``: clasifica los incluidos con el modelo activo
   y guarda ``evaluacion.xlsx`` (artículo por artículo) y ``metricas.json``.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from clasificador_ml.evaluacion import evaluar, guardar_json
from clasificador_ml.rutas import DATOS, DATOS_PROCESADOS, MODELOS

DATOS_EXTERNOS = DATOS / "external"
ARCHIVO_ARTICULOS = DATOS_EXTERNOS / "articulos.xlsx"
DESDE_ANIO = 2020  # WOS-46985 es de 2017: lo publicado desde 2020 no puede estar en el dataset.
MINIMO_PALABRAS = 50  # los resúmenes de WOS tienen unas 200 palabras

URL_ARXIV = "https://export.arxiv.org/api/query"
URL_PUBMED = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
# Nombre genérico del cliente: no se envían datos personales a los servicios externos.
AGENTE = "sicda-evaluacion/0.1"
ATOM = {"atom": "http://www.w3.org/2005/Atom"}

COLUMNAS = [
    "incluir",
    "revisado",
    "dominio",
    "area",
    "titulo",
    "resumen",
    "fuente",
    "identificador",
    "anio",
    "url",
    "consulta",
    "notas",
]


@dataclass(frozen=True)
class Busqueda:
    """Una consulta a arXiv o PubMed que debería devolver artículos de un área de WOS."""

    fuente: str  # "arxiv" o "pubmed"
    consulta: str
    dominio: str
    area: str


def _arxiv(consulta: str, dominio: str, area: str) -> Busqueda:
    return Busqueda("arxiv", consulta, dominio, area)


def _pubmed(consulta: str, dominio: str, area: str) -> Busqueda:
    return Busqueda("pubmed", consulta, dominio, area)


CS, ECE, PSI = "Computer Science", "Electrical and Computer Engineering", "Psychology"
MED, BIO = "Medical Sciences", "Biochemistry"

# 6 áreas por dominio, elegidas porque tienen una categoría de arXiv o un término MeSH de
# PubMed equivalente. `[majr]` exige que sea un tema principal del artículo.
BUSQUEDAS: list[Busqueda] = [
    _arxiv("cat:cs.CV AND ti:recognition", CS, "Computer vision"),
    _arxiv("cat:cs.LG AND ti:learning", CS, "Machine learning"),
    _arxiv("cat:cs.CR AND ti:encryption", CS, "Cryptography"),
    _arxiv("cat:cs.GR AND ti:rendering", CS, "Computer graphics"),
    _arxiv("cat:cs.DC AND ti:distributed", CS, "Distributed computing"),
    _arxiv("cat:cs.DB AND ti:SQL", CS, "Relational databases"),
    _arxiv("cat:eess.SY AND ti:PID", ECE, "PID controller"),
    _arxiv('cat:eess.SY AND ti:"system identification"', ECE, "System identification"),
    _arxiv('cat:eess.SY AND ti:"state space"', ECE, "State space representation"),
    _arxiv("ti:microcontroller", ECE, "Microcontroller"),
    _arxiv('ti:"induction motor"', ECE, "Electric motor"),
    _arxiv('ti:"operational amplifier"', ECE, "Operational amplifier"),
    _pubmed('"Prejudice"[majr]', PSI, "Prejudice"),
    _pubmed('"Leadership"[majr]', PSI, "Leadership"),
    _pubmed('"Feeding and Eating Disorders"[majr]', PSI, "Eating disorders"),
    _pubmed('"Borderline Personality Disorder"[majr]', PSI, "Borderline personality disorder"),
    _pubmed('"Child Abuse"[majr]', PSI, "Child abuse"),
    _pubmed('"Nonverbal Communication"[majr]', PSI, "Nonverbal communication"),
    _pubmed('"Alzheimer Disease"[majr]', MED, "Alzheimer's Disease"),
    _pubmed('"Asthma"[majr]', MED, "Asthma"),
    _pubmed('"Atrial Fibrillation"[majr]', MED, "Atrial Fibrillation"),
    _pubmed('"Hepatitis C"[majr]', MED, "Hepatitis C"),
    _pubmed('"Multiple Sclerosis"[majr]', MED, "Multiple Sclerosis"),
    _pubmed('"Osteoporosis"[majr]', MED, "Osteoporosis"),
    _pubmed('"Polymerase Chain Reaction"[majr]', BIO, "Polymerase chain reaction"),
    _pubmed('"Blotting, Northern"[majr]', BIO, "Northern blotting"),
    _pubmed('"Blotting, Southern"[majr]', BIO, "Southern blotting"),
    _pubmed('"enzyme kinetics"[tiab]', BIO, "Enzymology"),
    _pubmed('"Immunity, Innate"[majr]', BIO, "Immunology"),
    _pubmed('"Molecular Biology"[majr]', BIO, "Molecular biology"),
]


# --- Descarga ---------------------------------------------------------------------------------


def _get(url: str, parametros: dict[str, Any], intentos: int = 3) -> bytes:
    """GET con reintentos: arXiv y PubMed a veces responden 429/503 si se les pide rápido."""
    direccion = f"{url}?{urllib.parse.urlencode(parametros)}"
    solicitud = urllib.request.Request(direccion, headers={"User-Agent": AGENTE})
    for intento in range(intentos):
        try:
            with urllib.request.urlopen(solicitud, timeout=30) as respuesta:
                return respuesta.read()
        except OSError:
            if intento == intentos - 1:
                raise
            time.sleep(5 * (intento + 1))
    raise AssertionError("inalcanzable")


def _limpiar(texto: str | None) -> str:
    return " ".join((texto or "").split())


def leer_arxiv(xml: bytes) -> list[dict[str, Any]]:
    """Artículos de una respuesta Atom de la API de arXiv."""
    articulos = []
    for entrada in ET.fromstring(xml).findall("atom:entry", ATOM):
        url = _limpiar(entrada.findtext("atom:id", namespaces=ATOM))
        articulos.append(
            {
                "fuente": "arxiv",
                "identificador": url.rsplit("/abs/", 1)[-1],
                "titulo": _limpiar(entrada.findtext("atom:title", namespaces=ATOM)),
                "resumen": _limpiar(entrada.findtext("atom:summary", namespaces=ATOM)),
                "anio": int((entrada.findtext("atom:published", namespaces=ATOM) or "0")[:4]),
                "url": url,
            }
        )
    return articulos


def leer_pubmed(xml: bytes) -> list[dict[str, Any]]:
    """Artículos de una respuesta de `efetch` de PubMed (los resúmenes por secciones se unen)."""
    articulos = []
    for articulo in ET.fromstring(xml).iter("PubmedArticle"):
        pmid = articulo.findtext(".//PMID") or ""
        partes = ["".join(nodo.itertext()) for nodo in articulo.iter("AbstractText")]
        anio = articulo.findtext(".//PubDate/Year") or articulo.findtext(".//ArticleDate/Year")
        # El título puede traer etiquetas (<i>, <sup>): se toma todo su texto.
        nodo_titulo = articulo.find(".//ArticleTitle")
        titulo = "".join(nodo_titulo.itertext()) if nodo_titulo is not None else ""
        articulos.append(
            {
                "fuente": "pubmed",
                "identificador": pmid,
                "titulo": _limpiar(titulo),
                "resumen": _limpiar(" ".join(partes)),
                "anio": int(anio) if anio else None,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            }
        )
    return articulos


def buscar_arxiv(consulta: str, cantidad: int) -> list[dict[str, Any]]:
    fechas = f"submittedDate:[{DESDE_ANIO}01010000 TO 209912312359]"
    xml = _get(
        URL_ARXIV,
        {
            "search_query": f"({consulta}) AND {fechas}",
            "max_results": cantidad,
            "sortBy": "relevance",
        },
    )
    return leer_arxiv(xml)


def buscar_pubmed(consulta: str, cantidad: int) -> list[dict[str, Any]]:
    # Solo artículos de revista originales: sin capítulos de libro (StatPearls), revisiones,
    # reportes de caso ni estudios con animales, que se parecen poco a los resúmenes de WOS.
    filtros = (
        f"{DESDE_ANIO}:3000[dp] AND hasabstract[text] AND english[lang] "
        "AND journal article[pt] NOT review[pt] NOT case reports[pt] "
        "NOT (animals[mh] NOT humans[mh])"
    )
    respuesta = _get(
        f"{URL_PUBMED}/esearch.fcgi",
        {
            "db": "pubmed",
            "term": f"({consulta}) AND {filtros}",
            "retmax": cantidad,
            "retmode": "json",
            "sort": "relevance",
            "tool": "sicda",
        },
    )
    ids = json.loads(respuesta)["esearchresult"]["idlist"]
    if not ids:
        return []
    time.sleep(0.5)  # PubMed admite 3 solicitudes por segundo sin clave
    xml = _get(
        f"{URL_PUBMED}/efetch.fcgi",
        {"db": "pubmed", "id": ",".join(ids), "retmode": "xml", "tool": "sicda"},
    )
    return leer_pubmed(xml)


BUSCADORES: dict[str, Callable[[str, int], list[dict[str, Any]]]] = {
    "arxiv": buscar_arxiv,
    "pubmed": buscar_pubmed,
}
# arXiv pide 3 s entre solicitudes; PubMed, menos de 3 por segundo.
PAUSAS = {"arxiv": 3.0, "pubmed": 1.0}


def descargar(
    busquedas: Sequence[Busqueda] = BUSQUEDAS,
    por_area: int = 2,
    buscadores: dict[str, Callable[[str, int], list[dict[str, Any]]]] | None = None,
    pausas: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Busca `por_area` candidatos por área: el primero se incluye y el resto queda de reserva.

    Se descartan los artículos repetidos y los de resumen ausente o corto (`MINIMO_PALABRAS`).
    """
    buscadores = buscadores or BUSCADORES
    pausas = PAUSAS if pausas is None else pausas
    vistos: set[tuple[str, str]] = set()
    filas = []
    for busqueda in busquedas:
        # Se piden de más por si alguno se repite o tiene un resumen muy corto.
        candidatos = buscadores[busqueda.fuente](busqueda.consulta, por_area + 6)
        time.sleep(pausas.get(busqueda.fuente, 0))
        elegidos = 0
        for articulo in candidatos:
            clave = (articulo["fuente"], articulo["identificador"])
            corto = len(articulo["resumen"].split()) < MINIMO_PALABRAS
            if clave in vistos or corto or elegidos == por_area:
                continue
            vistos.add(clave)
            filas.append(
                {
                    **articulo,
                    "incluir": "si" if elegidos == 0 else "reserva",
                    "revisado": "",
                    "dominio": busqueda.dominio,
                    "area": busqueda.area,
                    "consulta": busqueda.consulta,
                    "notas": "",
                }
            )
            elegidos += 1
        if elegidos == 0:
            print(f"Sin resultados para {busqueda.area}: {busqueda.consulta}")
        print(f"{busqueda.dominio} / {busqueda.area}: {elegidos} artículo(s)", flush=True)
    return pd.DataFrame(filas, columns=COLUMNAS)


def guardar_articulos(tabla: pd.DataFrame, ruta: Path | str) -> Path:
    """Excel para la revisión: columnas anchas y el resumen con ajuste de línea."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(ruta, engine="openpyxl") as escritor:
        tabla.to_excel(escritor, index=False, sheet_name="articulos")
        hoja = escritor.sheets["articulos"]
        anchos = {"titulo": 50, "resumen": 90, "dominio": 22, "area": 26, "url": 40, "notas": 30}
        for indice, columna in enumerate(tabla.columns):
            letra = hoja.cell(row=1, column=indice + 1).column_letter
            hoja.column_dimensions[letra].width = anchos.get(columna, 12)
        hoja.freeze_panes = "A2"
    return ruta


# --- Evaluación -------------------------------------------------------------------------------


def cargar_revision(ruta: Path | str, categorias: dict[str, Any]) -> pd.DataFrame:
    """Artículos con `incluir = si`, con los ids de su dominio y área.

    Raises:
        ValueError: si un dominio o un área no existen en `categorias.json`.
    """
    tabla = pd.read_excel(ruta, sheet_name="articulos", dtype=str).fillna("")
    incluidos = tabla[tabla["incluir"].str.strip().str.lower() == "si"].copy()
    if incluidos.empty:
        raise ValueError(f"Ningún artículo tiene incluir = si en {ruta}")

    dominios = {d["nombre"]: d for d in categorias["dominios"]}
    errores, id_dominio, id_area = [], [], []
    for _, fila in incluidos.iterrows():
        dominio = dominios.get(fila["dominio"].strip())
        areas = {a["nombre"]: a["id"] for a in dominio["areas"]} if dominio else {}
        area = areas.get(fila["area"].strip())
        if dominio is None or area is None:
            errores.append(f"«{fila['titulo'][:60]}»: {fila['dominio']} / {fila['area']}")
        id_dominio.append(dominio["id"] if dominio else -1)
        id_area.append(area if area is not None else -1)
    if errores:
        raise ValueError(
            "Dominio o área que no existen en categorias.json:\n  " + "\n  ".join(errores)
        )
    incluidos["id_dominio"], incluidos["id_area"] = id_dominio, id_area
    return incluidos.reset_index(drop=True)


def evaluar_externos(
    articulos: pd.DataFrame, modelo: Any, categorias: dict[str, Any]
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Clasifica el resumen de cada artículo y calcula las métricas por nivel.

    Devuelve la tabla artículo por artículo y las métricas. Con 30 artículos el F1-macro de
    área es poco estable (casi una clase por artículo): la cifra principal es la de dominio.
    """
    nombres_dominio = {d["id"]: d["nombre"] for d in categorias["dominios"]}
    nombres_area = {a["id"]: a["nombre"] for d in categorias["dominios"] for a in d["areas"]}

    predicciones = modelo.predecir_niveles(articulos["resumen"].tolist())
    tabla = articulos[["fuente", "identificador", "titulo", "url"]].copy()
    tabla["dominio_real"] = articulos["dominio"].str.strip()
    tabla["dominio_pred"] = [nombres_dominio[int(i)] for i in predicciones["dominio_pred"]]
    tabla["area_real"] = articulos["area"].str.strip()
    tabla["area_pred"] = [nombres_area[int(i)] for i in predicciones["area_pred"]]
    tabla["acierto_dominio"] = predicciones["dominio_pred"].to_numpy() == articulos["id_dominio"]
    tabla["acierto_area"] = predicciones["area_pred"].to_numpy() == articulos["id_area"]
    for columna in ("confianza_dominio", "confianza_conjunta", "requiere_revision"):
        tabla[columna] = predicciones[columna].to_numpy()

    metricas: dict[str, Any] = evaluar(
        articulos["id_dominio"],
        predicciones["dominio_pred"],
        articulos["id_area"],
        predicciones["area_pred"],
    )
    aceptados = ~tabla["requiere_revision"].to_numpy(dtype=bool)
    metricas["revision"] = {
        "porcentaje_revision": float(1 - aceptados.mean()),
        "accuracy_jerarquica_aceptados": (
            float(tabla["acierto_area"][aceptados].mean()) if aceptados.any() else None
        ),
    }
    metricas["por_dominio"] = {
        dominio: {
            "articulos": int(len(grupo)),
            "accuracy_dominio": float(grupo["acierto_dominio"].mean()),
            "accuracy_area": float(grupo["acierto_area"].mean()),
        }
        for dominio, grupo in tabla.groupby("dominio_real")
    }
    metricas["articulos"] = int(len(tabla))
    return tabla, metricas


def _imprimir(metricas: dict[str, Any]) -> None:
    dominio, area = metricas["dominio"], metricas["jerarquico"]
    revision = metricas["revision"]
    print(f"\n{metricas['articulos']} artículos externos")
    print(f"  Dominio: accuracy {dominio['accuracy']:.3f} · F1-macro {dominio['f1_macro']:.3f}")
    print(f"  Área:    accuracy {area['accuracy']:.3f} · F1-macro {area['f1_macro']:.3f}")
    aceptados = revision["accuracy_jerarquica_aceptados"]
    print(
        f"  Requieren revisión: {revision['porcentaje_revision']:.0%}"
        + (f" · accuracy en los aceptados {aceptados:.3f}" if aceptados is not None else "")
    )
    for nombre, valores in metricas["por_dominio"].items():
        print(
            f"  {nombre}: dominio {valores['accuracy_dominio']:.0%} · "
            f"área {valores['accuracy_area']:.0%} ({valores['articulos']} artículos)"
        )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Evaluación con artículos externos (Fase V).")
    comandos = parser.add_subparsers(dest="comando", required=True)

    bajar = comandos.add_parser("descargar", help="Buscar candidatos en arXiv y PubMed")
    bajar.add_argument("--destino", type=Path, default=ARCHIVO_ARTICULOS)
    bajar.add_argument("--por-area", type=int, default=2)
    bajar.add_argument(
        "--sobrescribir", action="store_true", help="Reemplazar un Excel ya revisado"
    )

    medir = comandos.add_parser("evaluar", help="Clasificar los artículos revisados")
    medir.add_argument("--articulos", type=Path, default=ARCHIVO_ARTICULOS)
    medir.add_argument("--modelos", type=Path, default=MODELOS)
    medir.add_argument("--categorias", type=Path, default=DATOS_PROCESADOS / "categorias.json")

    args = parser.parse_args(argv)
    if args.comando == "descargar":
        if args.destino.exists() and not args.sobrescribir:
            parser.error(
                f"{args.destino} ya existe y puede tener tu revisión. "
                "Usa --sobrescribir para reemplazarlo."
            )
        tabla = descargar(por_area=args.por_area)
        guardar_articulos(tabla, args.destino)
        incluidos = int((tabla["incluir"] == "si").sum())
        print(f"\n{len(tabla)} artículos ({incluidos} incluidos) en {args.destino}")
        return

    from clasificador_ml.artefactos import cargar_activo

    categorias = json.loads(args.categorias.read_text(encoding="utf-8"))
    articulos = cargar_revision(args.articulos, categorias)
    sin_revisar = int((articulos["revisado"].str.strip().str.lower() != "si").sum())
    if sin_revisar:
        print(f"Aviso: {sin_revisar} artículo(s) incluidos sin revisado = si.")
    modelo, info = cargar_activo(args.modelos)
    tabla, metricas = evaluar_externos(articulos, modelo, categorias)
    metricas["modelo"] = {"algoritmo": info["algoritmo"], "version": info["version"]}

    carpeta = args.articulos.parent
    tabla.to_excel(carpeta / "evaluacion.xlsx", index=False)
    guardar_json(metricas, carpeta / "metricas.json")
    _imprimir(metricas)
    print(f"\nDetalle en {carpeta / 'evaluacion.xlsx'} y {carpeta / 'metricas.json'}")


if __name__ == "__main__":
    main()
