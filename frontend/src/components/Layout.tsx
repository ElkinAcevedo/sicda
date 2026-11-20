import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { api } from '@/api/cliente'
import { useTema } from '@/lib/hooks'

const enlaces = [
  { a: '/', texto: 'Clasificar', fin: true },
  { a: '/historial', texto: 'Historial', fin: false },
  { a: '/metricas', texto: 'Métricas', fin: false },
]

type EstadoApi = { conectada: boolean | null; modelo: string | null }

export function Layout() {
  const [estado, setEstado] = useState<EstadoApi>({ conectada: null, modelo: null })
  const [tema, alternarTema] = useTema()

  useEffect(() => {
    api
      .salud()
      .then((salud) => setEstado({ conectada: true, modelo: salud.modelo_activo }))
      .catch(() => setEstado({ conectada: false, modelo: null }))
  }, [])

  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900 md:flex-row dark:bg-slate-950 dark:text-slate-100">
      <a
        href="#contenido"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-10 focus:rounded focus:bg-white focus:px-3 focus:py-2"
      >
        Saltar al contenido
      </a>
      <aside className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-slate-200 bg-white p-3 md:w-60 md:flex-col md:flex-nowrap md:items-stretch md:border-r md:border-b-0 md:p-4 dark:border-slate-800 dark:bg-slate-900">
        <div className="md:mb-6 md:px-2">
          <p className="text-lg font-semibold">SICDA</p>
          <p className="hidden text-xs text-slate-500 md:block dark:text-slate-400">
            Clasificación de documentos académicos
          </p>
        </div>
        <nav aria-label="Principal" className="flex gap-1 md:flex-col">
          {enlaces.map(({ a, texto, fin }) => (
            <NavLink
              key={a}
              to={a}
              end={fin}
              className={({ isActive }) =>
                `rounded-md px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-indigo-600 ${
                  isActive
                    ? 'bg-indigo-50 font-semibold text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300'
                    : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
                }`
              }
            >
              {texto}
            </NavLink>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-3 md:mt-auto md:ml-0 md:flex-col md:items-stretch md:gap-2 md:px-2">
          <button
            type="button"
            onClick={alternarTema}
            className="rounded-md px-2 py-1 text-left text-xs text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            {tema === 'oscuro' ? '☀ Modo claro' : '☾ Modo oscuro'}
          </button>
          <p className="text-xs text-slate-500 dark:text-slate-400" aria-live="polite">
            <span
              aria-hidden="true"
              className={`mr-1.5 inline-block size-2 rounded-full ${
                estado.conectada === null
                  ? 'bg-slate-300'
                  : estado.conectada
                    ? 'bg-emerald-500'
                    : 'bg-rose-500'
              }`}
            />
            API:{' '}
            {estado.conectada === null ? 'comprobando…' : estado.conectada ? 'activa' : 'sin conexión'}
          </p>
          {estado.modelo && (
            <p className="hidden text-xs text-slate-500 md:block dark:text-slate-400">
              Modelo: {estado.modelo}
            </p>
          )}
        </div>
      </aside>
      <main id="contenido" className="min-w-0 flex-1 p-4 sm:p-6 lg:p-8">
        <div className="mx-auto max-w-6xl">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
