"""GET /api/v1/salud: comprueba que la API está activa y qué modelo tiene cargado."""

from fastapi import APIRouter, Request

from app import __version__
from app.schemas.salud import RespuestaSalud

router = APIRouter()


@router.get("/salud", response_model=RespuestaSalud, summary="Estado de la API")
def obtener_salud(request: Request) -> RespuestaSalud:
    servicio = getattr(request.app.state, "servicio", None)
    modelo = f"{servicio.nombre} {servicio.version}" if servicio is not None else None
    return RespuestaSalud(estado="activo", version=__version__, modelo_activo=modelo)
