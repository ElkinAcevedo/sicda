# Informe de pruebas

Resultados del plan de pruebas (sección 11 del documento de diseño). Se completa durante la
Fase V; cada sección indica la fecha y el commit en que se midió.

| Tipo | Criterio de aceptación | Estado |
| --- | --- | --- |
| Evaluación del modelo | F1-macro ≥ 0,85 (dominio) y ≥ 0,65 (área) | ✅ En test: 0,91 y 0,79 ([ADR 0003](decisiones/0003-seleccion-modelo.md)). ⏳ Faltan los 30 artículos externos |
| Unitarias | 100 % aprobadas y cobertura ≥ 70 % | ✅ Ver [Cobertura](#cobertura) |
| Integración (API) | Todos los contratos responden según lo especificado | ✅ `backend/tests/api/` |
| Extremo a extremo | El flujo completo funciona en Chrome y Firefox | ⏳ |
| Rendimiento | p95 < 2 s para texto y < 5 s para PDF | ⏳ |
| Usabilidad | Tasa de éxito ≥ 90 % y SUS ≥ 70 | ⏳ |

## Cobertura

Medida el 2026-11-21. El CI falla si cualquiera de las tres partes baja del 70 % (RNF-07).

| Parte | Pruebas | Cobertura | Comando |
| --- | --- | --- | --- |
| Backend (`app`) | 144 | 99 % de líneas | `cd backend && pytest --cov=app` |
| Paquete ML (`clasificador_ml`) | 80 | 95 % de líneas | `pytest ml/tests --cov=clasificador_ml` |
| Frontend (`src/`) | 40 | 95 % de líneas · 87 % de ramas | `cd frontend && npm run test:cobertura` |

En el frontend se mide todo `src/`, también los archivos que ninguna prueba importa, sin contar
las pruebas ni `main.tsx`. Las pruebas no usan `models/` ni `data/` reales: los modelos y la
base de datos se reemplazan por dobles (`backend/tests/conftest.py`), así que la cobertura es la
misma en local y en el CI.

Las partes con menos cobertura (`ZonaArchivo.tsx`, arrastrar y soltar, y los entrypoints
`python -m` de `datos.py` y `preprocesamiento.py`) las ejercitan las pruebas de extremo a
extremo y la ejecución manual de los comandos.
