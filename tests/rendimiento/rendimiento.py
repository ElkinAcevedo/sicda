"""Prueba de rendimiento de la API (RNF-01, plan de pruebas de la sección 11 del diseño).

Hace 50 clasificaciones seguidas de resúmenes pegados y 50 de PDF de 20 páginas contra una API
que ya esté corriendo, y comprueba que el percentil 95 del tiempo de respuesta quede por debajo
de 2 s para el texto y de 5 s para el PDF.

Uso (con la API levantada en otra terminal)::

    python tests/rendimiento/rendimiento.py                       # API en localhost:8000
    python tests/rendimiento/rendimiento.py --url http://localhost:8080   # Docker
    python tests/rendimiento/rendimiento.py --salida resultados.json

Los resúmenes salen de `data/processed/test.parquet` (WOS real). El tiempo se mide desde el
cliente: incluye la red local, la extracción, el modelo y el guardado en la base.
"""

from __future__ import annotations

import argparse
import json
import platform
import random
import statistics
import sys
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import httpx
import pymupdf

RAIZ = Path(__file__).resolve().parents[2]
DATOS = RAIZ / "data" / "processed" / "test.parquet"

REPETICIONES = 50
PAGINAS_PDF = 20
# Metas de RNF-01, en segundos.
LIMITES = {"texto": 2.0, "pdf": 5.0}
SEMILLA = 42


@dataclass
class Resumen:
    """Estadísticas de una serie de clasificaciones, en milisegundos."""

    tipo: str
    n: int
    minimo: float
    media: float
    mediana: float
    p95: float
    maximo: float
    servidor_p95: float  # `tiempo_ms` que informa la API (sin red ni serialización)
    limite: float
    cumple: bool


def percentil(valores: Sequence[float], q: float) -> float:
    """Percentil `q` (0-100) con interpolación lineal, igual que `numpy.percentile`."""
    if not valores:
        raise ValueError("No hay valores.")
    ordenados = sorted(valores)
    if len(ordenados) == 1:
        return ordenados[0]
    posicion = (len(ordenados) - 1) * q / 100
    abajo = int(posicion)
    arriba = min(abajo + 1, len(ordenados) - 1)
    return ordenados[abajo] + (ordenados[arriba] - ordenados[abajo]) * (posicion - abajo)


def resumir(tipo: str, cliente_ms: list[float], servidor_ms: list[float]) -> Resumen:
    limite = LIMITES[tipo] * 1000
    p95 = percentil(cliente_ms, 95)
    return Resumen(
        tipo=tipo,
        n=len(cliente_ms),
        minimo=min(cliente_ms),
        media=statistics.fmean(cliente_ms),
        mediana=percentil(cliente_ms, 50),
        p95=p95,
        maximo=max(cliente_ms),
        servidor_p95=percentil(servidor_ms, 95),
        limite=limite,
        cumple=p95 < limite,
    )


def cargar_resumenes(n: int, ruta: Path = DATOS, semilla: int = SEMILLA) -> list[str]:
    """`n` resúmenes distintos del conjunto de prueba, elegidos al azar con semilla fija."""
    import pandas as pd

    if not ruta.exists():
        raise FileNotFoundError(
            f"No existe {ruta}. Genere las particiones con `python -m clasificador_ml.datos`."
        )
    textos = pd.read_parquet(ruta, columns=["texto"])["texto"]
    textos = textos[textos.str.split().str.len() >= 50]
    if len(textos) < n:
        raise ValueError(f"Hacen falta {n} resúmenes de al menos 50 palabras y hay {len(textos)}.")
    return textos.sample(n=n, random_state=semilla).tolist()


def crear_pdf(titulo: str, resumen: str, relleno: list[str], paginas: int = PAGINAS_PDF) -> bytes:
    """PDF de `paginas` páginas con forma de artículo: título, Abstract, Keywords y cuerpo.

    El cuerpo se llena con otros resúmenes para que cada página tenga texto real que la API
    tenga que leer (unas 350 palabras por página).
    """
    documento = pymupdf.open()
    marco = pymupdf.Rect(50, 50, 550, 800)
    cuerpo = " ".join(relleno).split()
    por_pagina = 350
    for numero in range(paginas):
        # Se recorre el cuerpo de forma circular: siempre alcanza para todas las páginas.
        inicio = numero * por_pagina
        trozo = " ".join(cuerpo[(inicio + k) % len(cuerpo)] for k in range(por_pagina))
        if numero == 0:
            texto = (
                f"{titulo}\n\nAbstract\n{resumen}\n\n"
                f"Keywords: classification, evaluation\n\n1. Introduction\n{trozo}"
            )
        else:
            texto = f"{numero + 1}. Section\n{trozo}"
        documento.new_page().insert_textbox(marco, texto, fontsize=9)
    contenido = documento.tobytes()
    documento.close()
    return contenido


