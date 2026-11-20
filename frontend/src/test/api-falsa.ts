// API falsa para las pruebas: responde a `fetch` según el método y la ruta.
import { vi } from 'vitest'
import type {
  Categorias,
  ClasificacionDetalle,
  FilaHistorial,
  MetricasModelo,
  Modelo,
  PaginaHistorial,
} from '@/api/cliente'
import { reiniciarCategorias } from '@/lib/hooks'

type Respuesta = { estado?: number; cuerpo: unknown }
type Manejador = (url: URL, init?: RequestInit) => Respuesta | Promise<Respuesta>

export interface Llamada {
  metodo: string
  ruta: string
  parametros: URLSearchParams
  cuerpo: unknown
}

/**
 * Reemplaza `fetch`. Las claves son «MÉTODO /ruta» (sin /api/v1); una ruta con `:id`
 * acepta cualquier número. Devuelve la lista de llamadas para comprobarlas.
 */
export function simularApi(rutas: Record<string, Manejador | Respuesta>): Llamada[] {
  reiniciarCategorias()
  const llamadas: Llamada[] = []
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (entrada, init) => {
    const url = new URL(String(entrada), 'http://localhost')
    const metodo = (init?.method ?? 'GET').toUpperCase()
    const ruta = url.pathname.replace('/api/v1', '')
    let cuerpo: unknown = init?.body
    if (typeof cuerpo === 'string') cuerpo = JSON.parse(cuerpo)
    llamadas.push({ metodo, ruta, parametros: url.searchParams, cuerpo })

    const clave = Object.keys(rutas).find((patron) => {
      const [m, p] = patron.split(' ')
      const expresion = new RegExp(`^${p.replace(/:id/g, '\\d+')}$`)
      return m === metodo && expresion.test(ruta)
    })
    const definida = clave ? rutas[clave] : { estado: 404, cuerpo: ERROR_NO_ENCONTRADO }
    const { estado = 200, cuerpo: respuesta } =
      typeof definida === 'function' ? await definida(url, init) : definida
    return new Response(JSON.stringify(respuesta), {
      status: estado,
      headers: { 'Content-Type': 'application/json' },
    })
  })
  return llamadas
}

export function error(codigo: string, mensaje: string, estado: number): Respuesta {
  return { estado, cuerpo: { error: { codigo, mensaje } } }
}

const ERROR_NO_ENCONTRADO = { error: { codigo: 'NO_ENCONTRADO', mensaje: 'No existe.' } }

export const CATEGORIAS: Categorias = {
  total_dominios: 2,
  total_areas: 3,
  dominios: [
    {
      id: 0,
      codigo: 'CS',
      nombre: 'Computer Science',
      nombre_es: 'Ciencias de la computación',
      documentos: 600,
      areas: [
        { id: 0, nombre: 'Computer vision', documentos: 300 },
        { id: 1, nombre: 'Machine learning', documentos: 300 },
      ],
    },
    {
      id: 5,
      codigo: 'Medical',
      nombre: 'Medical Sciences',
      nombre_es: 'Ciencias médicas',
      documentos: 400,
      areas: [{ id: 2, nombre: 'Cancer', documentos: 400 }],
    },
  ],
}

export const CLASIFICACION: ClasificacionDetalle = {
  id: 7,
  documento: {
    titulo: 'Redes ligeras',
    nombre_archivo: null,
    idioma: 'en',
    num_terminos: 42,
    fuente_texto: 'texto_completo',
    tipo: 'texto',
    texto_extraido: 'Convolutional networks are trained for image segmentation.',
    palabras_clave: [],
  },
  dominio: {
    nombre: 'Computer Science',
    confianza: 0.92,
    alternativas: [
      { nombre: 'Computer Science', confianza: 0.92 },
      { nombre: 'Medical Sciences', confianza: 0.08 },
    ],
  },
  area: {
    nombre: 'Computer vision',
    confianza: 0.55,
    alternativas: [
      { nombre: 'Computer vision', confianza: 0.55 },
      { nombre: 'Machine learning', confianza: 0.45 },
    ],
  },
  confianza_conjunta: 0.506,
  requiere_revision: false,
  terminos_clave: [
    { termino: 'convolutional', peso: 0.3 },
    { termino: 'train', peso: 0.1 },
  ],
  advertencias: [],
  modelo: { nombre: 'TF-IDF + SVM lineal (plano)', version: 'v1' },
  tiempo_ms: 210,
  creado_en: '2026-11-19T15:00:00',
  correccion: null,
}

