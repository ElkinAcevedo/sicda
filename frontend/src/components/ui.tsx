// Componentes visuales básicos (tarjetas, botones, insignias, avisos y estados).
import type { ButtonHTMLAttributes, CSSProperties, ReactNode } from 'react'
import { mensajeError } from '@/lib/errores'
import { CLASES_CONFIANZA, nivelConfianza, porcentaje } from '@/lib/formato'

export function Tarjeta({
  children,
  className = '',
  style,
}: {
  children: ReactNode
  className?: string
  style?: CSSProperties
}) {
  return (
    <div
      style={style}
      className={`rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900 ${className}`}
    >
      {children}
    </div>
  )
}

export function TituloSeccion({ children }: { children: ReactNode }) {
  return (
    <h2 className="text-sm font-semibold tracking-wide text-slate-500 uppercase dark:text-slate-400">
      {children}
    </h2>
  )
}

type VarianteBoton = 'primario' | 'secundario' | 'fantasma'

const CLASES_BOTON: Record<VarianteBoton, string> = {
  primario:
    'bg-indigo-600 text-white hover:bg-indigo-700 disabled:bg-indigo-300 dark:disabled:bg-indigo-900',
  secundario:
    'border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800',
  fantasma: 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800',
}

export function Boton({
  variante = 'primario',
  className = '',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variante?: VarianteBoton }) {
  return (
    <button
      type="button"
      className={`inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600 disabled:cursor-not-allowed ${CLASES_BOTON[variante]} ${className}`}
      {...props}
    />
  )
}

/** Punto de color + nombre del dominio. */
export function InsigniaDominio({
  nombre,
  color,
  etiqueta,
}: {
  nombre: string
  color: string
  etiqueta?: string
}) {
  return (
    <span className="inline-flex items-center gap-1.5" title={nombre}>
      <span
        aria-hidden="true"
        className="size-2.5 shrink-0 rounded-full"
        style={{ backgroundColor: color }}
      />
      <span>{etiqueta ?? nombre}</span>
    </span>
  )
}

/** Barra de confianza con el color de su rango (verde, ámbar o rojo). */
export function BarraConfianza({
  valor,
  etiqueta,
  grande = false,
}: {
  valor: number
  etiqueta: string
  grande?: boolean
}) {
  const clases = CLASES_CONFIANZA[nivelConfianza(valor)]
  return (
    <div className="flex items-center gap-3">
      <div
        role="meter"
        aria-label={etiqueta}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(valor * 100)}
        className={`flex-1 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800 ${grande ? 'h-3' : 'h-2'}`}
      >
        <div className={`h-full rounded-full ${clases.barra}`} style={{ width: `${valor * 100}%` }} />
      </div>
      <span className={`w-12 text-right text-sm font-semibold tabular-nums ${clases.texto}`}>
        {porcentaje(valor)}
      </span>
    </div>
  )
}

type TonoAviso = 'info' | 'advertencia' | 'error' | 'exito'

const CLASES_AVISO: Record<TonoAviso, string> = {
  info: 'border-sky-200 bg-sky-50 text-sky-900 dark:border-sky-900 dark:bg-sky-950 dark:text-sky-100',
  advertencia:
    'border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-100',
  error:
    'border-rose-200 bg-rose-50 text-rose-900 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-100',
  exito:
    'border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-100',
}

export function Aviso({
  tono = 'info',
  titulo,
  children,
}: {
  tono?: TonoAviso
  titulo?: string
  children?: ReactNode
}) {
  return (
    <div
      role={tono === 'error' ? 'alert' : 'status'}
      className={`rounded-lg border px-4 py-3 text-sm ${CLASES_AVISO[tono]}`}
    >
      {titulo && <p className="font-semibold">{titulo}</p>}
      {children && <div className={titulo ? 'mt-1' : ''}>{children}</div>}
    </div>
  )
}

export function EstadoError({ error, reintentar }: { error: unknown; reintentar?: () => void }) {
  const { mensaje, accion } = mensajeError(error)
  return (
    <Aviso tono="error" titulo={mensaje}>
      {accion && <p>{accion}</p>}
      {reintentar && (
        <Boton variante="secundario" className="mt-3" onClick={reintentar}>
          Reintentar
        </Boton>
      )}
    </Aviso>
  )
}

export function Cargando({ texto = 'Cargando…' }: { texto?: string }) {
  return (
    <p role="status" className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
      <span
        aria-hidden="true"
        className="size-4 animate-spin rounded-full border-2 border-slate-300 border-t-indigo-600"
      />
      {texto}
    </p>
  )
}

export function EncabezadoPagina({
  titulo,
  descripcion,
  acciones,
}: {
  titulo: string
  descripcion?: string
  acciones?: ReactNode
}) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{titulo}</h1>
        {descripcion && <p className="mt-1 text-slate-600 dark:text-slate-400">{descripcion}</p>}
      </div>
      {acciones}
    </header>
  )
}
