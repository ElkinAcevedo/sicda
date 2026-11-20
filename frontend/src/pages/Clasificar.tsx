import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, type Clasificacion } from '@/api/cliente'
import { ProgresoEtapas } from '@/components/ProgresoEtapas'
import {
  Aviso,
  Boton,
  Cargando,
  EncabezadoPagina,
  EstadoError,
  InsigniaDominio,
  Tarjeta,
  TituloSeccion,
} from '@/components/ui'
import { ZonaArchivo } from '@/components/ZonaArchivo'
import { validarArchivo } from '@/lib/archivos'
import { EJEMPLO } from '@/lib/ejemplo'
import { fechaHora, porcentaje } from '@/lib/formato'
import { useCarga, useCategorias } from '@/lib/hooks'

const MINIMO_PALABRAS = 20

type Pestana = 'archivo' | 'texto'

function contarPalabras(texto: string): number {
  return texto.trim() ? texto.trim().split(/\s+/).length : 0
}

export function Clasificar() {
  const navegar = useNavigate()
  const [pestana, setPestana] = useState<Pestana>('archivo')
  const [titulo, setTitulo] = useState('')
  const [texto, setTexto] = useState('')
  const [procesando, setProcesando] = useState(false)
  const [error, setError] = useState<unknown>(null)

  async function clasificar(solicitud: () => Promise<Clasificacion>) {
    setProcesando(true)
    setError(null)
    try {
      const resultado = await solicitud()
      navegar(`/resultado/${resultado.id}`)
    } catch (fallo) {
      setError(fallo)
      setProcesando(false)
    }
  }

  function elegirArchivo(archivo: File) {
    const problema = validarArchivo(archivo)
    if (problema) {
      setError(problema)
      return
    }
    void clasificar(() => api.clasificarArchivo(archivo))
  }

  function probarEjemplo() {
    setPestana('texto')
    setTitulo(EJEMPLO.titulo)
    setTexto(EJEMPLO.texto)
    void clasificar(() => api.clasificarTexto(EJEMPLO.texto, EJEMPLO.titulo))
  }

  const palabras = contarPalabras(texto)

  return (
    <section>
      <EncabezadoPagina
        titulo="Clasificar documento"
        descripcion="El sistema identifica el dominio y el área temática a partir del resumen."
        acciones={
          <Boton variante="secundario" onClick={probarEjemplo} disabled={procesando}>
            Probar con un ejemplo
          </Boton>
        }
      />

      <div role="tablist" aria-label="Forma de enviar el documento" className="mb-4 flex gap-1">
        {(
          [
            ['archivo', 'Subir archivo'],
            ['texto', 'Pegar texto'],
          ] as const
        ).map(([valor, etiqueta]) => (
          <button
            key={valor}
            type="button"
            role="tab"
            id={`pestana-${valor}`}
            aria-selected={pestana === valor}
            aria-controls={`panel-${valor}`}
            onClick={() => setPestana(valor)}
            className={`rounded-lg px-4 py-2 text-sm font-medium focus-visible:outline-2 focus-visible:outline-indigo-600 ${
              pestana === valor
                ? 'bg-white shadow-sm ring-1 ring-slate-200 dark:bg-slate-900 dark:ring-slate-700'
                : 'text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800'
            }`}
          >
            {etiqueta}
          </button>
        ))}
      </div>

      {pestana === 'archivo' ? (
        <div role="tabpanel" id="panel-archivo" aria-labelledby="pestana-archivo">
          <ZonaArchivo onArchivo={elegirArchivo} deshabilitada={procesando} />
        </div>
      ) : (
        <form
          role="tabpanel"
          id="panel-texto"
          aria-labelledby="pestana-texto"
          onSubmit={(evento) => {
            evento.preventDefault()
            void clasificar(() => api.clasificarTexto(texto, titulo))
          }}
        >
          <Tarjeta className="flex flex-col gap-4">
            <label className="flex flex-col gap-1 text-sm font-medium">
              Título (opcional)
              <input
                value={titulo}
                onChange={(evento) => setTitulo(evento.target.value)}
                maxLength={500}
                className="rounded-lg border border-slate-300 bg-white px-3 py-2 font-normal dark:border-slate-700 dark:bg-slate-950"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm font-medium">
              Resumen (abstract) en inglés
              <textarea
                value={texto}
                onChange={(evento) => setTexto(evento.target.value)}
                rows={9}
                required
                aria-describedby="ayuda-texto"
                className="rounded-lg border border-slate-300 bg-white px-3 py-2 font-normal dark:border-slate-700 dark:bg-slate-950"
              />
            </label>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p id="ayuda-texto" className="text-sm text-slate-500 dark:text-slate-400">
                {palabras} palabras
                {palabras > 0 && palabras < MINIMO_PALABRAS && ` · se necesitan al menos ${MINIMO_PALABRAS}`}
              </p>
              <Boton type="submit" disabled={procesando || palabras === 0}>
                Clasificar
              </Boton>
            </div>
          </Tarjeta>
        </form>
      )}

      <div className="mt-4 space-y-4" aria-live="polite">
        {procesando && (
          <Tarjeta>
            <ProgresoEtapas />
          </Tarjeta>
        )}
        {error !== null && !procesando && <EstadoError error={error} />}
      </div>

      <UltimasClasificaciones />
    </section>
  )
}

function UltimasClasificaciones() {
  const { datos, error, cargando } = useCarga(() => api.historial({ tamano: 5 }), [])
  const { color } = useCategorias()

  return (
    <section className="mt-10" aria-labelledby="titulo-ultimas">
      <div className="mb-3 flex items-center justify-between">
        <TituloSeccion>
          <span id="titulo-ultimas">Últimas clasificaciones</span>
        </TituloSeccion>
        <Link to="/historial" className="text-sm font-medium text-indigo-700 hover:underline dark:text-indigo-300">
          Ver todo el historial
        </Link>
      </div>
      {cargando && <Cargando />}
      {error !== null && <Aviso tono="info">No se pudieron cargar las últimas clasificaciones.</Aviso>}
      {datos && datos.elementos.length === 0 && (
        <Aviso tono="info" titulo="Todavía no hay clasificaciones">
          Sube un documento o usa «Probar con un ejemplo» para ver cómo funciona.
        </Aviso>
      )}
      {datos && datos.elementos.length > 0 && (
        <ul className="divide-y divide-slate-200 rounded-xl border border-slate-200 bg-white dark:divide-slate-800 dark:border-slate-800 dark:bg-slate-900">
          {datos.elementos.map((fila) => (
            <li key={fila.id}>
              <Link
                to={`/resultado/${fila.id}`}
                className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-sm hover:bg-slate-50 dark:hover:bg-slate-800"
              >
                <span className="min-w-0 flex-1 truncate font-medium">
                  {fila.documento.titulo || fila.documento.nombre_archivo || 'Texto sin título'}
                </span>
                <span className="text-slate-600 dark:text-slate-300">
                  <InsigniaDominio nombre={fila.dominio} color={color(fila.dominio)} /> · {fila.area}
                </span>
                <span className="w-14 text-right tabular-nums text-slate-500">
                  {porcentaje(fila.confianza_conjunta)}
                </span>
                <span className="text-right text-xs whitespace-nowrap text-slate-500 sm:w-44">
                  {fechaHora(fila.creado_en)}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
