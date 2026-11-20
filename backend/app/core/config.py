"""Configuración centralizada, leída de variables de entorno o del archivo .env."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Parámetros de la API. Cada campo se puede sobrescribir con CLASIFICADOR_<NOMBRE>."""

    model_config = SettingsConfigDict(env_prefix="CLASIFICADOR_", env_file=".env", extra="ignore")

    entorno: str = "desarrollo"
    url_base_datos: str = "sqlite:///./clasificador.db"
    # Carpeta con `activo.json` y los artefactos. Los umbrales de «requiere revisión» se
    # calibraron en validación y vienen en `activo.json`, no en la configuración.
    ruta_modelos: Path = Path("../models")
    ruta_categorias: Path = Path("../data/processed/categorias.json")
    tamano_maximo_archivo_mb: int = 10
    minimo_terminos: int = 20
    origenes_cors: list[str] = ["http://localhost:5173"]


settings = Settings()
