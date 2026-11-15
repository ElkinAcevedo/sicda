import io

import docx
import pymupdf
import pytest

from app.extraccion import (
    ArchivoDanado,
    ArchivoDemasiadoGrande,
    FormatoNoSoportado,
    OrigenResumen,
    TextoInsuficiente,
    extraer_documento,
    extraer_texto_pegado,
)
from app.extraccion.lectores import limpiar_texto_extraido, quitar_encabezados_y_pies
from app.extraccion.resumen import detectar_titulo, localizar_resumen

from .conftest import ARTICULO, RESUMEN_EN, RESUMEN_ES, crear_docx, crear_pdf


def _codigos(resultado):
    return [a.codigo for a in resultado.advertencias]


# --- Lectura por formato -----------------------------------------------------


@pytest.mark.parametrize(
    "fixture, nombre", [("pdf_articulo", "a.pdf"), ("docx_articulo", "a.DOCX")]
)
def test_extrae_titulo_resumen_y_palabras_clave(request, fixture, nombre):
    resultado = extraer_documento(request.getfixturevalue(fixture), nombre)

    assert resultado.fuente_texto is OrigenResumen.SECCION
    assert resultado.fuente_texto == "abstract"
    assert resultado.titulo == "A Lightweight Network for Image Recognition"
    assert resultado.texto.startswith("Convolutional neural networks")
    assert resultado.texto.endswith("previous baselines.")
    assert resultado.num_terminos == len(RESUMEN_EN.split())
    assert resultado.palabras_clave == [
        "deep learning",
        "image recognition",
        "convolutional networks",
    ]
    assert resultado.idioma == "en"
    assert resultado.advertencias == []
    assert resultado.formato == nombre.split(".")[1].lower()


def test_txt_en_cp1252():
    contenido = ("Résumé del autor\n\n" + ARTICULO).encode("cp1252")

    resultado = extraer_documento(contenido, "articulo.txt")

    assert resultado.texto.startswith("Convolutional neural networks")


def test_titulo_de_los_metadatos_tiene_prioridad():
    documento = pymupdf.open(stream=crear_pdf(ARTICULO), filetype="pdf")
    documento.set_metadata({"title": "Título en metadatos"})

    resultado = extraer_documento(documento.tobytes(), "a.pdf")

    assert resultado.titulo == "Título en metadatos"


def test_docx_ignora_tablas():
    documento = docx.Document(io.BytesIO(crear_docx(ARTICULO)))
    documento.add_table(rows=1, cols=1).cell(0, 0).text = "TEXTO DE TABLA"
    salida = io.BytesIO()
    documento.save(salida)

    resultado = extraer_documento(salida.getvalue(), "a.docx")

    assert "TEXTO DE TABLA" not in resultado.texto


def test_pdf_quita_encabezados_y_pies_repetidos():
    documento = pymupdf.open()
    for numero in range(1, 5):
        pagina = documento.new_page()
        pagina.insert_text((50, 30), "Journal of Testing · Vol. 3")
        cuerpo = f"Abstract\n{RESUMEN_EN}" if numero == 1 else f"Section {numero} text " * 20
        pagina.insert_textbox(pymupdf.Rect(50, 60, 550, 700), cuerpo, fontsize=10)
        pagina.insert_text((50, 800), f"Page {numero} of 4")

    resultado = extraer_documento(documento.tobytes(), "a.pdf")

    assert "Journal of Testing" not in resultado.texto
    assert "Page" not in resultado.texto


def test_quitar_encabezados_conserva_paginas_cortas():
    paginas = ["Solo una página"]

    assert quitar_encabezados_y_pies(paginas) == paginas


# --- Errores (códigos de la sección 7.3 del diseño) --------------------------


def test_formato_no_soportado():
    with pytest.raises(FormatoNoSoportado) as error:
        extraer_documento(b"datos", "foto.png")
    assert (error.value.codigo_http, error.value.codigo) == (415, "FORMATO_NO_SOPORTADO")


def test_archivo_demasiado_grande():
    with pytest.raises(ArchivoDemasiadoGrande) as error:
        extraer_documento(b"x" * 2048, "a.txt", tamano_maximo_mb=0.001)
    assert (error.value.codigo_http, error.value.codigo) == (413, "ARCHIVO_MUY_GRANDE")


def test_pdf_danado():
    with pytest.raises(ArchivoDanado):
        extraer_documento(b"%PDF-1.7 esto no es un pdf", "a.pdf")


def test_extension_pdf_con_otro_contenido():
    with pytest.raises(ArchivoDanado, match="no es un PDF"):
        extraer_documento(crear_docx(ARTICULO), "a.pdf")


