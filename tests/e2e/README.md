# Pruebas de extremo a extremo

Pruebas con **Playwright** que usan la aplicación completa desde el navegador, en **Chromium y
Firefox** (plan de pruebas, sección 11 del diseño):

| Prueba | Qué comprueba |
| --- | --- |
| Clasifica un PDF, lo encuentra en el historial y lo corrige | El flujo del diseño: cargar un PDF → ver el resultado (título extraído, «Abstract» encontrado, dominio, área y términos clave) → buscarlo en el historial → corregirlo → la corrección sigue tras recargar. |
| Clasifica un texto pegado | La pestaña «Pegar texto» con título. |
| Muestra el error de la API cuando el texto no alcanza | Un TXT demasiado corto llega a la API y el dashboard muestra `TEXTO_INSUFICIENTE`. |

## Cómo funcionan

No usan `models/` ni `data/` (en el CI no existen) ni dobles de la API: todo es real.

1. `preparar.py` entrena un **SVM plano diminuto** con el mismo código del proyecto
   (`clasificador_ml.entrenamiento`) sobre un dataset sintético de 2 dominios y 4 áreas, lo
   publica como modelo activo y genera un PDF por navegador. Todo queda en `.recursos/`
   (no se versiona) y tarda unos 3 s.
2. Playwright levanta la API (puerto 8001) con ese modelo y una base SQLite nueva, y el
   dashboard con Vite (puerto 5174). Son puertos propios para no chocar con el entorno de
   desarrollo (8000 y 5173) ni con Docker (8080).

La API reutiliza los documentos con el mismo contenido (hash SHA-256), así que cada navegador
sube su propio PDF y su propio texto.

## Ejecutar

Requiere el `.venv` del proyecto y las dependencias del frontend (`npm ci` en `frontend/`).

```bash
cd tests/e2e
npm ci
npm run navegadores     # solo la primera vez: descarga Chromium y Firefox
npm test                # o: npx playwright test --project=chromium --headed
```

Para usar otro intérprete de Python: `PYTHON=/ruta/a/python npm test`.

Si una prueba falla, Playwright guarda la captura y la traza en `test-results/`; se abren con
`npx playwright show-trace test-results/<prueba>/trace.zip`. En el CI se suben como artefacto
(`informe-playwright`).
