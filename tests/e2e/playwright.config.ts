import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { defineConfig, devices } from '@playwright/test'

/**
 * Pruebas de extremo a extremo (plan de pruebas, sección 11 del diseño).
 *
 * Playwright levanta la API real con un modelo diminuto (`preparar.py`) y el dashboard con
 * Vite, en puertos propios para no chocar con el entorno de desarrollo ni con Docker.
 */
const aqui = path.dirname(fileURLToPath(import.meta.url))
const raiz = path.resolve(aqui, '../..')
const recursos = path.join(aqui, '.recursos')
const python = process.env.PYTHON ?? path.join(raiz, '.venv/bin/python')

const PUERTO_API = 8001
const PUERTO_WEB = 5174

export default defineConfig({
  testDir: '.',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: `http://localhost:${PUERTO_WEB}`,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
  ],
  webServer: [
    {
      // Primero entrena el modelo diminuto y borra la base; luego levanta la API.
      command: `"${python}" "${path.join(aqui, 'preparar.py')}" && "${python}" -m uvicorn app.main:app --port ${PUERTO_API}`,
      cwd: path.join(raiz, 'backend'),
      url: `http://localhost:${PUERTO_API}/api/v1/salud`,
      timeout: 180_000,
      reuseExistingServer: false,
      env: {
        CLASIFICADOR_RUTA_MODELOS: path.join(recursos, 'modelos'),
        CLASIFICADOR_RUTA_DATOS: path.join(recursos, 'datos'),
        CLASIFICADOR_RUTA_CATEGORIAS: path.join(recursos, 'datos', 'categorias.json'),
        CLASIFICADOR_URL_BASE_DATOS: `sqlite:///${path.join(recursos, 'e2e.db')}`,
      },
    },
    {
      command: `npm run dev -- --port ${PUERTO_WEB} --strictPort`,
      cwd: path.join(raiz, 'frontend'),
      url: `http://localhost:${PUERTO_WEB}`,
      timeout: 60_000,
      reuseExistingServer: false,
      env: { VITE_API_PROXY: `http://localhost:${PUERTO_API}` },
    },
  ],
})
