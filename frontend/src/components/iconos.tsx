// Íconos de línea (24×24, trazo de 1,8). Decorativos: aria-hidden.
import type { SVGProps } from 'react'

function Icono({ children, ...props }: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      {children}
    </svg>
  )
}

/** Flecha subiendo a una bandeja: cargar un documento. */
export function IconoClasificar(props: SVGProps<SVGSVGElement>) {
  return (
    <Icono {...props}>
      <path d="M12 15V4" />
      <path d="m7 9 5-5 5 5" />
      <path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" />
    </Icono>
  )
}

/** Hoja con la esquina doblada y renglones: un documento. */
export function IconoDocumento(props: SVGProps<SVGSVGElement>) {
  return (
    <Icono {...props}>
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
      <path d="M14 3v5h5" />
      <path d="M9 13h6M9 17h6" />
    </Icono>
  )
}

/** Reloj con flecha: historial. */
export function IconoHistorial(props: SVGProps<SVGSVGElement>) {
  return (
    <Icono {...props}>
      <path d="M3 12a9 9 0 1 0 3-6.7" />
      <path d="M3 4v4h4" />
      <path d="M12 7v5l3 2" />
    </Icono>
  )
}

/** Barras: métricas. */
export function IconoMetricas(props: SVGProps<SVGSVGElement>) {
  return (
    <Icono {...props}>
      <path d="M4 20h16" />
      <path d="M7 16v-5" />
      <path d="M12 16V6" />
      <path d="M17 16v-8" />
    </Icono>
  )
}

export function IconoSol(props: SVGProps<SVGSVGElement>) {
  return (
    <Icono {...props}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </Icono>
  )
}

export function IconoLuna(props: SVGProps<SVGSVGElement>) {
  return (
    <Icono {...props}>
      <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" />
    </Icono>
  )
}
