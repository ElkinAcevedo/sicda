// Reglas de los archivos que acepta la API (mismas que backend/app/extraccion).
import { ErrorApi } from '@/api/cliente'

export const EXTENSIONES = ['.pdf', '.docx', '.txt']
export const TAMANO_MAXIMO_MB = 10

/** Valida en el navegador lo mismo que la API, para avisar antes de subir el archivo. */
export function validarArchivo(archivo: File): ErrorApi | null {
  const nombre = archivo.name.toLowerCase()
  if (!EXTENSIONES.some((extension) => nombre.endsWith(extension))) {
    return new ErrorApi('FORMATO_NO_SOPORTADO', `«${archivo.name}» no es un PDF, DOCX ni TXT.`, 415)
  }
  if (archivo.size > TAMANO_MAXIMO_MB * 1024 * 1024) {
    return new ErrorApi(
      'ARCHIVO_MUY_GRANDE',
      `«${archivo.name}» pesa más de ${TAMANO_MAXIMO_MB} MB.`,
      413,
    )
  }
  if (archivo.size === 0) {
    return new ErrorApi('TEXTO_INSUFICIENTE', `«${archivo.name}» está vacío.`, 422)
  }
  return null
}
