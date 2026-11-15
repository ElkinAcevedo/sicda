"""Generadores de documentos de prueba (se crean en memoria, sin archivos binarios en el repo)."""

import io

import docx
import pymupdf
import pytest

RESUMEN_EN = (
    "Convolutional neural networks have become the dominant approach for image recognition. "
    "In this work we propose a lightweight architecture that reduces the number of parameters "
    "while keeping accuracy on standard benchmarks. Experiments on three public datasets show "
    "that the proposed model trains faster and generalizes better than previous baselines."
)

RESUMEN_ES = (
    "Las redes neuronales convolucionales se han convertido en el enfoque dominante para el "
    "reconocimiento de imágenes. En este trabajo proponemos una arquitectura ligera que reduce "
    "el número de parámetros manteniendo la precisión en los conjuntos de referencia."
)

ARTICULO = f"""A Lightweight Network for Image Recognition
John Doe, Jane Roe
University of Somewhere

Abstract
{RESUMEN_EN}

Keywords: deep learning; image recogni-
tion; convolutional networks

1. Introduction
Image recognition is a classic problem in computer vision with many applications.
"""


def crear_pdf(texto: str) -> bytes:
    documento = pymupdf.open()
    pagina = documento.new_page()
    pagina.insert_textbox(pymupdf.Rect(50, 50, 550, 800), texto, fontsize=10)
    contenido = documento.tobytes()
    documento.close()
    return contenido


def crear_docx(texto: str) -> bytes:
    documento = docx.Document()
    for linea in texto.split("\n"):
        documento.add_paragraph(linea)
    salida = io.BytesIO()
    documento.save(salida)
    return salida.getvalue()


@pytest.fixture
def pdf_articulo() -> bytes:
    return crear_pdf(ARTICULO)


@pytest.fixture
def docx_articulo() -> bytes:
    return crear_docx(ARTICULO)