def _medir(peticion) -> tuple[float, float]:
    inicio = time.perf_counter()
    respuesta = peticion()
    transcurrido = (time.perf_counter() - inicio) * 1000
    if respuesta.status_code != 201:
        raise RuntimeError(f"La API respondió {respuesta.status_code}: {respuesta.text[:300]}")
    return transcurrido, float(respuesta.json()["tiempo_ms"])


def medir_texto(cliente: httpx.Client, resumenes: list[str]) -> tuple[list[float], list[float]]:
    cliente_ms, servidor_ms = [], []
    for i, resumen in enumerate(resumenes, start=1):
        cuerpo = {"titulo": f"Prueba de rendimiento {i}", "texto": resumen}
        total, servidor = _medir(
            lambda c=cuerpo: cliente.post("/api/v1/clasificaciones/texto", json=c)
        )
        cliente_ms.append(total)
        servidor_ms.append(servidor)
    return cliente_ms, servidor_ms


def medir_pdf(cliente: httpx.Client, pdfs: list[bytes]) -> tuple[list[float], list[float]]:
    cliente_ms, servidor_ms = [], []
    for i, contenido in enumerate(pdfs, start=1):
        archivos = {"archivo": (f"rendimiento-{i:02d}.pdf", contenido, "application/pdf")}
        total, servidor = _medir(
            lambda a=archivos: cliente.post("/api/v1/clasificaciones/archivo", files=a)
        )
        cliente_ms.append(total)
        servidor_ms.append(servidor)
    return cliente_ms, servidor_ms


def ejecutar(
    cliente: httpx.Client, resumenes: list[str], repeticiones: int = REPETICIONES
) -> list[Resumen]:
    """Mide `repeticiones` textos y `repeticiones` PDF, después de un calentamiento de cada uno.

    `resumenes` necesita `repeticiones + 1` elementos: el primero es para calentar. Así la
    primera petición, que es más lenta (conexión, cachés de spaCy), no ensucia la medición.
    """
    if len(resumenes) < repeticiones + 1:
        raise ValueError(f"Hacen falta {repeticiones + 1} resúmenes.")
    calentamiento, *medidos = resumenes[: repeticiones + 1]
    relleno = random.Random(SEMILLA).sample(resumenes, k=min(len(resumenes), 30))
    pdfs = [
        crear_pdf(f"Performance test document {i}", resumen, relleno)
        for i, resumen in enumerate(resumenes[: repeticiones + 1])
    ]

    medir_texto(cliente, [calentamiento])
    medir_pdf(cliente, pdfs[:1])
    return [
        resumir("texto", *medir_texto(cliente, medidos)),
        resumir("pdf", *medir_pdf(cliente, pdfs[1:])),
    ]


def informe(resultados: list[Resumen]) -> str:
    filas = [
        "| Entrada | n | Mín. | Media | Mediana | p95 | Máx. | p95 servidor | Meta | ¿Cumple? |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in resultados:
        nombre = "Texto pegado" if r.tipo == "texto" else f"PDF de {PAGINAS_PDF} páginas"
        filas.append(
            f"| {nombre} | {r.n} | {r.minimo:.0f} ms | {r.media:.0f} ms | {r.mediana:.0f} ms | "
            f"**{r.p95:.0f} ms** | {r.maximo:.0f} ms | {r.servidor_p95:.0f} ms | "
            f"< {r.limite / 1000:g} s | {'✅' if r.cumple else '❌'} |"
        )
    return "\n".join(filas)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prueba de rendimiento de la API (RNF-01).")
    parser.add_argument("--url", default="http://localhost:8000", help="URL base de la API")
    parser.add_argument("--repeticiones", type=int, default=REPETICIONES)
    parser.add_argument("--datos", type=Path, default=DATOS, help="Parquet con la columna texto")
    parser.add_argument("--salida", type=Path, help="Guardar los resultados en JSON")
    args = parser.parse_args(argv)

    resumenes = cargar_resumenes(args.repeticiones + 1, args.datos)
    with httpx.Client(base_url=args.url, timeout=60) as cliente:
        salud = cliente.get("/api/v1/salud")
        salud.raise_for_status()
        print(f"API en {args.url}: {salud.json()}")
        print(f"Midiendo {args.repeticiones} textos y {args.repeticiones} PDF…")
        resultados = ejecutar(cliente, resumenes, args.repeticiones)

    print()
    print(informe(resultados))
    if args.salida:
        args.salida.write_text(
            json.dumps(
                {
                    "fecha": datetime.now().isoformat(timespec="seconds"),
                    "url": args.url,
                    "equipo": {"sistema": platform.platform(), "python": platform.python_version()},
                    "resultados": [asdict(r) for r in resultados],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"\nResultados guardados en {args.salida}")
    return 0 if all(r.cumple for r in resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
