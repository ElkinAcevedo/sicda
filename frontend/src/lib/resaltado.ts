// Resaltado de los términos clave en el texto que leyó el modelo.
//
// Los términos vienen preprocesados (minúsculas, sin tildes, lematizados: «train», «neural
// network»), así que se comparan con cada palabra normalizada del texto: «trained» y
// «training» coinciden con «train». No es exacto, pero basta para ubicar lo que pesó.

export interface Fragmento {
  texto: string
  resaltado: boolean
}

export function normalizar(palabra: string): string {
  return palabra
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
}

/** Cuántas letras de más se aceptan tras la raíz («network» → «networks», «trained»). */
const SUFIJO_MAXIMO = 3

export function palabrasDeTerminos(terminos: string[]): string[] {
  const palabras = new Set<string>()
  for (const termino of terminos) {
    for (const palabra of normalizar(termino).split(/\s+/)) {
      if (palabra.length >= 3) palabras.add(palabra)
    }
  }
  return [...palabras]
}

function coincide(palabra: string, raices: string[]): boolean {
  const normal = normalizar(palabra)
  return raices.some(
    (raiz) => normal.startsWith(raiz) && normal.length - raiz.length <= SUFIJO_MAXIMO,
  )
}

/** Divide el texto en fragmentos, marcando las palabras que corresponden a algún término. */
export function resaltar(texto: string, terminos: string[]): Fragmento[] {
  const raices = palabrasDeTerminos(terminos)
  if (raices.length === 0) return [{ texto, resaltado: false }]
  const fragmentos: Fragmento[] = []
  // Separa palabras (letras y números, incluidas las tildes) del resto.
  for (const parte of texto.split(/([\p{L}\p{N}]+)/u)) {
    if (!parte) continue
    const resaltado = /^[\p{L}\p{N}]+$/u.test(parte) && coincide(parte, raices)
    const ultimo = fragmentos.at(-1)
    if (ultimo && ultimo.resaltado === resaltado) ultimo.texto += parte
    else fragmentos.push({ texto: parte, resaltado })
  }
  return fragmentos
}
