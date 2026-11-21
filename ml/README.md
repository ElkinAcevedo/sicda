# ML · paquete `clasificador_ml`

Código de aprendizaje automático: preparación del dataset, preprocesamiento de texto, entrenamiento, evaluación y exportación de modelos.

El paquete se instala en modo editable y lo importan **tanto los scripts de entrenamiento como la API**. Así el texto que llega en producción se procesa exactamente igual que el texto con el que se entrenó.

## Módulos

| Módulo | Responsabilidad | Fase |
| --- | --- | --- |
| `rutas.py` | Rutas estándar del repositorio (`data/`, `models/`, `configs/`). | — |
| `configuracion.py` | Cargar un YAML de `configs/` combinado con `base.yaml`. | — |
| `datos.py` | Cargar WOS-46985, limpiar, generar `categorias.json` y dividir 70/15/15. | I |
| `preprocesamiento.py` | Normalización, *stopwords* y lematización en inglés. | II |
| `evaluacion.py` | Accuracy, precisión, recall, F1 (macro y ponderado) y matrices de confusión por nivel. | III |
| `jerarquico.py` | `ClasificadorJerarquico` (dominio + área por dominio) y `ClasificadorPlano`. | III |
| `busqueda.py` | `BusquedaYCalibracion`: `GridSearchCV` + calibración del mejor modelo. | III |
| `entrenamiento.py` | CLI que entrena NB y SVM y guarda los artefactos versionados. | III |
| `seleccion.py` | Regla de elección del modelo y calibración de los umbrales de revisión. | III |
| `artefactos.py` | Leer versiones de `models/` y publicar el modelo activo. | III |
| `externos.py` | Descargar artículos reales de arXiv y PubMed y evaluar el modelo activo con ellos. | V |

## Preparar el dataset (Fase I)

Con el dataset en `data/raw/` (ver [`data/README.md`](../data/README.md)):

```bash
python -m clasificador_ml.datos
```

Genera `data/processed/{train,val,test}.parquet` y `categorias.json`. Las reglas de etiquetado están en [ADR 0002](../docs/decisiones/0002-etiquetas-wos.md).

## Preprocesar el texto (Fase II)

```bash
python -m clasificador_ml.preprocesamiento --procesos 4   # ~2,5 min con 4 procesos
```

Genera `data/processed/preprocesado/{train,val,test}.parquet` con la columna `texto_procesado`.
Los pasos (sección 6.2 del diseño) son: minúsculas y Unicode → quitar URL, correos, números y
puntuación → lematizar con spaCy → quitar *stopwords* de NLTK. Se lematiza antes de quitar las
*stopwords* para que spaCy vea la frase completa.

`Preprocesador` es un transformador de scikit-learn, así que se guarda **dentro** del pipeline
del modelo y la API procesa el texto igual que el entrenamiento:

```python
from clasificador_ml.preprocesamiento import Preprocesador
from sklearn.pipeline import make_pipeline

modelo = make_pipeline(Preprocesador.desde_configuracion(), TfidfVectorizer(...), LinearSVC())
```

Para DistilBERT basta con `normalizar(texto)` (pasos 1 y 2), porque usa su propio tokenizador.

## Entrenar los modelos clásicos (Fase III)

```bash
python -m clasificador_ml.entrenamiento --config ml/configs/naive_bayes.yaml
python -m clasificador_ml.entrenamiento --config ml/configs/svm.yaml
# Prueba rápida con el 10 % de los datos (~40 s):
python -m clasificador_ml.entrenamiento --config ml/configs/svm.yaml --muestra 0.1 --version humo
```

Cada corrida entrena el clasificador **jerárquico** (1 modelo de dominio + 1 de área por cada
uno de los 7 dominios) y el **plano** (las 136 áreas), y los evalúa en validación. Cada
submodelo es un `Pipeline(TF-IDF, clasificador)` con su propio vocabulario; sus
hiperparámetros se eligen con `GridSearchCV` (5 particiones estratificadas sobre train,
F1-macro). En el SVM la búsqueda se hace sin calibrar y solo el mejor `C` se calibra
(`CalibratedClassifierCV`, sigmoide).

