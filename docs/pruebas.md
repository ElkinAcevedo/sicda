# Informe de pruebas

Resultados del plan de pruebas (sección 11 del documento de diseño). Cada sección indica la
fecha y el commit en que se midió.

| Tipo | Criterio de aceptación | Estado |
| --- | --- | --- |
| Evaluación del modelo | F1-macro ≥ 0,85 (dominio) y ≥ 0,65 (área) | ✅ En test: 0,91 y 0,79 ([ADR 0003](decisiones/0003-seleccion-modelo.md)). ✅ En 30 artículos externos: 0,97 y 0,81 (ver [Artículos externos](#artículos-externos)) |
| Unitarias | 100 % aprobadas y cobertura ≥ 70 % | ✅ Ver [Cobertura](#cobertura) |
| Integración (API) | Todos los contratos responden según lo especificado | ✅ `backend/tests/api/` |
| Extremo a extremo | El flujo completo funciona en Chrome y Firefox | ✅ Ver [Extremo a extremo](#extremo-a-extremo) |
| Rendimiento | p95 < 2 s para texto y < 5 s para PDF | ✅ p95 de 0,23 s en ambos (ver [Rendimiento](#rendimiento)) |
| Usabilidad | Tasa de éxito ≥ 90 % y SUS ≥ 70 | ⚪ No realizada (ver [Usabilidad](#usabilidad)) |

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

## Rendimiento

Medido el 2026-11-21 con el modelo activo (`linear_svc` `20261119-1555`) y el script
[`tests/rendimiento/rendimiento.py`](../tests/rendimiento/README.md) (httpx), contra la API
levantada con `uvicorn` (un proceso, sin `--reload`) en un portátil con Intel Core i5-1135G7
(4 núcleos, 8 hilos) y Linux.

Se hicieron **50 clasificaciones seguidas de cada tipo**, después de una de calentamiento que no
se cuenta:

- **Texto pegado:** 50 resúmenes distintos del conjunto de prueba de WOS (entre 50 y 770
  palabras).
- **PDF de 20 páginas:** 50 PDF generados por el script, cada uno con título, `Abstract`,
  `Keywords` y 19 páginas más de cuerpo (unas 7.000 palabras en total). La API los lee
  completos, quita encabezados y pies, localiza el resumen y lo clasifica.

| Entrada | Mediana | p95 | Máximo | Meta (RNF-01) | ¿Cumple? |
| --- | --- | --- | --- | --- | --- |
| Texto pegado | 216 ms | **231 ms** | 329 ms | p95 < 2 s | ✅ |
| PDF de 20 páginas | 227 ms | **234 ms** | 243 ms | p95 < 5 s | ✅ |

El tiempo se mide en el cliente, desde que sale la petición hasta que llega la respuesta: incluye
la red local, la extracción, el modelo y el guardado en SQLite. El `tiempo_ms` que informa la
propia API es casi igual (p95 de 226 y 230 ms), así que la red y la serialización no pesan.

Casi todo el tiempo es del modelo, sobre todo de la lematización con spaCy. Leer las 20 páginas
del PDF solo suma unos 10 ms. El margen es de unas 8 veces para el texto y de 20 para el PDF.

Límites de la medición:

- Las peticiones son seguidas, de una en una, como en el plan de pruebas. No se midió la carga
  con varios usuarios a la vez.
- Los PDF son generados, con texto seleccionable. Un PDF real con imágenes pesa más, pero la API
  solo lee el texto (y como máximo 30 páginas).
- Con Docker (`--url http://localhost:8080`) se suma el paso por nginx, que no se midió aquí.

## Usabilidad

**No se realizó.** El plan preveía que 5 a 8 usuarios (estudiantes y docentes) completaran
4 tareas sin ayuda y respondieran el cuestionario SUS: clasificar un PDF, interpretar una
clasificación que pide revisión, encontrar una clasificación en el historial e identificar el
modelo con mejor desempeño en el panel de métricas. Por el tiempo disponible para la entrega se
decidió omitirla, así que **RNF-04** (primer documento clasificado en menos de 1 minuto sin
ayuda y SUS ≥ 70) **queda sin verificar** y pasa a trabajo futuro.

Lo que sí está comprobado del flujo es que funciona de extremo a extremo en Chrome y Firefox
(ver [Extremo a extremo](#extremo-a-extremo)); no se midió si un usuario nuevo lo entiende sin
ayuda.
