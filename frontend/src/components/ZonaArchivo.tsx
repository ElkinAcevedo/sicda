import { type DragEvent, useId, useRef, useState } from 'react'
import { EXTENSIONES, TAMANO_MAXIMO_MB } from '@/lib/archivos'
import { IconoDocumento } from '@/components/iconos'

/** Zona de arrastrar y soltar (también se puede hacer clic o usar el teclado). */
export function ZonaArchivo({
  onArchivo,
  deshabilitada = false,
}: {
  onArchivo: (archivo: File) => void
  deshabilitada?: boolean
}) {
  const entrada = useRef<HTMLInputElement>(null)
  const idAyuda = useId()
  const [encima, setEncima] = useState(false)

  function soltar(evento: DragEvent) {
    evento.preventDefault()
    setEncima(false)
    const archivo = evento.dataTransfer.files[0]
    if (archivo && !deshabilitada) onArchivo(archivo)
  }

  return (
    <div
      onDragOver={(evento) => {
        evento.preventDefault()
        if (!deshabilitada) setEncima(true)
      }}
      onDragLeave={() => setEncima(false)}
      onDrop={soltar}
      className={`flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed px-6 py-12 text-center transition-colors ${
        encima
          ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-950'
          : 'border-slate-300 bg-white dark:border-slate-700 dark:bg-slate-900'
      }`}
    >
      <IconoDocumento className="h-10 w-10 text-indigo-500 dark:text-indigo-400" />
      <p className="text-lg font-medium">Arrastra aquí tu documento</p>
      <p id={idAyuda} className="text-sm text-slate-500 dark:text-slate-400">
        PDF, DOCX o TXT · máximo {TAMANO_MAXIMO_MB} MB · en inglés
      </p>
      <button
        type="button"
        disabled={deshabilitada}
        onClick={() => entrada.current?.click()}
        aria-describedby={idAyuda}
        className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600 disabled:bg-indigo-300"
      >
        Elegir archivo
      </button>
      <input
        ref={entrada}
        type="file"
        accept={EXTENSIONES.join(',')}
        className="sr-only"
        tabIndex={-1}
        aria-label="Archivo a clasificar"
        onChange={(evento) => {
          const archivo = evento.target.files?.[0]
          if (archivo) onArchivo(archivo)
          evento.target.value = '' // permite volver a elegir el mismo archivo
        }}
      />
    </div>
  )
}
