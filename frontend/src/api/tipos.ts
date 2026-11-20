// Tipos del contrato de la API (backend/app/schemas). Mantener sincronizados con el backend.

export interface RespuestaSalud {
  estado: string
  version: string
  modelo_activo: string | null
}

export interface Alternativa {
  nombre: string
  confianza: number
}

export interface Nivel {
  nombre: string
  confianza: number
  alternativas: Alternativa[]
}

export interface TerminoClave {
  termino: string
  peso: number
}

export interface Advertencia {
  codigo: string
  mensaje: string
}

export interface Correccion {
  dominio_correcto: string
  area_correcta: string | null
  comentario: string | null
  creado_en: string
}

export type FuenteTexto = 'abstract' | 'inicio' | 'texto_completo'

export interface DocumentoClasificado {
  titulo: string | null
  nombre_archivo: string | null
  idioma: string
  num_terminos: number
  fuente_texto: FuenteTexto
}

export interface Clasificacion {
  id: number
  documento: DocumentoClasificado
  dominio: Nivel
  area: Nivel
  confianza_conjunta: number
  requiere_revision: boolean
  terminos_clave: TerminoClave[]
  advertencias: Advertencia[]
  modelo: { nombre: string; version: string }
  tiempo_ms: number
  creado_en: string
  correccion: Correccion | null
}

export interface ClasificacionDetalle extends Clasificacion {
  documento: DocumentoClasificado & {
    tipo: string
    texto_extraido: string
    palabras_clave: string[]
  }
}

export interface FilaHistorial {
  id: number
  creado_en: string
  documento: { titulo: string | null; nombre_archivo: string | null; tipo: string }
  dominio: string
  area: string
  confianza_dominio: number
  confianza_conjunta: number
  requiere_revision: boolean
  correccion: Correccion | null
}

export interface PaginaHistorial {
  elementos: FilaHistorial[]
  total: number
  pagina: number
  tamano: number
  paginas: number
}

export interface FiltrosHistorial {
  pagina?: number
  tamano?: number
  dominio?: string
  desde?: string
  hasta?: string
  requiere_revision?: boolean
  busqueda?: string
}

export interface EntradaCorreccion {
  dominio_correcto: string
  area_correcta?: string | null
  comentario?: string | null
}

export interface AreaCategoria {
  id: number
  nombre: string
  documentos: number | null
}

export interface DominioCategoria {
  id: number
  codigo: string
  nombre: string
  nombre_es: string | null
  documentos: number | null
  areas: AreaCategoria[]
}

export interface Categorias {
  total_dominios: number
  total_areas: number
  dominios: DominioCategoria[]
}

export interface ResumenMetricas {
  f1_dominio: number | null
  f1_area: number | null
  f1_jerarquico: number | null
  accuracy_jerarquica: number | null
}

export interface Modelo {
  id: number
  nombre: string
  algoritmo: string
  tipo: string
  version: string
  activo: boolean
  entrenado_en: string | null
  hiperparametros: Record<string, unknown>
  validacion: ResumenMetricas | null
  prueba: ResumenMetricas | null
  umbrales: Record<string, number> | null
  tiempo_ms: number | null
  porcentaje_revision_validacion: number | null
  variantes: Record<string, ResumenMetricas | null>
}

export interface MetricasNivel {
  accuracy: number
  precision_macro: number
  recall_macro: number
  f1_macro: number
  precision_ponderado: number
  recall_ponderado: number
  f1_ponderado: number
}

export interface MetricaClase {
  id: number
  nombre: string
  precision: number
  recall: number
  f1: number
  soporte: number
  dominio?: string | null
}

export interface MatrizConfusion {
  etiquetas: string[]
  columnas: string[]
  matriz: number[][]
}

export type Particion = 'validacion' | 'prueba'

export interface MetricasModelo {
  modelo: { id: number; nombre: string; version: string; tipo: string }
  particion: Particion
  particiones_disponibles: Particion[]
  documentos: number
  metricas: Record<'dominio' | 'area' | 'jerarquico', MetricasNivel>
  por_clase: { dominio: MetricaClase[]; area: MetricaClase[] }
  confusion: { dominio: MatrizConfusion; area_por_dominio: (MatrizConfusion & { dominio: string })[] }
  revision: {
    umbrales: Record<string, number>
    porcentaje: number
    accuracy_aceptados: number | null
  }
}
