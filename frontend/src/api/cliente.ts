// Cliente HTTP de la API. Las rutas son relativas: Vite (desarrollo) y Nginx (Docker) las
// redirigen a FastAPI, así que el frontend nunca escribe la URL del backend.
import type {
  Categorias,
  Clasificacion,
  ClasificacionDetalle,
  EntradaCorreccion,
  FiltrosHistorial,
  MetricasModelo,
  Modelo,
  PaginaHistorial,
  Particion,
  RespuestaSalud,
} from '@/api/tipos'

export type * from '@/api/tipos'

const BASE = '/api/v1'

/** Error con el formato del contrato: `{"error": {"codigo", "mensaje"}}`. */
export class ErrorApi extends Error {
  readonly codigo: string
  readonly estado: number

  constructor(codigo: string, mensaje: string, estado: number) {
    super(mensaje)
    this.name = 'ErrorApi'
    this.codigo = codigo
    this.estado = estado
  }
}

/** Código usado cuando la API no responde (apagada, sin red). */
export const SIN_CONEXION = 'SIN_CONEXION'

async function solicitar<T>(ruta: string, opciones?: RequestInit): Promise<T> {
  let respuesta: Response
  try {
    respuesta = await fetch(`${BASE}${ruta}`, opciones)
  } catch {
    throw new ErrorApi(SIN_CONEXION, 'No se pudo conectar con la API.', 0)
  }
  if (!respuesta.ok) {
    let codigo = 'ERROR_DESCONOCIDO'
    let mensaje = `La API respondió con el error ${respuesta.status}.`
    try {
      const cuerpo = (await respuesta.json()) as { error?: { codigo?: string; mensaje?: string } }
      codigo = cuerpo.error?.codigo ?? codigo
      mensaje = cuerpo.error?.mensaje ?? mensaje
    } catch {
      // La respuesta no era JSON (p. ej. un proxy caído): se deja el mensaje genérico.
    }
    throw new ErrorApi(codigo, mensaje, respuesta.status)
  }
  return (await respuesta.json()) as T
}

function enviarJson<T>(ruta: string, cuerpo: unknown): Promise<T> {
  return solicitar<T>(ruta, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(cuerpo),
  })
}

function consulta(filtros: object): string {
  const parametros = new URLSearchParams()
  for (const [clave, valor] of Object.entries(filtros)) {
    if (valor !== undefined && valor !== null && valor !== '') parametros.set(clave, String(valor))
  }
  const texto = parametros.toString()
  return texto ? `?${texto}` : ''
}

export const api = {
  salud: () => solicitar<RespuestaSalud>('/salud'),
  categorias: () => solicitar<Categorias>('/categorias'),

  clasificarTexto: (texto: string, titulo?: string) =>
    enviarJson<Clasificacion>('/clasificaciones/texto', { texto, titulo: titulo || null }),
  clasificarArchivo: (archivo: File) => {
    const formulario = new FormData()
    formulario.append('archivo', archivo)
    return solicitar<Clasificacion>('/clasificaciones/archivo', {
      method: 'POST',
      body: formulario,
    })
  },

  historial: (filtros: FiltrosHistorial = {}) =>
    solicitar<PaginaHistorial>(`/clasificaciones${consulta(filtros)}`),
  clasificacion: (id: number) => solicitar<ClasificacionDetalle>(`/clasificaciones/${id}`),
  corregir: (id: number, entrada: EntradaCorreccion) =>
    enviarJson<ClasificacionDetalle>(`/clasificaciones/${id}/correccion`, entrada),

  modelos: () => solicitar<Modelo[]>('/modelos'),
  metricas: (id: number, particion?: Particion) =>
    solicitar<MetricasModelo>(`/modelos/${id}/metricas${consulta({ particion })}`),
}
