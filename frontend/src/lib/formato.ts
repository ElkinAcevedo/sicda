// Formato de números, fechas, colores de confianza y colores por dominio (sección 8 del diseño).

export function porcentaje(valor: number | null | undefined, decimales = 0): string {
  if (valor === null || valor === undefined || Number.isNaN(valor)) return '—'
  return `${(valor * 100).toFixed(decimales).replace('.', ',')} %`
}

export function decimal(valor: number | null | undefined, decimales = 3): string {
  if (valor === null || valor === undefined || Number.isNaN(valor)) return '—'
  return valor.toFixed(decimales).replace('.', ',')
}

/** La API guarda las fechas en UTC sin zona: se marcan como UTC antes de convertirlas. */
export function aFecha(iso: string): Date {
  return new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`)
}

export function fechaHora(iso: string): string {
  return aFecha(iso).toLocaleString('es-CO', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** Fecha corta para tablas: 19/11/2026 23:01. */
export function fechaCorta(iso: string): string {
  return aFecha(iso).toLocaleString('es-CO', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

export type NivelConfianza = 'alta' | 'media' | 'baja'

/** Verde ≥ 70 %, ámbar 40–70 %, rojo < 40 % (principio «la respuesta en un vistazo»). */
export function nivelConfianza(valor: number): NivelConfianza {
  if (valor >= 0.7) return 'alta'
  if (valor >= 0.4) return 'media'
  return 'baja'
}

export const CLASES_CONFIANZA: Record<NivelConfianza, { barra: string; texto: string }> = {
  alta: { barra: 'bg-emerald-500', texto: 'text-emerald-700 dark:text-emerald-400' },
  media: { barra: 'bg-amber-500', texto: 'text-amber-700 dark:text-amber-400' },
  baja: { barra: 'bg-rose-500', texto: 'text-rose-700 dark:text-rose-400' },
}

/** Un color fijo por dominio, en el orden de `categorias.json` (ids 0 a 6). */
const PALETA_DOMINIOS = [
  '#4f46e5', // índigo · Computer Science
  '#0891b2', // cian · Electrical and Computer Engineering
  '#db2777', // rosa · Psychology
  '#ea580c', // naranja · Mechanical and Aerospace Engineering
  '#65a30d', // lima · Civil Engineering
  '#dc2626', // rojo · Medical Sciences
  '#7c3aed', // violeta · Biochemistry
]

export const COLOR_SIN_DOMINIO = '#64748b'

export function colorDominio(id: number | undefined): string {
  if (id === undefined || id < 0) return COLOR_SIN_DOMINIO
  return PALETA_DOMINIOS[id % PALETA_DOMINIOS.length]
}

const ETIQUETAS_FUENTE: Record<string, string> = {
  abstract: 'Resumen (Abstract) encontrado',
  inicio: 'Inicio del documento',
  texto_completo: 'Texto completo',
}

export function etiquetaFuente(fuente: string): string {
  return ETIQUETAS_FUENTE[fuente] ?? fuente
}

const IDIOMAS: Record<string, string> = { en: 'inglés', es: 'español', pt: 'portugués', fr: 'francés' }

export function nombreIdioma(codigo: string): string {
  return IDIOMAS[codigo] ?? codigo
}
