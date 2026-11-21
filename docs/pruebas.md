# Informe de pruebas

Resultados del plan de pruebas (sección 11 del documento de diseño). Se completa durante la
Fase V; cada sección indica la fecha y el commit en que se midió.

| Tipo | Criterio de aceptación | Estado |
| --- | --- | --- |
| Evaluación del modelo | F1-macro ≥ 0,85 (dominio) y ≥ 0,65 (área) | ✅ En test: 0,91 y 0,79 ([ADR 0003](decisiones/0003-seleccion-modelo.md)). ✅ En 30 artículos externos: 0,97 y 0,81 (ver [Artículos externos](#artículos-externos)) |
| Unitarias | 100 % aprobadas y cobertura ≥ 70 % | ✅ Ver [Cobertura](#cobertura) |
| Integración (API) | Todos los contratos responden según lo especificado | ✅ `backend/tests/api/` |
| Extremo a extremo | El flujo completo funciona en Chrome y Firefox | ✅ Ver [Extremo a extremo](#extremo-a-extremo) |
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

## Artículos externos

Medida el 2026-11-21 con el modelo activo (`linear_svc` `20261119-1555`) sobre **30 artículos
reales de arXiv y PubMed publicados desde 2020**, que no pueden estar en WOS-46985 (2017).
Se cubren 5 dominios con 6 artículos cada uno. Ingeniería Civil e Ingeniería Mecánica casi no
tienen artículos en esas fuentes y quedan fuera. El modelo clasifica solo el resumen, como en
el entrenamiento. Procedimiento en [`ml/README.md`](../ml/README.md#evaluar-con-artículos-externos-fase-v).

| Nivel | Accuracy | F1-macro | Meta (RNF-02) |
| --- | --- | --- | --- |
| Dominio | 0,967 | 0,966 | ≥ 0,85 ✅ |
| Área (jerárquico) | 0,833 | 0,811 | ≥ 0,65 ✅ |

| Dominio | Dominio correcto | Área correcta |
| --- | --- | --- |
| Biochemistry | 5/6 | 5/6 |
| Computer Science | 6/6 | 4/6 |
| Electrical and Computer Engineering | 6/6 | 6/6 |
| Medical Sciences | 6/6 | 5/6 |
| Psychology | 6/6 | 5/6 |

El 27 % de los artículos se marca «requiere revisión». En los aceptados, la accuracy
jerárquica es 0,909, la misma meta con que se calibraron los umbrales en validación (≥ 0,90).

**Errores (5).** Todos son confusiones con un área cercana. Tres de ellos se mandaron a
revisión.

| Artículo | Real | Predicho | ¿A revisión? |
| --- | --- | --- | --- |
| Búsqueda federada con cifrado homomórfico | Cryptography | Relational databases | No |
| Acelerador para *rendering* neuronal | Computer graphics | Algorithm design | Sí |
| Narrativas de sobrevivientes de incesto | Child abuse | Borderline personality disorder | Sí |
| Osteoporosis menopáusica | Osteoporosis | Menopause | Sí |
| Piezo1 en macrófagos y fibrosis hepática | Biochemistry / Immunology | Medical / Idiopathic Pulmonary Fibrosis | No |

Los resultados son mejores que en test (dominio 0,91, área 0,79), pero con 30 artículos el
margen de error es amplio. Además, las áreas se eligieron porque tienen una categoría clara en
arXiv o PubMed, lo que probablemente las hace más fáciles que el promedio. La conclusión
prudente es que **el modelo generaliza a artículos recientes fuera del dataset**, sin perder
desempeño apreciable.

**Etiquetado.** Las categorías reales salen de la consulta que encontró cada artículo y se
revisaron leyendo el título y el resumen, sin ver las predicciones. De los 30 incluidos al
inicio, 6 se cambiaron por su reserva y uno de esos cambió de área (demencia en general:
Alzheimer's Disease → Dementia). Se descartaron 2 textos que no eran investigación (una
entrevista y un capítulo introductorio), 2 de otro tema, 1 editorial y 1 más cercano a
Bioinformática. Cada cambio está anotado en la columna `notas` de `data/external/articulos.xlsx`.

## Extremo a extremo

Medida el 2026-11-21 con Playwright 1.65 (Chromium y Firefox 159): **6 de 6 pruebas
aprobadas** (3 por navegador) en unos 15 s, estables en 4 ejecuciones seguidas. Corren en el CI
en cada *pull request* (job «Extremo a extremo»).

| Prueba | Chromium | Firefox |
| --- | --- | --- |
| Cargar un PDF → ver el resultado → encontrarlo en el historial → corregirlo | ✅ | ✅ |
| Clasificar un texto pegado | ✅ | ✅ |
| Mostrar el error `TEXTO_INSUFICIENTE` de la API | ✅ | ✅ |

Las pruebas usan la API y el dashboard reales con un SVM diminuto entrenado con el código del
proyecto sobre datos sintéticos, porque en el CI no hay modelos ni datos. Comprueban que todas
las piezas funcionen juntas, no la calidad del modelo; esa se mide en la evaluación del modelo.
Detalles en [`tests/e2e/README.md`](../tests/e2e/README.md).
