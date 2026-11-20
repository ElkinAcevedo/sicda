"""POST /api/v1/clasificaciones/texto y /archivo."""

import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.db.modelos import Clasificacion, Documento, Modelo
from tests.api.conftest import ModeloFalso, crear_servicio
from tests.extraccion.conftest import ARTICULO, RESUMEN_EN, RESUMEN_ES, crear_docx, crear_pdf

URL_TEXTO = "/api/v1/clasificaciones/texto"
URL_ARCHIVO = "/api/v1/clasificaciones/archivo"


def contar(fabrica_sesiones, tabla):
    with fabrica_sesiones() as sesion:
        return sesion.scalar(select(func.count()).select_from(tabla))


# --- Texto pegado -------------------------------------------------------------------------


def test_clasifica_texto_con_el_formato_del_contrato(cliente):
    respuesta = cliente.post(URL_TEXTO, json={"titulo": "Una red ligera", "texto": RESUMEN_EN})

    assert respuesta.status_code == 201
    datos = respuesta.json()
    assert datos["id"] == 1
    assert datos["documento"] == {
        "titulo": "Una red ligera",
        "nombre_archivo": None,
        "idioma": "en",
        "num_terminos": len(RESUMEN_EN.split()),
        "fuente_texto": "texto_completo",
    }
    assert datos["dominio"]["nombre"] == "Computer Science"
    assert datos["dominio"]["confianza"] == pytest.approx(0.9)
    assert [a["nombre"] for a in datos["dominio"]["alternativas"]] == [
        "Computer Science",
        "Medical Sciences",
    ]
    assert datos["area"]["nombre"] == "Computer vision"
    assert datos["area"]["alternativas"][1] == {"nombre": "Machine learning", "confianza": 0.2}
    assert datos["confianza_conjunta"] == pytest.approx(0.72)
    assert datos["requiere_revision"] is False
    assert datos["terminos_clave"] == [{"termino": "convolutional", "peso": 0.3}]
    assert datos["advertencias"] == []
    assert datos["modelo"] == {"nombre": "TF-IDF + SVM lineal (plano)", "version": "v-prueba"}
    assert datos["tiempo_ms"] >= 0


def test_el_modelo_recibe_el_resumen_extraido(cliente, aplicacion):
    cliente.post(URL_TEXTO, json={"texto": f"  {RESUMEN_EN}  "})
    assert aplicacion.state.servicio.modelo.textos == [RESUMEN_EN]


def test_guarda_documento_clasificacion_y_modelo_activo(cliente, fabrica_sesiones):
    cliente.post(URL_TEXTO, json={"texto": RESUMEN_EN})

    with fabrica_sesiones() as sesion:
        clasificacion = sesion.scalars(select(Clasificacion)).one()
        assert clasificacion.dominio == "Computer Science"
        assert clasificacion.documento.tipo == "texto"
        assert clasificacion.documento.texto_extraido == RESUMEN_EN
        assert clasificacion.alternativas["area"][0]["nombre"] == "Computer vision"
        modelo = sesion.scalars(select(Modelo)).one()
        assert modelo.activo and modelo.version == "v-prueba"
        assert modelo.hiperparametros == {"plano": {"clf__C": 1.0}}
        assert modelo.metricas["prueba"]["area"]["f1_macro"] == 0.79


def test_el_mismo_texto_reutiliza_el_documento(cliente, fabrica_sesiones):
    primero = cliente.post(URL_TEXTO, json={"texto": RESUMEN_EN}).json()
    segundo = cliente.post(URL_TEXTO, json={"texto": RESUMEN_EN.replace(" ", "  ")}).json()

    assert segundo["id"] == primero["id"] + 1
    assert contar(fabrica_sesiones, Documento) == 1
    assert contar(fabrica_sesiones, Clasificacion) == 2
    assert contar(fabrica_sesiones, Modelo) == 1


def test_baja_confianza_requiere_revision(aplicacion, cliente):
    aplicacion.state.servicio = crear_servicio(ModeloFalso(confianza_dominio=0.5))
    datos = cliente.post(URL_TEXTO, json={"texto": RESUMEN_EN}).json()
    assert datos["requiere_revision"] is True


def test_texto_en_espanol_devuelve_advertencia(cliente):
    datos = cliente.post(URL_TEXTO, json={"texto": RESUMEN_ES}).json()
    assert [a["codigo"] for a in datos["advertencias"]] == ["IDIOMA_NO_SOPORTADO"]
    assert datos["documento"]["idioma"] == "es"


