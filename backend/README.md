# Backend · API REST

API construida con **FastAPI** que recibe documentos, extrae su texto, los clasifica con el modelo activo y guarda el historial.

## Estructura

```text
backend/
├── app/
│   ├── main.py              # crea la aplicación FastAPI
│   ├── core/config.py       # configuración (variables CLASIFICADOR_*)
│   ├── api/v1/
│   │   ├── router.py        # agrupa los routers
│   │   └── endpoints/       # un archivo por recurso
│   ├── schemas/             # modelos Pydantic de entrada y salida
│   ├── extraccion/          # PDF, DOCX, TXT → texto; resumen; idioma
│   ├── clasificacion/       # carga del modelo y predicción jerárquica
│   └── db/                  # SQLAlchemy: tablas y repositorios
└── tests/
```

## Ejecutar

Con el entorno configurado (`scripts/configurar_entorno.sh`) y activado:

```bash
cd backend
uvicorn app.main:app --reload
```

- Documentación interactiva: <http://localhost:8000/docs>
- Estado: <http://localhost:8000/api/v1/salud>

## Configuración

Todas las variables usan el prefijo `CLASIFICADOR_` y se leen del archivo `.env` (ver `.env.example`).

| Variable | Valor por defecto | Descripción |
| --- | --- | --- |
| `CLASIFICADOR_URL_BASE_DATOS` | `sqlite:///./clasificador.db` | Conexión a la base de datos. |
| `CLASIFICADOR_RUTA_MODELOS` | `../models` | Carpeta con `activo.json` y los modelos entrenados. |
| `CLASIFICADOR_RUTA_CATEGORIAS` | `../data/processed/categorias.json` | Nombres de los dominios y las áreas. |
| `CLASIFICADOR_TAMANO_MAXIMO_ARCHIVO_MB` | `10` | Tamaño máximo de archivo aceptado. |
| `CLASIFICADOR_MINIMO_TERMINOS` | `20` | Términos mínimos del resumen para poder clasificarlo. |
| `CLASIFICADOR_ORIGENES_CORS` | `["http://localhost:5173"]` | Orígenes permitidos (frontend). |

Los umbrales de «requiere revisión» **no** se configuran aquí: se calibraron en validación
(notebook 05) y vienen en `models/activo.json` junto con el modelo.

## Persistencia

`app/db/` implementa el modelo de datos de la sección 5.2 del diseño con SQLAlchemy 2.0:

| Archivo | Contenido |
| --- | --- |
| `sesion.py` | `crear_motor(url)`, `SesionLocal`, `crear_tablas()` y la dependencia `obtener_sesion`. |
| `modelos.py` | Tablas `documento`, `clasificacion`, `correccion` y `modelo`. |
| `repositorios.py` | Funciones de lectura y escritura (historial paginado y filtrado, modelo activo, correcciones). |

- Las tablas se crean al iniciar la API (`crear_tablas` en el *lifespan*); no hay migraciones.
- En SQLite se activan las claves foráneas, y un índice único parcial garantiza que haya
  **como máximo un modelo activo**. `activar_modelo` desactiva los demás.
- `documento.hash_sha256` es único: el mismo archivo (o el mismo texto pegado, sin contar los
  espacios) se guarda una sola vez y cada nueva clasificación se le asocia.
- Una clasificación tiene como máximo una corrección; una corrección nueva reemplaza a la anterior.
- Las fechas se guardan en UTC sin zona horaria; los filtros `desde` y `hasta` aceptan fechas
  con zona y las convierten. Una fecha sin hora en `hasta` incluye el día completo.
- Campos agregados al diseño, para reconstruir la respuesta de `GET /clasificaciones/{id}` sin
  volver a clasificar: `documento.fuente_texto`, `documento.palabras_clave`,
  `clasificacion.conf_conjunta` y `clasificacion.advertencias`.

## Endpoints

| Método | Ruta | Estado |
| --- | --- | --- |
| GET | `/api/v1/salud` | ✅ Implementado |
| GET | `/api/v1/categorias` | ⏳ Pendiente |
| POST | `/api/v1/clasificaciones/archivo` | ✅ Implementado |
| POST | `/api/v1/clasificaciones/texto` | ✅ Implementado |
| GET | `/api/v1/clasificaciones` | ⏳ Pendiente |
| GET | `/api/v1/clasificaciones/{id}` | ⏳ Pendiente |
| POST | `/api/v1/clasificaciones/{id}/correccion` | ⏳ Pendiente |
| GET | `/api/v1/modelos` | ⏳ Pendiente |
| GET | `/api/v1/modelos/{id}/metricas` | ⏳ Pendiente |

Los contratos completos están en la sección 7 del documento de diseño.

