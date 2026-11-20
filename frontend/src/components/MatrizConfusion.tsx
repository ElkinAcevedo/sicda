import { useState } from 'react'
import type { MatrizConfusion as Matriz } from '@/api/cliente'
import { porcentaje } from '@/lib/formato'

/**
 * Matriz de confusión interactiva: filas = clase real, columnas = clase predicha.
 * El color es la proporción de la fila (cuántos documentos de esa clase fueron a cada columna).
 * Al pasar el ratón o enfocar una celda con el teclado se explica qué significa.
 */
export function MatrizConfusion({
  matriz,
  abreviar = (nombre) => nombre,
  colorFila,
  titulo,
}: {
  matriz: Matriz
  abreviar?: (nombre: string) => string
  colorFila?: (nombre: string) => string
  titulo: string
}) {
  const [modo, setModo] = useState<'porcentaje' | 'conteo'>('porcentaje')
  const [celda, setCelda] = useState<{ fila: number; columna: number } | null>(null)
  const totales = matriz.matriz.map((fila) => fila.reduce((suma, valor) => suma + valor, 0))

  const descripcion = (fila: number, columna: number) => {
    const valor = matriz.matriz[fila][columna]
    const real = matriz.etiquetas[fila]
    const predicha = matriz.columnas[columna]
    const parte = totales[fila] ? valor / totales[fila] : 0
    return real === predicha
      ? `${valor} de ${totales[fila]} documentos de «${real}» se clasificaron bien (${porcentaje(parte, 1)}).`
      : `${valor} de ${totales[fila]} documentos de «${real}» se enviaron a «${predicha}» (${porcentaje(parte, 1)}).`
  }

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-slate-500 dark:text-slate-400">
          Filas: categoría real · columnas: categoría predicha
        </p>
        <div role="group" aria-label="Valores de la matriz" className="flex gap-1 text-xs">
          {(['porcentaje', 'conteo'] as const).map((valor) => (
            <button
              key={valor}
              type="button"
              aria-pressed={modo === valor}
              onClick={() => setModo(valor)}
              className={`rounded-md px-2 py-1 ${
                modo === valor
                  ? 'bg-indigo-600 text-white'
                  : 'bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300'
              }`}
            >
              {valor === 'porcentaje' ? '% por fila' : 'Documentos'}
            </button>
          ))}
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="border-separate border-spacing-0.5 text-xs" aria-label={titulo}>
          <thead>
            <tr>
              <th scope="col" className="sr-only">
                Real
              </th>
              {matriz.columnas.map((columna) => (
                <th
                  key={columna}
                  scope="col"
                  title={columna}
                  className="max-w-20 truncate px-1 pb-1 font-medium text-slate-600 dark:text-slate-400"
                >
                  {abreviar(columna)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {matriz.matriz.map((fila, i) => (
              <tr key={matriz.etiquetas[i]}>
                <th
                  scope="row"
                  title={matriz.etiquetas[i]}
                  className="max-w-40 truncate pr-2 text-right font-medium text-slate-600 dark:text-slate-400"
                >
                  {colorFila && (
                    <span
                      aria-hidden="true"
                      className="mr-1.5 inline-block size-2 rounded-full"
                      style={{ backgroundColor: colorFila(matriz.etiquetas[i]) }}
                    />
                  )}
                  {abreviar(matriz.etiquetas[i])}
                </th>
                {fila.map((valor, j) => {
                  const parte = totales[i] ? valor / totales[i] : 0
                  const diagonal = matriz.etiquetas[i] === matriz.columnas[j]
                  const activa = celda?.fila === i && celda?.columna === j
                  return (
                    <td
                      key={j}
                      tabIndex={0}
                      aria-label={descripcion(i, j)}
                      onMouseEnter={() => setCelda({ fila: i, columna: j })}
                      onFocus={() => setCelda({ fila: i, columna: j })}
                      className={`size-12 min-w-12 rounded text-center tabular-nums outline-offset-1 focus-visible:outline-2 focus-visible:outline-indigo-600 ${
                        activa ? 'ring-2 ring-slate-900 dark:ring-white' : ''
                      } ${parte > 0.55 ? 'text-white' : 'text-slate-800 dark:text-slate-200'}`}
                      style={{
                        backgroundColor: diagonal
                          ? `rgba(79, 70, 229, ${0.08 + parte * 0.92})`
                          : `rgba(225, 29, 72, ${parte === 0 ? 0 : 0.1 + parte * 0.9})`,
                      }}
                    >
                      {modo === 'porcentaje' ? Math.round(parte * 100) : valor}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3 min-h-5 text-sm text-slate-700 dark:text-slate-300" aria-live="polite">
        {celda
          ? descripcion(celda.fila, celda.columna)
          : 'Pasa el ratón o usa Tab sobre una celda para ver el detalle.'}
      </p>
    </div>
  )
}
