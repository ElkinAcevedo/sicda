import { type FormEvent, useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api, type FilaHistorial, type FiltrosHistorial } from '@/api/cliente'
import {
  Aviso,
  Boton,
  Cargando,
  EncabezadoPagina,
  EstadoError,
  InsigniaDominio,
  Tarjeta,
} from '@/components/ui'
import { CLASES_CONFIANZA, fechaCorta, nivelConfianza, porcentaje } from '@/lib/formato'
import { useCarga, useCategorias } from '@/lib/hooks'

const TAMANO_PAGINA = 20
const CAMPOS = ['busqueda', 'dominio', 'desde', 'hasta', 'requiere_revision'] as const
type Campo = (typeof CAMPOS)[number]

/** Los filtros viven en la URL (?dominio=…&pagina=2) para poder recargar o compartir la vista. */
function filtrosDesdeUrl(parametros: URLSearchParams): FiltrosHistorial {
  const revision = parametros.get('requiere_revision')
  return {
    pagina: Number(parametros.get('pagina')) || 1,
    tamano: TAMANO_PAGINA,
    busqueda: parametros.get('busqueda') || undefined,
    dominio: parametros.get('dominio') || undefined,
    desde: parametros.get('desde') || undefined,
    hasta: parametros.get('hasta') || undefined,
    requiere_revision: revision === 'true' ? true : revision === 'false' ? false : undefined,
  }
}

export function Historial() {
  const [parametros, setParametros] = useSearchParams()
  const filtros = filtrosDesdeUrl(parametros)
  const clave = parametros.toString()
  const { datos, error, cargando, recargar } = useCarga(() => api.historial(filtros), [clave])

  function irAPagina(pagina: number) {
    const siguiente = new URLSearchParams(parametros)
    siguiente.set('pagina', String(pagina))
    setParametros(siguiente)
  }

  return (
    <section>
      <EncabezadoPagina
        titulo="Historial"
        descripcion="Todas las clasificaciones guardadas, de la más reciente a la más antigua."
      />
      <Filtros
        valores={parametros}
        onAplicar={(nuevos) => setParametros(nuevos)}
        onLimpiar={() => setParametros(new URLSearchParams())}
      />

      <div className="mt-4">
        {cargando && !datos && <Cargando />}
        {error !== null && <EstadoError error={error} reintentar={recargar} />}
        {datos && datos.total === 0 && (
          <Aviso tono="info" titulo={clave ? 'Ningún resultado con estos filtros' : 'Todavía no hay clasificaciones'}>
            {clave ? (
              'Prueba con otros filtros o límpialos.'
            ) : (
              <>
                Ve a <Link to="/" className="font-medium underline">Clasificar</Link> para empezar.
              </>
            )}
          </Aviso>
        )}
        {datos && datos.total > 0 && (
          <>
            <TablaHistorial filas={datos.elementos} />
            <nav
              aria-label="Paginación"
              className="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm text-slate-600 dark:text-slate-400"
            >
              <p>
                {datos.total} clasificaciones · página {datos.pagina} de {datos.paginas}
              </p>
              <div className="flex gap-2">
                <Boton
                  variante="secundario"
                  disabled={datos.pagina <= 1}
                  onClick={() => irAPagina(datos.pagina - 1)}
                >
                  ← Anterior
                </Boton>
                <Boton
                  variante="secundario"
                  disabled={datos.pagina >= datos.paginas}
                  onClick={() => irAPagina(datos.pagina + 1)}
                >
                  Siguiente →
                </Boton>
              </div>
            </nav>
          </>
        )}
      </div>
    </section>
  )
}

