"""Aísla todas las pruebas de la base de datos y de la carpeta `models/` reales."""

import pytest
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.sesion import crear_motor, crear_tablas


@pytest.fixture(autouse=True)
def aislar_recursos(monkeypatch, tmp_path):
    """La API usa una base en memoria y una carpeta de modelos vacía.

    Las pruebas que necesitan otra cosa la cambian con su propio `monkeypatch`.
    """
    motor = crear_motor("sqlite://")
    crear_tablas(motor)
    fabrica = sessionmaker(bind=motor, autoflush=False, expire_on_commit=False)
    # El arranque (`app.main`) y los endpoints (`obtener_sesion`) usan la misma base temporal.
    monkeypatch.setattr("app.main.SesionLocal", fabrica)
    monkeypatch.setattr("app.db.sesion.SesionLocal", fabrica)
    monkeypatch.setattr(settings, "ruta_modelos", tmp_path / "models-vacio")
    yield
    motor.dispose()