def test_docx_danado():
    with pytest.raises(ArchivoDanado):
        extraer_documento(b"PK\x03\x04 roto", "a.docx")


def test_pdf_protegido():
    documento = pymupdf.open()
    documento.new_page().insert_text((50, 50), "secreto")
    contenido = documento.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="clave")

    with pytest.raises(ArchivoDanado, match="contraseña"):
        extraer_documento(contenido, "a.pdf")


def test_pdf_escaneado_sin_texto():
    documento = pymupdf.open()
    documento.new_page()

    with pytest.raises(TextoInsuficiente, match="escaneado") as error:
        extraer_documento(documento.tobytes(), "a.pdf")
    assert (error.value.codigo_http, error.value.codigo) == (422, "TEXTO_INSUFICIENTE")


def test_archivo_vacio():
    with pytest.raises(TextoInsuficiente):
        extraer_documento(b"", "a.txt")


def test_texto_con_pocos_terminos():
    with pytest.raises(TextoInsuficiente, match="al menos 20"):
        extraer_texto_pegado("Deep learning for image recognition.", minimo_terminos=20)


def test_texto_pegado_vacio():
    with pytest.raises(TextoInsuficiente):
        extraer_texto_pegado("   \n ")


# --- Localización del resumen y del título -----------------------------------


def test_encabezado_espaciado_estilo_elsevier():
    texto = f"Title\n\nA B S T R A C T\n{RESUMEN_EN}\n\n© 2020 Elsevier Ltd."

    resumen = localizar_resumen(texto)

    assert resumen.origen is OrigenResumen.SECCION
    assert "Elsevier" not in resumen.texto


def test_resumen_en_la_misma_linea_del_encabezado():
    resumen = localizar_resumen(f"Abstract— {RESUMEN_EN}\nIndex Terms—CNN, vision")

    assert resumen.texto.startswith("Convolutional")
    assert resumen.palabras_clave == ["CNN", "vision"]


def test_prefiere_abstract_en_ingles_sobre_resumen():
    texto = f"Resumen\n{RESUMEN_ES}\n\nAbstract\n{RESUMEN_EN}\n\nIntroducción\nTexto."

    resumen = localizar_resumen(texto)

    assert resumen.texto.startswith("Convolutional")


def test_ignora_entrada_de_indice():
    texto = "Contents\nSummary 3\n\n" + RESUMEN_EN

    assert localizar_resumen(texto).origen is OrigenResumen.COMPLETO


def test_frase_que_empieza_con_summary_no_es_encabezado():
    texto = "Summary statistics were computed for " + RESUMEN_EN

    assert localizar_resumen(texto).origen is OrigenResumen.COMPLETO


def test_encabezado_sin_separador_seguido_de_mayuscula():
    # Formato Springer: "Abstract Convolutional neural networks..."
    resumen = localizar_resumen(f"Title\nAbstract {RESUMEN_EN}\nKeywords CNN")

    assert resumen.origen is OrigenResumen.SECCION
    assert resumen.texto.startswith("Convolutional")


def test_sin_encabezado_usa_los_primeros_300_terminos():
    resultado = extraer_texto_pegado(" ".join([RESUMEN_EN] * 10))

    assert resultado.fuente_texto == "inicio"
    assert resultado.num_terminos == 300
    assert _codigos(resultado) == ["RESUMEN_NO_ENCONTRADO"]


def test_detectar_titulo_salta_lineas_cortas_y_correos():
    texto = f"arXiv 2401\njohn@uni.edu, jane@uni.edu\nA Study of Things\nAbstract\n{RESUMEN_EN}"

    assert detectar_titulo(texto) == "A Study of Things"


# --- Texto pegado y advertencias ---------------------------------------------


def test_texto_pegado_con_titulo():
    resultado = extraer_texto_pegado(RESUMEN_EN, titulo="  Lightweight   CNN ")

    assert resultado.fuente_texto is OrigenResumen.COMPLETO
    assert resultado.formato == "texto"
    assert resultado.titulo == "Lightweight CNN"
    assert resultado.texto == RESUMEN_EN


def test_advierte_idioma_distinto_al_ingles():
    resultado = extraer_texto_pegado(RESUMEN_ES)

    assert resultado.idioma == "es"
    assert _codigos(resultado) == ["IDIOMA_NO_SOPORTADO"]


def test_limpieza_une_guiones_y_espacios():
    texto = "classi-\nfication  of\u00a0text\r\n\n\n\nnext \ufb01eld"

    assert limpiar_texto_extraido(texto) == "classification of text\n\nnext field"
