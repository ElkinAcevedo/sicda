import { ErrorApi, SIN_CONEXION } from '@/api/cliente'

/** Qué puede hacer el usuario ante cada error (principio «errores con una acción sugerida»). */
const ACCIONES: Record<string, string> = {
  TEXTO_INSUFICIENTE:
    'Pega el resumen completo (al menos 20 palabras) o sube un PDF con texto seleccionable.',
  FORMATO_NO_SOPORTADO: 'Guarda el documento como PDF, DOCX o TXT y vuelve a subirlo.',
  ARCHIVO_MUY_GRANDE: 'Sube solo el artículo (máximo 10 MB) o pega su resumen.',
  ARCHIVO_DANADO: 'Comprueba que el archivo se abre en tu equipo, o pega el texto del resumen.',
  MODELO_NO_DISPONIBLE: 'Verifica que exista models/activo.json y reinicia la API.',
  CATEGORIAS_NO_DISPONIBLES: 'Verifica que exista data/processed/categorias.json y reinicia la API.',
  NO_ENCONTRADO: 'Vuelve al historial y elige otra clasificación.',
  [SIN_CONEXION]: 'Comprueba que la API esté corriendo (puerto 8000) y vuelve a intentarlo.',
}

export function mensajeError(error: unknown): { mensaje: string; accion?: string } {
  if (error instanceof ErrorApi) return { mensaje: error.message, accion: ACCIONES[error.codigo] }
  return { mensaje: 'Ocurrió un error inesperado.', accion: 'Recarga la página.' }
}
