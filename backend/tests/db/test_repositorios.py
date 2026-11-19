from datetime import UTC, date, datetime, timedelta, timezone

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from app.db import repositorios as repo
from app.db.modelos import Clasificacion, Correccion, Modelo
from app.db.sesion import crear_motor, crear_tablas
from tests.db.conftest import crear_clasificacion, crear_documento

# --- Esquema ------------------------------------------------------------------------------


def test_crear_tablas_crea_las_cuatro_tablas_del_diseno():
    motor = crear_motor("sqlite://")
    crear_tablas(motor)
    tablas = set(inspect(motor).get_table_names())
    assert {"documento", "clasificacion", "correccion", "modelo"} <= tablas


def test_crear_motor_crea_la_carpeta_del_archivo(tmp_path):
    ruta = tmp_path / "datos" / "sicda.db"
    motor = crear_motor(f"sqlite:///{ruta}")
    crear_tablas(motor)
    assert ruta.is_file()
    motor.dispose()


def test_claves_foraneas_activas(sesion, modelo):
    sesion.add(
        Clasificacion(
            documento_id=999,
            modelo_id=modelo.id,
            dominio="CS",
            conf_dominio=0.9,
            area="X",
            conf_area=0.9,
            conf_conjunta=0.81,
            requiere_revision=False,
            tiempo_ms=1,
        )
    )
    with pytest.raises(IntegrityError):
        sesion.flush()


# --- Documentos ---------------------------------------------------------------------------


def test_calcular_hash_normaliza_espacios_del_texto():
    assert repo.calcular_hash("hola   mundo\n") == repo.calcular_hash("hola mundo")
    assert repo.calcular_hash(b"hola") != repo.calcular_hash(b"hola ")
    assert len(repo.calcular_hash(b"x")) == 64


def test_obtener_o_crear_documento_no_duplica_por_hash(sesion):
    primero = crear_documento(sesion)
    segundo = crear_documento(sesion, titulo="Otro título")
    assert primero.id == segundo.id
    assert segundo.titulo == "Un artículo"
    assert repo.buscar_documento_por_hash(sesion, primero.hash_sha256) is primero


def test_documento_guarda_palabras_clave_como_json(sesion):
    documento = crear_documento(sesion, palabras_clave=["deep learning", "images"])
    sesion.commit()
    sesion.expire_all()
    assert repo.buscar_documento_por_hash(sesion, documento.hash_sha256).palabras_clave == [
        "deep learning",
        "images",
    ]


# --- Modelos ------------------------------------------------------------------------------


def test_registrar_modelo_actualiza_si_ya_existe(sesion, modelo):
    otro = repo.registrar_modelo(
        sesion,
        nombre="SVM calibrado",
        algoritmo="svm",
        version="v1",
        ruta_artefacto="svm/v1/jerarquico.joblib",
    )
    assert otro.id == modelo.id
    assert otro.nombre == "SVM calibrado"
    assert len(repo.listar_modelos(sesion)) == 1


def test_solo_un_modelo_activo(sesion, modelo):
    nb = repo.registrar_modelo(
        sesion,
        nombre="NB",
        algoritmo="naive_bayes",
        version="v1",
        ruta_artefacto="naive_bayes/v1/plano.joblib",
        activar=True,
    )
    sesion.refresh(modelo)
    assert nb.activo and not modelo.activo
    assert repo.obtener_modelo_activo(sesion).id == nb.id

    repo.activar_modelo(sesion, modelo.id)
    sesion.refresh(nb)
    assert repo.obtener_modelo_activo(sesion).id == modelo.id
    assert not nb.activo


def test_la_base_rechaza_dos_modelos_activos(sesion, modelo):
    sesion.add(Modelo(nombre="X", algoritmo="x", version="1", ruta_artefacto="x", activo=True))
    with pytest.raises(IntegrityError):
        sesion.flush()


def test_sin_modelo_activo_devuelve_none(sesion):
    assert repo.obtener_modelo_activo(sesion) is None


def test_listar_modelos_pone_primero_el_activo(sesion, modelo):
    repo.registrar_modelo(
        sesion, nombre="NB", algoritmo="naive_bayes", version="v2", ruta_artefacto="nb"
    )
    assert [m.id for m in repo.listar_modelos(sesion)][0] == modelo.id


def test_obtener_modelo_inexistente(sesion):
    with pytest.raises(repo.NoEncontrado):
        repo.obtener_modelo(sesion, 42)


# --- Clasificaciones ----------------------------------------------------------------------


def test_guardar_y_obtener_clasificacion(sesion, modelo):
    documento = crear_documento(sesion)
    guardada = crear_clasificacion(sesion, documento, modelo)
    sesion.commit()
    sesion.expire_all()

    leida = repo.obtener_clasificacion(sesion, guardada.id)
    assert leida.documento.titulo == "Un artículo"
    assert leida.modelo.version == "v1"
    assert leida.alternativas["dominio"][0]["nombre"] == "CS"
    assert leida.terminos_clave == [{"termino": "network", "peso": 0.3}]
    assert leida.correccion is None
    assert leida.creado_en is not None


def test_obtener_clasificacion_inexistente(sesion):
    with pytest.raises(repo.NoEncontrado):
        repo.obtener_clasificacion(sesion, 1)


def test_un_documento_puede_tener_varias_clasificaciones(sesion, modelo):
    documento = crear_documento(sesion)
    crear_clasificacion(sesion, documento, modelo)
    crear_clasificacion(sesion, documento, modelo)
    sesion.refresh(documento)
    assert len(documento.clasificaciones) == 2


