"""Carga del modelo activo y traducción de sus predicciones al formato de la API.

El modelo se carga **una sola vez** al iniciar la API (sección 5.2 del diseño), a partir de
`models/activo.json`, que publica el notebook 05 con los umbrales calibrados en validación.
El pipeline incluye el `Preprocesador` de `clasificador_ml`, así que recibe el resumen tal
como lo entrega la extracción y lo procesa igual que en el entrenamiento.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from clasificador_ml.artefactos import cargar_activo

logger = logging.getLogger(__name__)

NOMBRES_ALGORITMO = {
    "linear_svc": "TF-IDF + SVM lineal",
    "complement_nb": "TF-IDF + Complement Naive Bayes",
    "distilbert": "DistilBERT",
}

TEXTO_CALENTAMIENTO = (
    "Convolutional neural networks are trained on large image datasets to recognize objects."
)


@dataclass(frozen=True)
class Alternativa:
    nombre: str
    confianza: float


@dataclass(frozen=True)
class Nivel:
    """Predicción de un nivel (dominio o área). La primera alternativa es la elegida."""

    id: int
    nombre: str
    confianza: float
    alternativas: list[Alternativa] = field(default_factory=list)


@dataclass(frozen=True)
class Prediccion:
    dominio: Nivel
    area: Nivel
    confianza_conjunta: float
    requiere_revision: bool
    terminos_clave: list[dict[str, Any]] = field(default_factory=list)


class ServicioClasificacion:
    """Envuelve el modelo activo: recibe un resumen y devuelve dominio, área y confianzas.

    Args:
        modelo: objeto con `predecir_detallado(textos)` (`ClasificadorPlano` o
            `ClasificadorJerarquico` de `clasificador_ml`).
        info: contenido de `models/activo.json` (algoritmo, versión, tipo, umbrales, métricas).
        categorias: contenido de `categorias.json`, para traducir los ids a nombres.
        metadatos: `metadatos.json` de la versión (hiperparámetros y métricas de validación).
    """

    def __init__(
        self,
        modelo: Any,
        info: dict[str, Any],
        categorias: dict[str, Any],
        metadatos: dict[str, Any] | None = None,
    ) -> None:
        self.modelo = modelo
        self.info = info
        self.metadatos = metadatos or {}
        self._dominios = {d["id"]: d["nombre"] for d in categorias["dominios"]}
        self._areas = {a["id"]: a["nombre"] for d in categorias["dominios"] for a in d["areas"]}

    @classmethod
    def desde_directorio(
        cls, ruta_modelos: Path | str, ruta_categorias: Path | str
    ) -> ServicioClasificacion:
        """Carga `activo.json`, el `.joblib` que señala y las categorías."""
        modelo, info = cargar_activo(ruta_modelos)
        categorias = json.loads(Path(ruta_categorias).read_text(encoding="utf-8"))
        ruta_metadatos = Path(ruta_modelos) / Path(info["archivo"]).parent / "metadatos.json"
        metadatos = (
            json.loads(ruta_metadatos.read_text(encoding="utf-8"))
            if ruta_metadatos.is_file()
            else {}
        )
        return cls(modelo, info, categorias, metadatos)

    # --- Identificación del modelo -------------------------------------------------------

    @property
    def algoritmo(self) -> str:
        return self.info["algoritmo"]

    @property
    def version(self) -> str:
        return self.info["version"]

    @property
    def tipo(self) -> str:
        return self.info.get("tipo", "plano")

    @property
    def nombre(self) -> str:
        """Nombre legible, por ejemplo «TF-IDF + SVM lineal (plano)»."""
        return f"{NOMBRES_ALGORITMO.get(self.algoritmo, self.algoritmo)} ({self.tipo})"

    @property
    def ruta_artefacto(self) -> str:
        return self.info["archivo"]

    @property
    def hiperparametros(self) -> dict[str, Any]:
        """Mejores hiperparámetros de cada submodelo (de `metadatos.json`)."""
        submodelos = self.metadatos.get("tipos", {}).get(self.tipo, {}).get("submodelos", {})
        return {
            nombre: datos.get("mejores_parametros", {}) for nombre, datos in submodelos.items()
        } or dict(self.metadatos.get("configuracion", {}))

    @property
    def metricas(self) -> dict[str, Any]:
        """Métricas de validación y de prueba, más los umbrales con que se publicó."""
        tipo = self.metadatos.get("tipos", {}).get(self.tipo, {})
        validacion = tipo.get("metricas_validacion") or self.metadatos.get("metricas_validacion")
        return {
            "validacion": validacion,
            "prueba": self.info.get("metricas_prueba"),
            "umbrales": self.info.get("umbrales", {}),
        }

    @property
    def entrenado_en(self) -> datetime | None:
        fecha = self.metadatos.get("fecha")
        return datetime.fromisoformat(fecha) if fecha else None

    # --- Predicción ----------------------------------------------------------------------

    def clasificar(self, texto: str) -> Prediccion:
        """Clasifica un resumen. Los umbrales de revisión son los de `activo.json`."""
        resultado = self.modelo.predecir_detallado([texto])[0]
        return Prediccion(
            dominio=self._nivel(resultado["dominio"], self._dominios),
            area=self._nivel(resultado["area"], self._areas),
            confianza_conjunta=float(resultado["confianza_conjunta"]),
            requiere_revision=bool(resultado["requiere_revision"]),
            terminos_clave=list(resultado.get("terminos_clave", [])),
        )

    @staticmethod
    def _nivel(datos: dict[str, Any], nombres: dict[int, str]) -> Nivel:
        def nombre(identificador: int) -> str:
            return nombres.get(int(identificador), str(identificador))

        return Nivel(
            id=int(datos["id"]),
            nombre=nombre(datos["id"]),
            confianza=float(datos["confianza"]),
            alternativas=[
                Alternativa(nombre(a["id"]), float(a["confianza"]))
                for a in datos.get("alternativas", [])
            ],
        )


def cargar_servicio(
    ruta_modelos: Path | str, ruta_categorias: Path | str
) -> ServicioClasificacion | None:
    """Intenta cargar el modelo activo. Si falla, la API arranca igual y responde 503."""
    try:
        servicio = ServicioClasificacion.desde_directorio(ruta_modelos, ruta_categorias)
    except Exception:  # cualquier fallo (archivo ausente, joblib incompatible) deja la API viva
        logger.exception("No se pudo cargar el modelo activo desde %s", ruta_modelos)
        return None
    try:
        # La primera predicción carga spaCy; se hace aquí para que no la pague un usuario.
        servicio.clasificar(TEXTO_CALENTAMIENTO)
    except Exception:
        logger.exception("El modelo activo no pudo clasificar el texto de prueba")
        return None
    logger.info("Modelo activo cargado: %s %s", servicio.nombre, servicio.version)
    return servicio
