"""GET /clasificaciones, GET /clasificaciones/{id} y POST /clasificaciones/{id}/correccion."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.db.modelos import Clasificacion, Correccion
from tests.api.conftest import ModeloFalso, crear_servicio
from tests.extraccion.conftest import ARTICULO, RESUMEN_EN, crear_pdf

URL = "/api/v1/clasificaciones"


def clasificar(cliente, texto=RESUMEN_EN, titulo=None):
    return cliente.post(f"{URL}/texto", json={"titulo": titulo, "texto": texto}).json()


def otro_texto(n):
    return f"{RESUMEN_EN} Variant number {n}."


def error(respuesta):
    return respuesta.status_code, respuesta.json()["error"]["codigo"]


def cambiar_fecha(fabrica_sesiones, clasificacion_id, fecha):
    with fabrica_sesiones() as sesion:
        sesion.get(Clasificacion, clasificacion_id).creado_en = fecha
        sesion.commit()


# --- Historial ----------------------------------------------------------------------------


def test_historial_vacio(cliente):
    assert cliente.get(URL).json() == {
        "elementos": [],
        "total": 0,
        "pagina": 1,
        "tamano": 20,
        "paginas": 1,
    }


def test_historial_lista_de_la_mas_reciente_a_la_mas_antigua(cliente):
    ids = [clasificar(cliente, otro_texto(i), titulo=f"Artículo {i}")["id"] for i in range(3)]

    datos = cliente.get(URL).json()

    assert [e["id"] for e in datos["elementos"]] == ids[::-1]
    fila = datos["elementos"][0]
    assert fila["documento"] == {"titulo": "Artículo 2", "nombre_archivo": None, "tipo": "texto"}
    assert fila["dominio"] == "Computer Science"
    assert fila["area"] == "Computer vision"
    assert fila["confianza_dominio"] == pytest.approx(0.9)
    assert fila["confianza_conjunta"] == pytest.approx(0.72)
    assert fila["requiere_revision"] is False
    assert fila["correccion"] is None


def test_historial_paginado(cliente):
    for i in range(5):
        clasificar(cliente, otro_texto(i))

    datos = cliente.get(URL, params={"pagina": 2, "tamano": 2}).json()

    assert datos["total"] == 5
    assert datos["paginas"] == 3
    assert [e["id"] for e in datos["elementos"]] == [3, 2]
    assert cliente.get(URL, params={"pagina": 9, "tamano": 2}).json()["elementos"] == []


def test_historial_filtra_por_dominio_y_revision(cliente, aplicacion):
    clasificar(cliente, otro_texto(1))
    aplicacion.state.servicio = crear_servicio(ModeloFalso(confianza_dominio=0.5))
    dudosa = clasificar(cliente, otro_texto(2))

    revision = cliente.get(URL, params={"requiere_revision": "true"}).json()
    assert [e["id"] for e in revision["elementos"]] == [dudosa["id"]]
    assert cliente.get(URL, params={"requiere_revision": "false"}).json()["total"] == 1
    assert cliente.get(URL, params={"dominio": "Computer Science"}).json()["total"] == 2
    assert cliente.get(URL, params={"dominio": "Psychology"}).json()["total"] == 0


def test_historial_filtra_por_fechas(cliente, fabrica_sesiones):
    vieja = clasificar(cliente, otro_texto(1))["id"]
    nueva = clasificar(cliente, otro_texto(2))["id"]
    cambiar_fecha(fabrica_sesiones, vieja, datetime(2026, 1, 15, 10, 0))
    cambiar_fecha(fabrica_sesiones, nueva, datetime(2026, 3, 1, 23, 30))

    def ids(**params):
        return [e["id"] for e in cliente.get(URL, params=params).json()["elementos"]]

    assert ids(desde="2026-02-01") == [nueva]
    assert ids(hasta="2026-02-01") == [vieja]
    # `hasta` sin hora incluye todo ese día.
    assert ids(desde="2026-03-01", hasta="2026-03-01") == [nueva]
    assert ids(desde="2026-01-15T11:00:00") == [nueva]


def test_historial_busca_en_titulo_y_nombre_de_archivo(cliente):
    clasificar(cliente, otro_texto(1), titulo="Redes neuronales ligeras")
    cliente.post(f"{URL}/archivo", files={"archivo": ("tesis_final.pdf", crear_pdf(ARTICULO))})

    def titulos(busqueda):
        datos = cliente.get(URL, params={"busqueda": busqueda}).json()
        return [e["documento"]["titulo"] for e in datos["elementos"]]

    assert titulos("NEURONALES") == ["Redes neuronales ligeras"]
    assert titulos("tesis") == ["A Lightweight Network for Image Recognition"]


@pytest.mark.parametrize(
    ("params", "texto"),
    [
        ({"pagina": 0}, "pagina: debe ser mayor o igual que 1"),
        ({"tamano": 101}, "tamano: debe ser menor o igual que 100"),
        ({"desde": "ayer"}, "desde: debe ser una fecha"),
        ({"requiere_revision": "quizas"}, "requiere_revision: debe ser true o false"),
        ({"desde": "2026-12-01", "hasta": "2026-11-01"}, "no puede ser posterior"),
    ],
)
def test_historial_parametros_invalidos(cliente, params, texto):
    respuesta = cliente.get(URL, params=params)
    assert error(respuesta) == (400, "ENTRADA_INVALIDA")
    assert texto in respuesta.json()["error"]["mensaje"]


def test_historial_no_necesita_el_modelo(cliente, aplicacion):
    clasificar(cliente)
    aplicacion.state.servicio = None
    assert cliente.get(URL).json()["total"] == 1


# --- Detalle ------------------------------------------------------------------------------


def test_detalle_incluye_el_texto_extraido(cliente):
    creada = clasificar(cliente, titulo="Una red ligera")

    respuesta = cliente.get(f"{URL}/{creada['id']}")

    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["documento"]["texto_extraido"] == RESUMEN_EN
    assert datos["documento"]["tipo"] == "texto"
    assert datos["documento"]["palabras_clave"] == []
    # El resto coincide con lo que respondió la clasificación.
    sin_documento = {k: v for k, v in datos.items() if k != "documento"}
    assert sin_documento == {k: v for k, v in creada.items() if k != "documento"}


def test_detalle_de_un_pdf_trae_sus_palabras_clave(cliente):
    creada = cliente.post(
        f"{URL}/archivo", files={"archivo": ("a.pdf", crear_pdf(ARTICULO))}
    ).json()
    palabras = cliente.get(f"{URL}/{creada['id']}").json()["documento"]["palabras_clave"]
    assert "deep learning" in palabras


def test_detalle_inexistente_responde_404(cliente):
    respuesta = cliente.get(f"{URL}/999")
    assert error(respuesta) == (404, "NO_ENCONTRADO")
    assert "999" in respuesta.json()["error"]["mensaje"]


def test_detalle_con_id_no_numerico_responde_400(cliente):
    assert error(cliente.get(f"{URL}/abc")) == (400, "ENTRADA_INVALIDA")


# --- Correcciones -------------------------------------------------------------------------


def corregir(cliente, clasificacion_id, **cuerpo):
    return cliente.post(f"{URL}/{clasificacion_id}/correccion", json=cuerpo)


def test_guarda_la_correccion(cliente, fabrica_sesiones):
    creada = clasificar(cliente)

    respuesta = corregir(
        cliente,
        creada["id"],
        dominio_correcto="Medical Sciences",
        area_correcta="Cancer",
        comentario="Es un artículo de oncología.",
    )

    assert respuesta.status_code == 200
    correccion = respuesta.json()["correccion"]
    assert correccion["dominio_correcto"] == "Medical Sciences"
    assert correccion["area_correcta"] == "Cancer"
    assert correccion["comentario"] == "Es un artículo de oncología."
    # La predicción original no cambia.
    assert respuesta.json()["dominio"]["nombre"] == "Computer Science"
    assert cliente.get(f"{URL}/{creada['id']}").json()["correccion"] == correccion
    fila = cliente.get(URL).json()["elementos"][0]
    assert fila["correccion"]["dominio_correcto"] == "Medical Sciences"


def test_el_area_es_opcional(cliente):
    creada = clasificar(cliente)
    respuesta = corregir(cliente, creada["id"], dominio_correcto="Medical Sciences")
    assert respuesta.status_code == 200
    assert respuesta.json()["correccion"]["area_correcta"] is None


def test_una_nueva_correccion_reemplaza_la_anterior(cliente, fabrica_sesiones):
    creada = clasificar(cliente)
    corregir(cliente, creada["id"], dominio_correcto="Medical Sciences", area_correcta="Cancer")
    ultima = corregir(
        cliente, creada["id"], dominio_correcto="Computer Science", area_correcta="Machine learning"
    ).json()

    assert ultima["correccion"]["area_correcta"] == "Machine learning"
    with fabrica_sesiones() as sesion:
        assert len(sesion.scalars(select(Correccion)).all()) == 1


@pytest.mark.parametrize(
    ("cuerpo", "texto"),
    [
        ({"dominio_correcto": "Astrología"}, "El dominio «Astrología» no existe."),
        (
            {"dominio_correcto": "Medical Sciences", "area_correcta": "Computer vision"},
            "no pertenece al dominio «Medical Sciences»",
        ),
        ({}, "dominio_correcto: es obligatorio"),
        ({"dominio_correcto": ""}, "dominio_correcto: no puede estar vacío"),
    ],
)
def test_correccion_invalida_responde_400(cliente, fabrica_sesiones, cuerpo, texto):
    creada = clasificar(cliente)
    respuesta = corregir(cliente, creada["id"], **cuerpo)
    assert error(respuesta) == (400, "ENTRADA_INVALIDA")
    assert texto in respuesta.json()["error"]["mensaje"]
    with fabrica_sesiones() as sesion:
        assert sesion.scalars(select(Correccion)).all() == []


def test_correccion_de_clasificacion_inexistente_responde_404(cliente):
    respuesta = corregir(cliente, 999, dominio_correcto="Computer Science")
    assert error(respuesta) == (404, "NO_ENCONTRADO")


def test_sin_catalogo_acepta_cualquier_nombre(cliente, aplicacion):
    creada = clasificar(cliente)
    aplicacion.state.catalogo = None
    respuesta = corregir(cliente, creada["id"], dominio_correcto="Otro dominio")
    assert respuesta.status_code == 200


def test_correccion_reciente_tiene_fecha(cliente):
    creada = clasificar(cliente)
    datos = corregir(cliente, creada["id"], dominio_correcto="Computer Science").json()
    fecha = datetime.fromisoformat(datos["correccion"]["creado_en"])
    assert datetime.now() - fecha < timedelta(days=2)


def test_json_mal_formado_responde_400(cliente):
    creada = clasificar(cliente)
    respuesta = cliente.post(
        f"{URL}/{creada['id']}/correccion",
        content=b"{malo",
        headers={"content-type": "application/json"},
    )
    assert error(respuesta) == (400, "ENTRADA_INVALIDA")
    assert respuesta.json()["error"]["mensaje"] == "Entrada inválida. el JSON está mal formado"
