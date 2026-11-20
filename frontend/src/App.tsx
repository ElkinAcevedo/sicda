import { lazy, Suspense } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Layout } from '@/components/Layout'
import { Cargando } from '@/components/ui'
import { Clasificar } from '@/pages/Clasificar'
import { Historial } from '@/pages/Historial'
import { NoEncontrada } from '@/pages/NoEncontrada'
import { Resultado } from '@/pages/Resultado'

// Métricas trae Recharts (la mayor parte del peso): se descarga solo al abrir la vista.
const Metricas = lazy(() => import('@/pages/Metricas').then((m) => ({ default: m.Metricas })))

/** Rutas de la aplicación (separadas del router para poder probarlas con MemoryRouter). */
export function Rutas() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Clasificar />} />
        <Route path="resultado/:id" element={<Resultado />} />
        <Route path="historial" element={<Historial />} />
        <Route
          path="metricas"
          element={
            <Suspense fallback={<Cargando texto="Cargando métricas…" />}>
              <Metricas />
            </Suspense>
          }
        />
        <Route path="*" element={<NoEncontrada />} />
      </Route>
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Rutas />
    </BrowserRouter>
  )
}
