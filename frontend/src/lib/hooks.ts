import { useCallback, useEffect, useMemo, useState } from 'react'
import { api, type Categorias, type DominioCategoria } from '@/api/cliente'
import { COLOR_SIN_DOMINIO, colorDominio } from '@/lib/formato'

export interface EstadoCarga<T> {
  datos: T | null
  error: unknown
  cargando: boolean
  recargar: () => void
}

/** Ejecuta `cargar` al montar y cada vez que cambian `dependencias`. */
export function useCarga<T>(cargar: () => Promise<T>, dependencias: unknown[]): EstadoCarga<T> {
  const [datos, setDatos] = useState<T | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [cargando, setCargando] = useState(true)
  const [version, setVersion] = useState(0)

  useEffect(() => {
    let vigente = true
    setCargando(true)
    setError(null)
    cargar()
      .then((resultado) => vigente && setDatos(resultado))
      .catch((fallo: unknown) => vigente && setError(fallo))
      .finally(() => vigente && setCargando(false))
    return () => {
      vigente = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- las dependencias las da quien llama
  }, [...dependencias, version])

  const recargar = useCallback(() => setVersion((v) => v + 1), [])
  return { datos, error, cargando, recargar }
}

// Las categorías no cambian mientras la API corre: se piden una sola vez por sesión.
let categoriasPendientes: Promise<Categorias> | null = null

export function reiniciarCategorias(): void {
  categoriasPendientes = null
}

function pedirCategorias(): Promise<Categorias> {
  categoriasPendientes ??= api.categorias().catch((error: unknown) => {
    categoriasPendientes = null // se reintenta en la próxima vista
    throw error
  })
  return categoriasPendientes
}

export interface CatalogoDominios {
  categorias: Categorias | null
  dominio: (nombre: string) => DominioCategoria | undefined
  color: (nombre: string) => string
  codigo: (nombre: string) => string
}

/** Catálogo de dominios y áreas, con el color fijo de cada dominio. */
export function useCategorias(): CatalogoDominios {
  const { datos } = useCarga(pedirCategorias, [])
  return useMemo(() => {
    const porNombre = new Map(datos?.dominios.map((d) => [d.nombre, d]))
    return {
      categorias: datos,
      dominio: (nombre) => porNombre.get(nombre),
      color: (nombre) => {
        const encontrado = porNombre.get(nombre)
        return encontrado ? colorDominio(encontrado.id) : COLOR_SIN_DOMINIO
      },
      codigo: (nombre) => porNombre.get(nombre)?.codigo ?? nombre,
    }
  }, [datos])
}

export type Tema = 'claro' | 'oscuro'

function temaInicial(): Tema {
  try {
    const guardado = localStorage.getItem('sicda-tema')
    if (guardado === 'claro' || guardado === 'oscuro') return guardado
  } catch {
    // localStorage bloqueado: se usa la preferencia del sistema.
  }
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'oscuro' : 'claro'
}

/** Modo oscuro: clase `dark` en <html>, recordado en localStorage. */
export function useTema(): [Tema, () => void] {
  const [tema, setTema] = useState<Tema>(temaInicial)
  useEffect(() => {
    document.documentElement.classList.toggle('dark', tema === 'oscuro')
    try {
      localStorage.setItem('sicda-tema', tema)
    } catch {
      // Sin almacenamiento: el tema dura lo que la pestaña.
    }
  }, [tema])
  return [tema, () => setTema((t) => (t === 'oscuro' ? 'claro' : 'oscuro'))]
}