# --- Archivos -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("nombre", "contenido", "tipo"),
    [
        ("articulo.pdf", crear_pdf(ARTICULO), "pdf"),
        ("articulo.docx", crear_docx(ARTICULO), "docx"),
        ("articulo.txt", ARTICULO.encode("utf-8"), "txt"),
    ],
)
def test_clasifica_archivos(cliente, fabrica_sesiones, aplicacion, nombre, contenido, tipo):
    respuesta = cliente.post(URL_ARCHIVO, files={"archivo": (nombre, contenido)})

    assert respuesta.status_code == 201
    documento = respuesta.json()["documento"]
    assert documento["nombre_archivo"] == nombre
    assert documento["fuente_texto"] == "abstract"
    assert documento["titulo"] == "A Lightweight Network for Image Recognition"
    assert aplicacion.state.servicio.modelo.textos[0].startswith("Convolutional neural networks")
    with fabrica_sesiones() as sesion:
        assert sesion.scalars(select(Documento)).one().tipo == tipo


def test_el_mismo_archivo_reutiliza_el_documento(cliente, fabrica_sesiones):
    contenido = crear_pdf(ARTICULO)
    for _ in range(2):
        cliente.post(URL_ARCHIVO, files={"archivo": ("articulo.pdf", contenido)})
    assert contar(fabrica_sesiones, Documento) == 1
    assert contar(fabrica_sesiones, Clasificacion) == 2


# --- Errores ------------------------------------------------------------------------------


def error(respuesta):
    return respuesta.status_code, respuesta.json()["error"]["codigo"]


def test_sin_modelo_responde_503(aplicacion, cliente, fabrica_sesiones):
    aplicacion.state.servicio = None
    assert error(cliente.post(URL_TEXTO, json={"texto": RESUMEN_EN})) == (
        503,
        "MODELO_NO_DISPONIBLE",
    )
    assert error(cliente.post(URL_ARCHIVO, files={"archivo": ("a.txt", b"x")})) == (
        503,
        "MODELO_NO_DISPONIBLE",
    )
    assert contar(fabrica_sesiones, Documento) == 0


def test_texto_corto_responde_422(cliente, fabrica_sesiones):
    respuesta = cliente.post(URL_TEXTO, json={"texto": "Muy corto"})
    assert error(respuesta) == (422, "TEXTO_INSUFICIENTE")
    assert "al menos 20" in respuesta.json()["error"]["mensaje"]
    assert contar(fabrica_sesiones, Documento) == 0


@pytest.mark.parametrize("cuerpo", [{}, {"texto": ""}, {"texto": 5}, {"titulo": "x" * 501}])
def test_cuerpo_invalido_responde_400(cliente, cuerpo):
    assert error(cliente.post(URL_TEXTO, json=cuerpo)) == (400, "ENTRADA_INVALIDA")


def test_sin_archivo_responde_400(cliente):
    respuesta = cliente.post(URL_ARCHIVO)
    assert error(respuesta) == (400, "ENTRADA_INVALIDA")
    assert "archivo" in respuesta.json()["error"]["mensaje"]


def test_formato_no_soportado_responde_415(cliente):
    respuesta = cliente.post(URL_ARCHIVO, files={"archivo": ("foto.png", b"\x89PNG")})
    assert error(respuesta) == (415, "FORMATO_NO_SOPORTADO")


def test_archivo_muy_grande_responde_413(cliente, monkeypatch):
    monkeypatch.setattr(settings, "tamano_maximo_archivo_mb", 1)
    contenido = b"word " * (1024 * 1024 // 5 + 10)
    respuesta = cliente.post(URL_ARCHIVO, files={"archivo": ("grande.txt", contenido)})
    assert error(respuesta) == (413, "ARCHIVO_MUY_GRANDE")


def test_archivo_danado_responde_422(cliente):
    respuesta = cliente.post(URL_ARCHIVO, files={"archivo": ("roto.pdf", b"no es un pdf")})
    assert error(respuesta) == (422, "ARCHIVO_DANADO")


def test_openapi_documenta_los_endpoints_y_errores(cliente):
    rutas = cliente.get("/openapi.json").json()["paths"]
    assert {"201", "503"} <= set(rutas[URL_TEXTO]["post"]["responses"])
    assert {"201", "413", "415"} <= set(rutas[URL_ARCHIVO]["post"]["responses"])