Resultado en `models/<algoritmo>/<version>/`:

| Archivo | Contenido |
| --- | --- |
| `jerarquico.joblib`, `plano.joblib` | Modelos con el `Preprocesador` incluido (reciben texto crudo). |
| `predicciones_val_<tipo>.parquet` | Predicciones y confianzas en validación. |
| `metadatos.json` | Configuración, hiperparámetros por submodelo, métricas y tiempos. |

```python
from clasificador_ml.artefactos import cargar_modelo

modelo = cargar_modelo("linear_svc", "jerarquico")  # la versión más reciente
modelo.predecir_detallado(["Deep convolutional networks for image segmentation ..."])
# [{'dominio': {'id', 'confianza', 'alternativas'}, 'area': {...}, 'confianza_conjunta',
#   'requiere_revision', 'terminos_clave': [{'termino', 'peso'}, ...]}]
```

**Decodificación.** Se elige el dominio con mayor `P(dominio)` y, dentro de él, el área con
mayor `P(área | dominio)`; la confianza conjunta es el producto. El plano (y DistilBERT) obtiene
`P(dominio)` sumando las probabilidades de sus áreas. «Requiere revisión» si
`P(dominio) < 0,60` o la conjunta `< 0,40` (se calibran en el notebook 05).

DistilBERT se entrena en Google Colab con `notebooks/04-distilbert-colab.ipynb`; el notebook 05
compara todos los modelos, calibra los umbrales, evalúa **una sola vez** en test y escribe
`models/activo.json`.

## Evaluar con artículos externos (Fase V)

El test viene del mismo dataset con que se entrenó; el diseño (sección 6.6) pide medir también
con **30 artículos reales** que el modelo nunca vio. Se usan artículos de arXiv y PubMed
publicados desde 2020, 6 por dominio en 5 dominios. Ingeniería Civil e Ingeniería Mecánica casi
no tienen artículos en esas fuentes y quedan fuera.

```bash
python -m clasificador_ml.externos descargar   # ~1,5 min: 2 candidatos por área → data/external/articulos.xlsx
# … revisión humana del Excel …
python -m clasificador_ml.externos evaluar     # ~3 s: evaluacion.xlsx y metricas.json
```

**Revisión del Excel.** De cada área, el primer candidato tiene `incluir = si` y el segundo
`incluir = reserva`. Para cada artículo con `si`, lee el título y el resumen (el enlace está en
`url`) y decide si de verdad es de ese dominio y esa área:

- Si lo es, pon `revisado = si`.
- Si es de otra área, corrige `dominio`/`area`. Los nombres deben ser exactamente los de
  `categorias.json`; `evaluar` avisa si alguno no existe.
- Si no sirve (biografía, editorial, tema ajeno), pon `incluir = no` y `incluir = si` en la
  reserva de esa área, y revísala.

`descargar` no sobrescribe un Excel ya existente, para no perder la revisión (`--sobrescribir`
lo fuerza). Las consultas de cada área están en `BUSQUEDAS`. Con 30 artículos el F1-macro de
área es poco estable (casi un artículo por clase), así que la cifra principal es la de dominio.

## Configuraciones

`configs/base.yaml` define la semilla, la partición y los parámetros de TF-IDF. Cada modelo tiene su archivo:

- `naive_bayes.yaml`: Complement Naive Bayes (línea base)
- `svm.yaml`: SVM lineal calibrado
- `distilbert.yaml`: DistilBERT con *fine-tuning* (se entrena en Google Colab)

## Instalación

El script `scripts/configurar_entorno.sh` (o `.ps1`) ya instala el paquete con `dev` y `notebooks`, el modelo `en_core_web_sm` de spaCy y las *stopwords* de NLTK.

Para entrenar DistilBERT en tu equipo (opcional, descarga varios GB; lo normal es usar Google Colab):

```bash
uv pip install -e "ml[transformers]"
```

Para abrir los notebooks:

```bash
jupyter lab notebooks/
```

## Pruebas

```bash
pytest ml/tests
```
