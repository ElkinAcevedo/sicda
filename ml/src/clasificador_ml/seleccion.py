"""Comparación de modelos, calibración de umbrales y regla de selección (sección 6.6).

- Selección: mayor F1-macro jerárquico en validación; entre los que quedan a menos de 2
  puntos del mejor, gana el más rápido.
- Umbrales de «requiere revisión»: se recorre una rejilla en validación y se elige la
  combinación que marca **menos** documentos para revisión manteniendo una accuracy
  jerárquica mínima en los documentos aceptados automáticamente.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd

from clasificador_ml.jerarquico import condicional_desde_plano, decodificar, requiere_revision

MARGEN_EMPATE = 0.02
ACCURACY_MINIMA_ACEPTADOS = 0.90
UMBRALES_DOMINIO = tuple(np.round(np.arange(0.30, 0.91, 0.05), 2))
UMBRALES_CONJUNTA = tuple(np.round(np.arange(0.10, 0.81, 0.05), 2))


def seleccionar_modelo(
    tabla: pd.DataFrame,
    metrica: str = "f1_jerarquico",
    tiempo: str = "tiempo_ms",
    margen: float = MARGEN_EMPATE,
) -> str:
    """Nombre (índice de `tabla`) del modelo elegido según la regla del diseño."""
    if tabla.empty:
        raise ValueError("No hay modelos para comparar.")
    mejor = tabla[metrica].max()
    empatados = tabla[tabla[metrica] >= mejor - margen]
    return str(empatados[tiempo].idxmin())


def predicciones_desde_probabilidades(
    probabilidades: pd.DataFrame,
    area_a_dominio: Mapping[int, int],
    umbral_dominio: float = 0.60,
    umbral_conjunta: float = 0.40,
) -> pd.DataFrame:
    """Decodifica `P(área)` de un modelo plano externo (DistilBERT) como lo hace la API.

    Args:
        probabilidades: `id_documento` y columnas `p_<id_area>`.

    Devuelve las mismas columnas que `ClasificadorPlano.predecir_niveles`, más `id_documento`.
    """
    columnas = [c for c in probabilidades.columns if c.startswith("p_")]
    areas = np.array([int(c[2:]) for c in columnas])
    orden = np.argsort(areas)
    areas, matriz = areas[orden], probabilidades[columnas].to_numpy()[:, orden]
    dominios_area = np.array([area_a_dominio[a] for a in areas])
    dominios = np.unique(dominios_area)
    dominio_de_area = np.searchsorted(dominios, dominios_area)

    p_dominio, p_condicional = condicional_desde_plano(matriz, dominio_de_area, len(dominios))
    decision = decodificar(p_dominio, p_condicional, dominio_de_area)
    tabla = pd.DataFrame(
        {
            "id_documento": probabilidades["id_documento"].to_numpy(),
            "dominio_pred": dominios[decision["dominio"]],
            "area_pred": areas[decision["area"]],
            "confianza_dominio": decision["confianza_dominio"],
            "confianza_area": decision["confianza_area"],
            "confianza_conjunta": decision["confianza_conjunta"],
        }
    )
    tabla["requiere_revision"] = requiere_revision(
        tabla["confianza_dominio"], tabla["confianza_conjunta"], umbral_dominio, umbral_conjunta
    )
    return tabla


def curva_revision(
    predicciones: pd.DataFrame,
    umbrales_dominio: Sequence[float] = UMBRALES_DOMINIO,
    umbrales_conjunta: Sequence[float] = UMBRALES_CONJUNTA,
) -> pd.DataFrame:
    """Efecto de cada par de umbrales sobre las predicciones de validación.

    `predicciones` necesita `dominio_real`, `area_real`, `dominio_pred`, `area_pred`,
    `confianza_dominio` y `confianza_conjunta`.

    Columnas del resultado:
    - `porcentaje_revision`: documentos marcados para revisión.
    - `accuracy_aceptados`: accuracy jerárquica de los que **no** se marcan.
    - `errores_detectados`: proporción de los errores que quedan marcados.
    """
    acierto = (predicciones["dominio_pred"] == predicciones["dominio_real"]) & (
        predicciones["area_pred"] == predicciones["area_real"]
    )
    acierto = acierto.to_numpy()
    errores = max(int((~acierto).sum()), 1)
    filas = []
    for umbral_dominio in umbrales_dominio:
        for umbral_conjunta in umbrales_conjunta:
            marcados = requiere_revision(
                predicciones["confianza_dominio"],
                predicciones["confianza_conjunta"],
                umbral_dominio,
                umbral_conjunta,
            )
            aceptados = ~marcados
            filas.append(
                {
                    "umbral_dominio": float(umbral_dominio),
                    "umbral_conjunta": float(umbral_conjunta),
                    "porcentaje_revision": float(marcados.mean()),
                    "accuracy_aceptados": (
                        float(acierto[aceptados].mean()) if aceptados.any() else np.nan
                    ),
                    "accuracy_revisados": (
                        float(acierto[marcados].mean()) if marcados.any() else np.nan
                    ),
                    "errores_detectados": float((~acierto & marcados).sum() / errores),
                }
            )
    return pd.DataFrame(filas)


def elegir_umbrales(
    curva: pd.DataFrame, accuracy_minima: float = ACCURACY_MINIMA_ACEPTADOS
) -> pd.Series:
    """Fila de `curva` con menos revisión que cumple `accuracy_minima` en los aceptados.

    Si ninguna la cumple, devuelve la de mayor accuracy en los aceptados. En empate se
    prefieren umbrales más bajos.
    """
    validas = curva[curva["accuracy_aceptados"] >= accuracy_minima]
    if validas.empty:
        orden = curva.sort_values(
            ["accuracy_aceptados", "porcentaje_revision"], ascending=[False, True]
        )
        return orden.iloc[0]
    orden = validas.sort_values(["porcentaje_revision", "umbral_dominio", "umbral_conjunta"])
    return orden.iloc[0]
