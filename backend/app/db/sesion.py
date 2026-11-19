"""Motor de SQLAlchemy, fábrica de sesiones y dependencia de FastAPI."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings


def crear_motor(url: str) -> Engine:
    """Crea el motor. En SQLite activa las claves foráneas y crea la carpeta del archivo.

    `sqlite://` (en memoria) usa una sola conexión compartida, para que todas las sesiones
    vean las mismas tablas; se usa en las pruebas.
    """
    url_obj = make_url(url)
    if url_obj.get_backend_name() != "sqlite":
        return create_engine(url)

    en_memoria = url_obj.database in (None, "", ":memory:")
    if not en_memoria:
        Path(url_obj.database).parent.mkdir(parents=True, exist_ok=True)
    motor = create_engine(
        url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool if en_memoria else None,
    )

    @event.listens_for(motor, "connect")
    def _activar_claves_foraneas(conexion, _registro) -> None:
        cursor = conexion.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return motor


motor = crear_motor(settings.url_base_datos)
SesionLocal = sessionmaker(bind=motor, autoflush=False, expire_on_commit=False)


def crear_tablas(motor_destino: Engine | None = None) -> None:
    """Crea las tablas que falten (no modifica las existentes)."""
    from app.db.modelos import Base

    Base.metadata.create_all(motor_destino or motor)


def obtener_sesion() -> Iterator[Session]:
    """Dependencia de FastAPI: una sesión por solicitud, cerrada al terminar."""
    with SesionLocal() as sesion:
        yield sesion
