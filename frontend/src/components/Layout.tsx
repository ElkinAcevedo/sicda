import { type ComponentType, type SVGProps, useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { api } from '@/api/cliente'
import logo from '@/assets/logo-sicda.svg'
import {
  IconoClasificar,
  IconoHistorial,
  IconoLuna,
  IconoMetricas,
  IconoSol,
} from '@/components/iconos'
import { useTema } from '@/lib/hooks'

interface Enlace {
  a: string
  texto: string
  ayuda: string
  icono: ComponentType<SVGProps<SVGSVGElement>>
  fin: boolean
}

const enlaces: Enlace[] = [
  { a: '/', texto: 'Clasificar', ayuda: 'Sube o pega un documento', icono: IconoClasificar, fin: true },
  { a: '/historial', texto: 'Historial', ayuda: 'Clasificaciones guardadas', icono: IconoHistorial, fin: false },
  { a: '/metricas', texto: 'Métricas', ayuda: 'Desempeño de los modelos', icono: IconoMetricas, fin: false },
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

  const oscuro = tema === 'oscuro'

  return (
    <div className="flex min-h-screen flex-col bg-slate-50 text-slate-900 md:flex-row dark:bg-slate-950 dark:text-slate-100">
      <a
        href="#contenido"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-20 focus:rounded focus:bg-white focus:px-3 focus:py-2 focus:text-slate-900"
      >
        Saltar al contenido
      </a>

      {/* La barra es oscura en los dos modos: separa la navegación del contenido. */}
      <aside className="relative z-10 flex flex-wrap items-center gap-x-3 gap-y-2 bg-gradient-to-b from-slate-900 via-slate-900 to-indigo-950 px-3 py-3 text-slate-300 shadow-lg md:sticky md:top-0 md:h-screen md:w-64 md:flex-col md:flex-nowrap md:items-stretch md:gap-0 md:px-4 md:py-6">
        {/* Marca */}
        <div className="flex items-center gap-3 md:mb-8 md:px-2">
          <img
            src={logo}
            alt=""
            width={56}
            height={56}
            className="size-10 shrink-0 rounded-xl shadow-lg shadow-black/30 md:size-14 md:rounded-2xl"
          />
          <div className="leading-tight">
            <p className="text-base font-bold tracking-wide text-white md:text-lg">SICDA</p>
            <p className="hidden text-xs text-slate-400 md:block">Clasificación de documentos académicos</p>
          </div>
        </div>

        {/* Navegación */}
        <nav aria-label="Principal" className="flex gap-1 md:flex-col md:gap-1.5">
          <p className="mb-2 hidden px-3 text-[11px] font-semibold tracking-widest text-slate-500 uppercase md:block">
            Menú
          </p>
          {enlaces.map(({ a, texto, ayuda, icono: Icono, fin }) => (
            <NavLink
              key={a}
              to={a}
              end={fin}
              className={({ isActive }) =>
                `group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400 md:py-2.5 ${
                  isActive
                    ? 'bg-white/10 font-semibold text-white'
                    : 'text-slate-300 hover:bg-white/5 hover:text-white'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  {/* Franja de color a la izquierda de la opción activa. */}
                  <span
                    aria-hidden="true"
                    className={`absolute top-1/2 left-0 hidden h-6 w-1 -translate-y-1/2 rounded-r-full bg-indigo-400 transition-opacity md:block ${
                      isActive ? 'opacity-100' : 'opacity-0'
                    }`}
                  />
                  <Icono
                    className={`size-5 shrink-0 ${isActive ? 'text-indigo-300' : 'text-slate-400 group-hover:text-slate-200'}`}
                  />
                  <span className="flex flex-col leading-tight">
                    <span>{texto}</span>
                    <span aria-hidden="true" className="hidden text-xs font-normal text-slate-400 md:block">
                      {ayuda}
                    </span>
                  </span>
                </>
              )}
            </NavLink>
          ))}
        </nav>

        {/* Pie: tema y estado de la API */}
        <div className="ml-auto flex items-center gap-2 md:mt-auto md:ml-0 md:flex-col md:items-stretch md:gap-3">
          <button
            type="button"
            role="switch"
            aria-checked={oscuro}
            aria-label="Modo oscuro"
            onClick={alternarTema}
            className="flex items-center gap-3 rounded-lg px-2 py-1.5 text-xs text-slate-300 hover:bg-white/5 focus-visible:outline-2 focus-visible:outline-indigo-400 md:px-3 md:py-2"
          >
            <span
              aria-hidden="true"
              className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors ${
                oscuro ? 'bg-indigo-500' : 'bg-slate-600'
              }`}
            >
              <span
                className={`flex size-4 items-center justify-center rounded-full bg-white text-slate-700 shadow transition-transform ${
                  oscuro ? 'translate-x-4.5' : 'translate-x-0.5'
                }`}
              >
                {oscuro ? <IconoLuna className="size-3" /> : <IconoSol className="size-3" />}
              </span>
            </span>
            <span className="hidden md:inline">{oscuro ? 'Modo oscuro' : 'Modo claro'}</span>
          </button>

          <div
            className="rounded-xl bg-white/5 px-3 py-2 ring-1 ring-white/10 md:p-3"
            aria-live="polite"
          >
            <p className="flex items-center gap-2 text-xs font-medium text-slate-200">
              <span aria-hidden="true" className="relative flex size-2.5">
                {estado.conectada && (
                  <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-400 opacity-60" />
                )}
                <span
                  className={`relative inline-flex size-2.5 rounded-full ${
                    estado.conectada === null
                      ? 'bg-slate-500'
                      : estado.conectada
                        ? 'bg-emerald-400'
                        : 'bg-rose-500'
                  }`}
                />
              </span>
              API:{' '}
              {estado.conectada === null ? 'comprobando…' : estado.conectada ? 'activa' : 'sin conexión'}
            </p>
            {estado.modelo && (
              <p className="mt-2 hidden text-[11px] leading-snug text-slate-400 md:block">
                <span className="block font-semibold tracking-wider text-slate-500 uppercase">Modelo activo</span>
                {estado.modelo}
              </p>
            )}
          </div>
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
