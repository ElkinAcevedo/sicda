import { useMemo, useState } from 'react'
import type { MetricaClase } from '@/api/cliente'
import { InsigniaDominio } from '@/components/ui'
import { CLASES_CONFIANZA, decimal, nivelConfianza } from '@/lib/formato'

type Columna = 'nombre' | 'dominio' | 'precision' | 'recall' | 'f1' | 'soporte'

const COLUMNAS: { clave: Columna; titulo: string; numerica: boolean }[] = [
  { clave: 'nombre', titulo: 'Área', numerica: false },
  { clave: 'dominio', titulo: 'Dominio', numerica: false },
  { clave: 'precision', titulo: 'Precisión', numerica: true },
  { clave: 'recall', titulo: 'Recall', numerica: true },
  { clave: 'f1', titulo: 'F1', numerica: true },
  { clave: 'soporte', titulo: 'Documentos', numerica: true },
]

/** F1 por área, ordenable por cualquier columna y filtrable por dominio o nombre. */
export function TablaAreas({
  areas,
  color,
}: {
  areas: MetricaClase[]
  color: (dominio: string) => string
}) {
  const [orden, setOrden] = useState<{ columna: Columna; ascendente: boolean }>({
    columna: 'f1',
    ascendente: true, // primero las peores: son las que interesa revisar
  })
  const [dominio, setDominio] = useState('')
  const [busqueda, setBusqueda] = useState('')

  const dominios = useMemo(
    () => [...new Set(areas.map((a) => a.dominio ?? ''))].filter(Boolean).sort(),
    [areas],
  )

  const filas = useMemo(() => {
    const texto = busqueda.trim().toLowerCase()
    const filtradas = areas.filter(
      (a) => (!dominio || a.dominio === dominio) && (!texto || a.nombre.toLowerCase().includes(texto)),
    )
    const signo = orden.ascendente ? 1 : -1
    return filtradas.sort((a, b) => {
      const x = a[orden.columna] ?? ''
      const y = b[orden.columna] ?? ''
      if (typeof x === 'number' && typeof y === 'number') return (x - y) * signo
      return String(x).localeCompare(String(y), 'es') * signo
    })
  }, [areas, dominio, busqueda, orden])

  function ordenarPor(columna: Columna) {
    setOrden((previo) =>
      previo.columna === columna
        ? { columna, ascendente: !previo.ascendente }
        : { columna, ascendente: columna === 'nombre' || columna === 'dominio' || columna === 'f1' },
    )
  }

  const clasesCampo =
    'rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-950'

  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-2">
        <label className="flex items-center gap-2 text-xs font-medium">
          Dominio
          <select value={dominio} onChange={(e) => setDominio(e.target.value)} className={clasesCampo}>
            <option value="">Todos</option>
            {dominios.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 text-xs font-medium">
          Área
          <input
            type="search"
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
            placeholder="Buscar área"
            className={clasesCampo}
          />
        </label>
        <p className="ml-auto self-center text-xs text-slate-500">{filas.length} áreas</p>
      </div>
      <div className="max-h-[28rem] overflow-auto rounded-lg border border-slate-200 dark:border-slate-800">
        <table className="w-full min-w-[640px] text-sm">
          <thead className="sticky top-0 bg-slate-50 dark:bg-slate-900">
            <tr>
              {COLUMNAS.map(({ clave, titulo, numerica }) => {
                const activa = orden.columna === clave
                return (
                  <th
                    key={clave}
                    scope="col"
                    aria-sort={activa ? (orden.ascendente ? 'ascending' : 'descending') : 'none'}
                    className={`px-3 py-2 text-xs font-semibold text-slate-600 dark:text-slate-300 ${numerica ? 'text-right' : 'text-left'}`}
                  >
                    <button
                      type="button"
                      onClick={() => ordenarPor(clave)}
                      className="inline-flex items-center gap-1 hover:text-indigo-700 dark:hover:text-indigo-300"
                    >
                      {titulo}
                      <span aria-hidden="true">{activa ? (orden.ascendente ? '▲' : '▼') : '↕'}</span>
                    </button>
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {filas.map((area) => (
              <tr key={area.id}>
                <td className="px-3 py-2">{area.nombre}</td>
                <td className="px-3 py-2 whitespace-nowrap text-slate-600 dark:text-slate-400">
                  {area.dominio && <InsigniaDominio nombre={area.dominio} color={color(area.dominio)} />}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">{decimal(area.precision)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{decimal(area.recall)}</td>
                <td
                  className={`px-3 py-2 text-right font-semibold tabular-nums ${CLASES_CONFIANZA[nivelConfianza(area.f1)].texto}`}
                >
                  {decimal(area.f1)}
                </td>
                <td className="px-3 py-2 text-right tabular-nums text-slate-500">{area.soporte}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
