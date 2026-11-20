import { useEffect, useState } from 'react'

const ETAPAS = ['Extrayendo texto', 'Analizando el resumen', 'Clasificando'] as const

/** Milisegundos tras los que se pasa a la etapa siguiente (la API responde de una vez). */
const DURACION_ETAPA = 400

/** Progreso por etapas mientras la API procesa (extrayendo → analizando → clasificando). */
export function ProgresoEtapas() {
  const [etapa, setEtapa] = useState(0)

  useEffect(() => {
    const temporizador = setInterval(
      () => setEtapa((e) => Math.min(e + 1, ETAPAS.length - 1)),
      DURACION_ETAPA,
    )
    return () => clearInterval(temporizador)
  }, [])

  return (
    <ol aria-label="Progreso de la clasificación" className="flex flex-col gap-2 sm:flex-row sm:gap-6">
      {ETAPAS.map((nombre, i) => {
        const estado = i < etapa ? 'hecha' : i === etapa ? 'actual' : 'pendiente'
        return (
          <li
            key={nombre}
            aria-current={estado === 'actual' ? 'step' : undefined}
            className={`flex items-center gap-2 text-sm ${
              estado === 'pendiente' ? 'text-slate-400 dark:text-slate-500' : ''
            } ${estado === 'actual' ? 'font-semibold text-indigo-700 dark:text-indigo-300' : ''}`}
          >
            <span
              aria-hidden="true"
              className={`flex size-5 items-center justify-center rounded-full text-xs ${
                estado === 'hecha'
                  ? 'bg-emerald-500 text-white'
                  : estado === 'actual'
                    ? 'animate-pulse bg-indigo-600 text-white'
                    : 'bg-slate-200 dark:bg-slate-700'
              }`}
            >
              {estado === 'hecha' ? '✓' : i + 1}
            </span>
            {nombre}
          </li>
        )
      })}
    </ol>
  )
}
