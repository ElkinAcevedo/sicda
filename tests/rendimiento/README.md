# Prueba de rendimiento

Comprueba **RNF-01** con el plan de pruebas de la sección 11 del diseño: 50 clasificaciones
seguidas de resúmenes y 50 de PDF de 20 páginas. El percentil 95 del tiempo de respuesta debe
quedar por debajo de **2 s para el texto** y de **5 s para el PDF**. Los resultados están en el
[informe de pruebas](../../docs/pruebas.md#rendimiento).

## Ejecutar

Necesita la API corriendo con el modelo real y `data/processed/test.parquet`, de donde salen los
resúmenes. Las clasificaciones quedan guardadas en el historial, así que conviene usar una base
aparte:

```bash
# Terminal 1: API con una base de datos temporal
cd backend
CLASIFICADOR_URL_BASE_DATOS=sqlite:////tmp/rendimiento.db uvicorn app.main:app --port 8000

# Terminal 2: la prueba (unos 30 s)
python tests/rendimiento/rendimiento.py --salida /tmp/rendimiento.json
```

Opciones:

- `--url`: otra API, por ejemplo `http://localhost:8080` para medir la de Docker (pasa por nginx).
- `--repeticiones`: cuántas clasificaciones de cada tipo hacer (50 por defecto).
- `--datos`: otro Parquet con una columna `texto`.
- `--salida`: guarda los resultados en JSON, con la fecha y el equipo.

El script imprime la tabla en Markdown, lista para copiar al informe. Termina con código 1 si
alguna de las dos metas no se cumple.

## Cómo mide

- Antes de medir hace una clasificación de cada tipo que no se cuenta (calentamiento).
- Cada PDF se genera en memoria: título, `Abstract` con un resumen distinto, `Keywords` y 19
  páginas más de cuerpo con texto de otros resúmenes (unas 350 palabras por página).
- El tiempo se mide en el cliente con `time.perf_counter`, así que incluye la red, la extracción,
  el modelo y el guardado. También se informa el p95 del `tiempo_ms` que devuelve la API.
- El percentil se calcula con interpolación lineal, igual que `numpy.percentile`.

`test_rendimiento.py` prueba el script sin la API real (con `httpx.MockTransport`); el CI corre
esas pruebas con `pytest tests/rendimiento`.