export function fila(id: number, cambios: Partial<FilaHistorial> = {}): FilaHistorial {
  return {
    id,
    creado_en: '2026-11-19T15:00:00',
    documento: { titulo: `Artículo ${id}`, nombre_archivo: null, tipo: 'texto' },
    dominio: 'Computer Science',
    area: 'Computer vision',
    confianza_dominio: 0.9,
    confianza_conjunta: 0.8,
    requiere_revision: false,
    correccion: null,
    ...cambios,
  }
}

export function pagina(elementos: FilaHistorial[], cambios: Partial<PaginaHistorial> = {}): PaginaHistorial {
  return { elementos, total: elementos.length, pagina: 1, tamano: 20, paginas: 1, ...cambios }
}

const RESUMEN = { f1_dominio: 0.9, f1_area: 0.78, f1_jerarquico: 0.78, accuracy_jerarquica: 0.8 }

export const MODELOS: Modelo[] = [
  {
    id: 3,
    nombre: 'TF-IDF + SVM lineal (plano)',
    algoritmo: 'linear_svc',
    tipo: 'plano',
    version: 'v1',
    activo: true,
    entrenado_en: '2026-11-19T15:55:00',
    hiperparametros: {},
    validacion: RESUMEN,
    prueba: { ...RESUMEN, f1_dominio: 0.91, f1_area: 0.79 },
    umbrales: { umbral_dominio: 0.65, umbral_conjunta: 0.5 },
    tiempo_ms: 215,
    porcentaje_revision_validacion: 0.2,
    variantes: { plano: RESUMEN },
  },
  {
    id: 1,
    nombre: 'TF-IDF + Complement Naive Bayes (plano)',
    algoritmo: 'complement_nb',
    tipo: 'plano',
    version: 'v1',
    activo: false,
    entrenado_en: null,
    hiperparametros: {},
    validacion: { ...RESUMEN, f1_dominio: 0.8, f1_area: 0.6, f1_jerarquico: 0.6 },
    prueba: null,
    umbrales: null,
    tiempo_ms: 200,
    porcentaje_revision_validacion: 0.3,
    variantes: {},
  },
]

const NIVEL = {
  accuracy: 0.8,
  precision_macro: 0.8,
  recall_macro: 0.8,
  f1_macro: 0.79,
  precision_ponderado: 0.8,
  recall_ponderado: 0.8,
  f1_ponderado: 0.8,
}

export function metricas(cambios: Partial<MetricasModelo> = {}): MetricasModelo {
  return {
    modelo: { id: 3, nombre: 'TF-IDF + SVM lineal (plano)', version: 'v1', tipo: 'plano' },
    particion: 'prueba',
    particiones_disponibles: ['validacion', 'prueba'],
    documentos: 7048,
    metricas: { dominio: { ...NIVEL, f1_macro: 0.91 }, area: NIVEL, jerarquico: NIVEL },
    por_clase: {
      dominio: [],
      area: [
        { id: 0, nombre: 'Computer vision', precision: 0.9, recall: 0.9, f1: 0.9, soporte: 50, dominio: 'Computer Science' },
        { id: 1, nombre: 'Machine learning', precision: 0.5, recall: 0.4, f1: 0.45, soporte: 40, dominio: 'Computer Science' },
        { id: 2, nombre: 'Cancer', precision: 0.7, recall: 0.7, f1: 0.7, soporte: 30, dominio: 'Medical Sciences' },
      ],
    },
    confusion: {
      dominio: {
        etiquetas: ['Computer Science', 'Medical Sciences'],
        columnas: ['Computer Science', 'Medical Sciences'],
        matriz: [
          [90, 10],
          [5, 25],
        ],
      },
      area_por_dominio: [
        {
          dominio: 'Computer Science',
          etiquetas: ['Computer vision', 'Machine learning'],
          columnas: ['Computer vision', 'Machine learning', 'otro dominio'],
          matriz: [
            [45, 3, 2],
            [10, 25, 5],
          ],
        },
      ],
    },
    revision: { umbrales: { umbral_dominio: 0.65, umbral_conjunta: 0.5 }, porcentaje: 0.24, accuracy_aceptados: 0.9 },
    ...cambios,
  }
}
