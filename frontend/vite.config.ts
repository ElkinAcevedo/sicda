/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    port: 5173,
    // En desarrollo, /api se redirige a FastAPI: el frontend nunca escribe la URL del backend.
    // Las pruebas e2e cambian el destino con VITE_API_PROXY para usar su propia API.
    proxy: { '/api': process.env.VITE_API_PROXY ?? 'http://localhost:8000' },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    // `npm run test:cobertura`. Se mide todo src/, no solo lo que cargan las pruebas, y el
    // CI falla por debajo del 70 % (RNF-07).
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/**/*.test.{ts,tsx}', 'src/test/**', 'src/main.tsx', 'src/**/*.d.ts'],
      reporter: ['text-summary', 'text'],
      thresholds: { lines: 70, statements: 70, functions: 70, branches: 70 },
    },
  },
})