## Clasificación (`app/clasificacion/`)

Al iniciar, la API lee `models/activo.json` (lo publica el notebook 05), carga el `.joblib` que
señala **una sola vez**, lo registra como modelo activo en la tabla `modelo` y hace una
predicción de calentamiento para que spaCy ya esté cargado cuando llegue el primer usuario. Si
el modelo no se puede cargar, la API arranca igual y los endpoints de clasificación responden
`503 MODELO_NO_DISPONIBLE`. `GET /salud` indica qué modelo está cargado.

Cada `POST /clasificaciones/*`:

1. extrae el resumen (archivo o texto pegado);
2. lo clasifica con el modelo activo: dominio, área, top 3 de alternativas por nivel,
   confianza conjunta, «requiere revisión» y términos clave;
3. guarda el documento (una sola vez por hash) y la clasificación, y responde `201`.

```bash
curl -X POST localhost:8000/api/v1/clasificaciones/texto \
  -H 'Content-Type: application/json' \
  -d '{"titulo": "A lightweight CNN", "texto": "Convolutional neural networks ..."}'
curl -X POST localhost:8000/api/v1/clasificaciones/archivo -F archivo=@articulo.pdf
```

Errores, con el formato `{"error": {"codigo", "mensaje"}}`: `ENTRADA_INVALIDA` 400,
`ARCHIVO_MUY_GRANDE` 413, `FORMATO_NO_SOPORTADO` 415, `TEXTO_INSUFICIENTE` y
`ARCHIVO_DANADO` 422, `MODELO_NO_DISPONIBLE` 503.

Con el SVM plano, cada clasificación tarda unos 200 ms en CPU (RNF-01 pide menos de 2 s).

## Extracción de texto (`app/extraccion/`)

Convierte un archivo subido o un texto pegado en el resumen que recibirá el clasificador
(RF-01 a RF-04, sección 6.1 del diseño).

```python
from app.extraccion import extraer_documento, extraer_texto_pegado

resultado = extraer_documento(contenido_bytes, "articulo.pdf")
resultado.titulo, resultado.texto, resultado.fuente_texto, resultado.idioma, resultado.advertencias
```

| Paso | Cómo |
| --- | --- |
| Lectura | PDF con PyMuPDF (primeras 30 páginas, en el orden del PDF para no mezclar columnas, sin encabezados ni pies repetidos), DOCX con python-docx (solo párrafos), TXT en UTF-8 con respaldo a CP-1252/Latin-1. |
| Limpieza | Normalización NFKC (ligaduras como «ﬁ»), une palabras cortadas con guion y normaliza espacios. |
| Título | Metadatos del archivo o, si no hay, la primera línea con forma de título antes del resumen. |
| Resumen | Bloque que sigue a «Abstract», «A B S T R A C T», «Summary» o «Resumen» y termina en «Keywords», «Introduction», «Palabras clave», «©»… Si hay *Resumen* y *Abstract*, se prefiere el inglés. Si no hay encabezado, se usan los primeros 300 términos (`fuente_texto = "inicio"`). |
| Palabras clave | Línea «Keywords:» / «Index Terms» / «Palabras clave:». |
| Idioma | langdetect con semilla fija. |

Errores (cada uno con `codigo_http` y `codigo` de la sección 7.3 del diseño):

| Excepción | HTTP | Código | Cuándo |
| --- | --- | --- | --- |
| `FormatoNoSoportado` | 415 | `FORMATO_NO_SOPORTADO` | Extensión distinta de PDF, DOCX o TXT. |
| `ArchivoDemasiadoGrande` | 413 | `ARCHIVO_MUY_GRANDE` | Más de `CLASIFICADOR_TAMANO_MAXIMO_ARCHIVO_MB`. |
| `ArchivoDanado` | 422 | `ARCHIVO_DANADO` | Archivo corrupto, protegido con contraseña o con otra extensión. |
| `TextoInsuficiente` | 422 | `TEXTO_INSUFICIENTE` | Sin texto (PDF escaneado) o menos de `CLASIFICADOR_MINIMO_TERMINOS` términos. |

Advertencias no bloqueantes: `RESUMEN_NO_ENCONTRADO` e `IDIOMA_NO_SOPORTADO`.

> `ARCHIVO_DANADO` no está en la tabla 7.3 del diseño; se agregó para distinguir un archivo
> roto de uno sin texto. La comprobación de «20 términos útiles *tras* el preprocesamiento» se
> completará en la Fase IV, cuando la API cargue el pipeline del modelo.

Probado con *Deep Residual Learning for Image Recognition* (arXiv 1512.03385, dos columnas):
título y resumen completos en ~0,3 s.

## Pruebas

```bash
cd backend
pytest --cov=app
```
