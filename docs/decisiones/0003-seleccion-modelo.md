# 0003. Selección del modelo de clasificación

- **Estado:** aceptada
- **Fecha:** 2026-11-19

## Contexto

La Fase III (secciones 6.3 a 6.7 del documento de diseño) pide comparar varios algoritmos para
clasificar un documento en **dominio → área** (7 dominios y 136 áreas, ver ADR 0002), elegir uno
y publicarlo para la API. La regla de selección es:

- mayor **F1-macro jerárquico en validación**;
- si otro modelo queda a menos de 2 puntos del mejor y es más rápido, gana el más rápido;
- el conjunto de prueba se usa **una sola vez**, con el modelo ya elegido.

Metas: F1-macro ≥ 0,85 en dominio y ≥ 0,65 en área (RNF-02), y menos de 2 s por resumen
(RNF-01).

## Candidatos

Todos usan las particiones del ADR 0002 (train 32.888 · val 7.047 · test 7.048).

- **Complement Naive Bayes** (línea base) y **LinearSVC** (`class_weight=balanced`), cada uno
  sobre su propio TF-IDF (`ngram_range=(1,2)`, `min_df=3`, `max_df=0,9`,
  `max_features=100000`, `sublinear_tf`). Los hiperparámetros se eligen con `GridSearchCV`
  (CV estratificada de 5 particiones sobre train, F1-macro). Después se calibran las
  probabilidades con `CalibratedClassifierCV` sigmoide. Cada algoritmo se entrena en dos
  variantes:
  - **jerárquico:** 1 clasificador de dominio + 1 de área por dominio;
  - **plano:** 1 clasificador de las 136 áreas, con `P(dominio)` = suma de sus áreas.
- **DistilBERT** (`distilbert-base-uncased`, plano, 256 tokens, 3 épocas, lote 32, lr 5e-5),
  entrenado en Google Colab con una GPU T4 (11 min).

Hiperparámetros elegidos: NB plano `alpha=1,0`. SVM plano `C=1,0`. En el SVM jerárquico,
`C=1,0` en todos los submodelos salvo uno (`C=0,5`).

## Resultados en validación

| Modelo | F1 dominio | F1 área (= jerárquico) | Accuracy jerárquica | ms por resumen (CPU) |
| --- | --- | --- | --- | --- |
| **SVM · plano** | 0,902 | **0,781** | 0,795 | 215 |
| DistilBERT · plano | **0,908** | 0,769 | **0,799** | 233 |
| SVM · jerárquico | 0,878 | 0,751 | 0,763 | 79 |
| NB · plano | 0,856 | 0,720 | 0,727 | 203 |
| NB · jerárquico | 0,801 | 0,642 | 0,651 | 76 |

Los tiempos de los modelos clásicos incluyen el `Preprocesador` (spaCy), que es la mayor parte
del costo. El tiempo de DistilBERT es en CPU, que es donde corre la API.

## Decisión

Se elige el **SVM lineal plano calibrado** (`models/linear_svc/20261119-1555/plano.joblib`):

- Tiene el mayor F1-macro jerárquico (0,781).
- DistilBERT queda a 1,2 puntos, pero es más lento, así que la regla de desempate también
  favorece al SVM.
- El SVM jerárquico es más rápido, pero queda a 3 puntos, fuera del margen de 2.

**Umbrales de «requiere revisión»**, calibrados en validación: se eligió la combinación que
envía menos documentos a revisión con una accuracy jerárquica ≥ 0,90 en los aceptados.

| Umbrales (dominio / conjunta) | % a revisión | Accuracy aceptados | Errores detectados |
| --- | --- | --- | --- |
| Diseño (0,60 / 0,40) | 18,1 % | 0,875 | 49,9 % |
| **Calibrados (0,65 / 0,50)** | 24,8 % | **0,901** | 63,6 % |

**Evaluación en test** (una sola vez):

| Meta | Resultado | Cumple |
| --- | --- | --- |
| F1-macro dominio ≥ 0,85 | 0,910 | ✅ |
| F1-macro área ≥ 0,65 | 0,791 | ✅ |
| < 2 s por resumen | 0,21 s | ✅ |

En test, el 23,9 % de los documentos requiere revisión, con una accuracy jerárquica de 0,902
en los aceptados. El modelo, sus umbrales y sus métricas quedan en `models/activo.json`, que es
lo que carga la API.

## Alternativas consideradas

- **DistilBERT:** tiene el mejor F1 de dominio, pero no supera al SVM en área, es más lento en
  CPU, pesa ~260 MB frente a unos pocos MB y obliga a instalar PyTorch en el backend.
- **Clasificador jerárquico:** con TF-IDF rinde peor que el plano en los dos algoritmos (−3
  puntos en SVM, −8 en NB). Es probable que cada submodelo de área tenga menos datos y que los
  errores de dominio se arrastren al área. Esto ya se veía en la muestra del 10 %.
- **Complement NB:** es una línea base útil, pero queda 6 puntos por debajo del SVM.
- **Random Forest:** descartado desde el diseño. Con 100.000 rasgos dispersos es lento y suele
  rendir menos que los modelos lineales.

## Consecuencias

- La API solo necesita scikit-learn y spaCy. No hace falta GPU ni PyTorch.
- Como el modelo es plano, la jerarquía se impone al decodificar: el área se elige dentro del
  dominio predicho, y la confianza conjunta es `P(dominio)·P(área|dominio)`.
- Los errores se concentran en áreas que se repiten entre dominios o que tienen pocos ejemplos
  (*Depression*, *Schizophrenia* y *Anxiety*, entre Psychology y Medical), y en los
  dominios Psychology y biochemistry (13 a 15 % de sus documentos va a otro dominio). Esos
  casos son justo los que el umbral de revisión debe atrapar.
- Uno de cada cuatro documentos se marca para revisión. Si en la práctica son demasiados,
  los umbrales se pueden relajar con la curva del notebook 05, a cambio de menos precisión.
- Los artefactos no se versionan en Git. Para reproducirlos: `python -m
  clasificador_ml.entrenamiento --config ml/configs/svm.yaml` y luego el notebook 05.