function Filtros({
  valores,
  onAplicar,
  onLimpiar,
}: {
  valores: URLSearchParams
  onAplicar: (parametros: URLSearchParams) => void
  onLimpiar: () => void
}) {
  const { categorias } = useCategorias()
  const leer = () => Object.fromEntries(CAMPOS.map((c) => [c, valores.get(c) ?? ''])) as Record<Campo, string>
  const [borrador, setBorrador] = useState(leer)
  const clave = valores.toString()

  // Si la URL cambia (atrás/adelante en el navegador), el formulario la refleja.
  // eslint-disable-next-line react-hooks/exhaustive-deps -- `leer` depende solo de `clave`
  useEffect(() => setBorrador(leer()), [clave])

  function cambiar(campo: Campo, valor: string) {
    setBorrador((previo) => ({ ...previo, [campo]: valor }))
  }

  function aplicar(evento: FormEvent) {
    evento.preventDefault()
    const nuevos = new URLSearchParams()
    for (const campo of CAMPOS) if (borrador[campo]) nuevos.set(campo, borrador[campo])
    onAplicar(nuevos) // sin «pagina»: un filtro nuevo vuelve a la primera página
  }

  const clasesCampo =
    'rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-normal dark:border-slate-700 dark:bg-slate-950'

  return (
    <Tarjeta>
      <form onSubmit={aplicar} aria-label="Filtros del historial" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
        <label className="flex flex-col gap-1 text-xs font-medium lg:col-span-2">
          Buscar
          <input
            type="search"
            value={borrador.busqueda}
            onChange={(evento) => cambiar('busqueda', evento.target.value)}
            placeholder="Título o nombre de archivo"
            className={clasesCampo}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium">
          Dominio
          <select
            value={borrador.dominio}
            onChange={(evento) => cambiar('dominio', evento.target.value)}
            className={clasesCampo}
          >
            <option value="">Todos</option>
            {categorias?.dominios.map((d) => (
              <option key={d.id} value={d.nombre}>
                {d.nombre}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium">
          Estado
          <select
            value={borrador.requiere_revision}
            onChange={(evento) => cambiar('requiere_revision', evento.target.value)}
            className={clasesCampo}
          >
            <option value="">Todos</option>
            <option value="true">Requiere revisión</option>
            <option value="false">Confiable</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium">
          Desde
          <input
            type="date"
            value={borrador.desde}
            onChange={(evento) => cambiar('desde', evento.target.value)}
            className={clasesCampo}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium">
          Hasta
          <input
            type="date"
            value={borrador.hasta}
            onChange={(evento) => cambiar('hasta', evento.target.value)}
            className={clasesCampo}
          />
        </label>
        <div className="flex gap-2 sm:col-span-2 lg:col-span-6 lg:justify-end">
          <Boton variante="fantasma" onClick={onLimpiar}>
            Limpiar
          </Boton>
          <Boton type="submit">Filtrar</Boton>
        </div>
      </form>
    </Tarjeta>
  )
}

function Estado({ fila }: { fila: FilaHistorial }) {
  if (fila.correccion) {
    return (
      <span className="rounded-full whitespace-nowrap bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200">
        Corregida
      </span>
    )
  }
  if (fila.requiere_revision) {
    return (
      <span className="rounded-full whitespace-nowrap bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-950 dark:text-amber-200">
        Requiere revisión
      </span>
    )
  }
  return (
    <span className="rounded-full whitespace-nowrap bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700 dark:bg-slate-800 dark:text-slate-300">
      Confiable
    </span>
  )
}

function TablaHistorial({ filas }: { filas: FilaHistorial[] }) {
  const navegar = useNavigate()
  const { color } = useCategorias()
  const encabezado = 'px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase dark:text-slate-400'

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      <table className="w-full min-w-[720px] text-sm">
        <thead className="border-b border-slate-200 dark:border-slate-800">
          <tr>
            <th scope="col" className={encabezado}>Fecha</th>
            <th scope="col" className={encabezado}>Documento</th>
            <th scope="col" className={encabezado}>Dominio</th>
            <th scope="col" className={encabezado}>Área</th>
            <th scope="col" className={`${encabezado} text-right`}>Confianza</th>
            <th scope="col" className={encabezado}>Estado</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
          {filas.map((fila) => (
            <tr
              key={fila.id}
              onClick={() => navegar(`/resultado/${fila.id}`)}
              className="cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/60"
            >
              <td className="px-4 py-3 whitespace-nowrap text-slate-500">{fechaCorta(fila.creado_en)}</td>
              <td className="max-w-72 truncate px-4 py-3 font-medium">
                {/* El enlace hace la fila accesible con el teclado. */}
                <Link to={`/resultado/${fila.id}`} className="hover:underline focus-visible:outline-2 focus-visible:outline-indigo-600">
                  {fila.documento.titulo || fila.documento.nombre_archivo || 'Texto sin título'}
                </Link>
              </td>
              <td className="px-4 py-3 whitespace-nowrap">
                <InsigniaDominio nombre={fila.dominio} color={color(fila.dominio)} />
              </td>
              <td className="px-4 py-3">{fila.area}</td>
              <td
                className={`px-4 py-3 text-right font-semibold tabular-nums ${
                  CLASES_CONFIANZA[nivelConfianza(fila.confianza_conjunta)].texto
                }`}
              >
                {porcentaje(fila.confianza_conjunta)}
              </td>
              <td className="px-4 py-3">
                <Estado fila={fila} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
