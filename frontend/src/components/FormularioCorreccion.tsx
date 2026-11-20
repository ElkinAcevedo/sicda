import { type FormEvent, useState } from 'react'
import { api, type ClasificacionDetalle } from '@/api/cliente'
import { Boton, EstadoError, Tarjeta } from '@/components/ui'
import { useCategorias } from '@/lib/hooks'

/** «¿No es correcto?»: el usuario indica el dominio y, si lo sabe, el área correctos (RF-12). */
export function FormularioCorreccion({
  clasificacion,
  onGuardado,
  onCancelar,
}: {
  clasificacion: ClasificacionDetalle
  onGuardado: (actualizada: ClasificacionDetalle) => void
  onCancelar: () => void
}) {
  const { categorias, dominio: buscarDominio } = useCategorias()
  const previa = clasificacion.correccion
  const [dominio, setDominio] = useState(previa?.dominio_correcto ?? '')
  const [area, setArea] = useState(previa?.area_correcta ?? '')
  const [comentario, setComentario] = useState(previa?.comentario ?? '')
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState<unknown>(null)

  const areas = buscarDominio(dominio)?.areas ?? []

  async function guardar(evento: FormEvent) {
    evento.preventDefault()
    setGuardando(true)
    setError(null)
    try {
      onGuardado(
        await api.corregir(clasificacion.id, {
          dominio_correcto: dominio,
          area_correcta: area || null,
          comentario: comentario.trim() || null,
        }),
      )
    } catch (fallo) {
      setError(fallo)
    } finally {
      setGuardando(false)
    }
  }

  return (
    <Tarjeta>
      <form onSubmit={guardar} className="flex flex-col gap-4" aria-label="Corregir clasificación">
        <div>
          <h2 className="text-lg font-semibold">¿Cuál es la categoría correcta?</h2>
          <p className="text-sm text-slate-600 dark:text-slate-400">
            La predicción original se conserva; tu corrección se guarda junto a ella.
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="flex flex-col gap-1 text-sm font-medium">
            Dominio correcto
            <select
              required
              value={dominio}
              onChange={(evento) => {
                setDominio(evento.target.value)
                setArea('')
              }}
              className="rounded-lg border border-slate-300 bg-white px-3 py-2 font-normal dark:border-slate-700 dark:bg-slate-950"
            >
              <option value="" disabled>
                Elige un dominio
              </option>
              {categorias?.dominios.map((d) => (
                <option key={d.id} value={d.nombre}>
                  {d.nombre}
                  {d.nombre_es ? ` (${d.nombre_es})` : ''}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium">
            Área correcta (opcional)
            <select
              value={area}
              onChange={(evento) => setArea(evento.target.value)}
              disabled={!dominio}
              className="rounded-lg border border-slate-300 bg-white px-3 py-2 font-normal disabled:opacity-60 dark:border-slate-700 dark:bg-slate-950"
            >
              <option value="">No lo sé</option>
              {areas.map((a) => (
                <option key={a.id} value={a.nombre}>
                  {a.nombre}
                </option>
              ))}
            </select>
          </label>
        </div>
        <label className="flex flex-col gap-1 text-sm font-medium">
          Comentario (opcional)
          <textarea
            value={comentario}
            onChange={(evento) => setComentario(evento.target.value)}
            rows={2}
            maxLength={2000}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 font-normal dark:border-slate-700 dark:bg-slate-950"
          />
        </label>
        {error !== null && <EstadoError error={error} />}
        <div className="flex justify-end gap-2">
          <Boton variante="fantasma" onClick={onCancelar}>
            Cancelar
          </Boton>
          <Boton type="submit" disabled={!dominio || guardando}>
            {guardando ? 'Guardando…' : 'Guardar corrección'}
          </Boton>
        </div>
      </form>
    </Tarjeta>
  )
}