@pytest.fixture
def historial(sesion, modelo):
    """Cinco clasificaciones con fechas, dominios y estados distintos."""
    base = datetime(2026, 11, 10, 12, 0)
    datos = [
        ("a.pdf", "Neural networks", "CS", False, base),
        ("b.pdf", "Cancer therapy", "Medical", True, base + timedelta(days=1)),
        ("c.docx", "Graph theory", "CS", True, base + timedelta(days=2)),
        (None, "Protein folding", "Biochemistry", False, base + timedelta(days=3)),
        ("e.txt", None, "CS", False, base + timedelta(days=4)),
    ]
    clasificaciones = []
    for nombre, titulo, dominio, revision, fecha in datos:
        documento = crear_documento(
            sesion, texto=f"texto {nombre} {titulo}", nombre_archivo=nombre, titulo=titulo
        )
        clasificaciones.append(
            crear_clasificacion(
                sesion,
                documento,
                modelo,
                dominio=dominio,
                requiere_revision=revision,
                creado_en=fecha,
            )
        )
    sesion.commit()
    return clasificaciones


def test_listar_ordena_de_la_mas_reciente_a_la_mas_antigua(sesion, historial):
    pagina = repo.listar_clasificaciones(sesion)
    assert pagina.total == 5
    assert [c.id for c in pagina.elementos] == [c.id for c in reversed(historial)]


def test_listar_pagina(sesion, historial):
    pagina = repo.listar_clasificaciones(sesion, pagina=2, tamano=2)
    assert pagina.total == 5
    assert pagina.paginas == 3
    assert [c.id for c in pagina.elementos] == [historial[2].id, historial[1].id]
    assert repo.listar_clasificaciones(sesion, pagina=4, tamano=2).elementos == []


def test_listar_rechaza_pagina_invalida(sesion):
    with pytest.raises(ValueError):
        repo.listar_clasificaciones(sesion, pagina=0)


def test_listar_filtra_por_dominio_y_revision(sesion, historial):
    assert repo.listar_clasificaciones(sesion, dominio="CS").total == 3
    assert repo.listar_clasificaciones(sesion, requiere_revision=True).total == 2
    assert repo.listar_clasificaciones(sesion, requiere_revision=False).total == 3
    ambos = repo.listar_clasificaciones(sesion, dominio="CS", requiere_revision=True)
    assert [c.id for c in ambos.elementos] == [historial[2].id]


def test_listar_filtra_por_fechas_inclusivas(sesion, historial):
    pagina = repo.listar_clasificaciones(sesion, desde=date(2026, 11, 11), hasta=date(2026, 11, 12))
    assert {c.id for c in pagina.elementos} == {historial[1].id, historial[2].id}


def test_listar_convierte_fechas_con_zona_a_utc(sesion, historial):
    bogota = timezone(timedelta(hours=-5))
    # 2026-11-13 07:00 en Bogotá = 12:00 UTC: incluye exactamente la cuarta clasificación.
    pagina = repo.listar_clasificaciones(
        sesion,
        desde=datetime(2026, 11, 13, 7, 0, tzinfo=bogota),
        hasta=datetime(2026, 11, 13, 12, 0, tzinfo=UTC),
    )
    assert [c.id for c in pagina.elementos] == [historial[3].id]


def test_listar_busca_en_titulo_y_nombre_de_archivo(sesion, historial):
    assert [c.id for c in repo.listar_clasificaciones(sesion, busqueda="graph").elementos] == [
        historial[2].id
    ]
    assert [c.id for c in repo.listar_clasificaciones(sesion, busqueda="E.TXT").elementos] == [
        historial[4].id
    ]
    assert repo.listar_clasificaciones(sesion, busqueda="   ").total == 5


def test_ultimas_clasificaciones(sesion, historial):
    ultimas = repo.ultimas_clasificaciones(sesion, cantidad=2)
    assert [c.id for c in ultimas] == [historial[4].id, historial[3].id]


# --- Correcciones -------------------------------------------------------------------------


def test_guardar_correccion(sesion, modelo):
    clasificacion = crear_clasificacion(sesion, crear_documento(sesion), modelo)
    correccion = repo.guardar_correccion(
        sesion,
        clasificacion.id,
        dominio_correcto="ECE",
        area_correcta="Signal processing",
        comentario="Es de procesamiento de señales.",
    )
    sesion.commit()
    sesion.expire_all()
    leida = repo.obtener_clasificacion(sesion, clasificacion.id)
    assert leida.correccion.id == correccion.id
    assert leida.correccion.dominio_correcto == "ECE"


def test_una_segunda_correccion_reemplaza_la_primera(sesion, modelo):
    clasificacion = crear_clasificacion(sesion, crear_documento(sesion), modelo)
    repo.guardar_correccion(sesion, clasificacion.id, dominio_correcto="ECE")
    repo.guardar_correccion(sesion, clasificacion.id, dominio_correcto="Civil")
    sesion.commit()
    correcciones = sesion.query(Correccion).all()
    assert len(correcciones) == 1
    assert correcciones[0].dominio_correcto == "Civil"
    assert correcciones[0].area_correcta is None


def test_corregir_clasificacion_inexistente(sesion):
    with pytest.raises(repo.NoEncontrado):
        repo.guardar_correccion(sesion, 7, dominio_correcto="CS")


def test_borrar_documento_borra_sus_clasificaciones_y_correcciones(sesion, modelo):
    documento = crear_documento(sesion)
    clasificacion = crear_clasificacion(sesion, documento, modelo)
    repo.guardar_correccion(sesion, clasificacion.id, dominio_correcto="ECE")
    sesion.commit()
    sesion.delete(documento)
    sesion.commit()
    assert sesion.query(Clasificacion).count() == 0
    assert sesion.query(Correccion).count() == 0
