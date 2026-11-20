import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, type ClasificacionDetalle, type Nivel } from '@/api/cliente'
import { FormularioCorreccion } from '@/components/FormularioCorreccion'
import {
  Aviso,
  BarraConfianza,
  Boton,
  Cargando,
  EncabezadoPagina,
  EstadoError,
  Tarjeta,
  TituloSeccion,
} from '@/components/ui'
import { etiquetaFuente, fechaHora, nombreIdioma, porcentaje } from '@/lib/formato'
import { useCarga, useCategorias } from '@/lib/hooks'
import { resaltar } from '@/lib/resaltado'

export function Resultado() {
  const { id } = useParams()
  const numero = Number(id)
  const { datos, error, cargando, recargar } = useCarga(() => api.clasificacion(numero), [numero])
  const [actualizada, setActualizada] = useState<ClasificacionDetalle | null>(null)

  if (cargando) return <Cargando texto="Cargando el resultado…" />
  if (error !== null) return <EstadoError error={error} reintentar={recargar} />
  const clasificacion = actualizada?.id === numero ? actualizada : datos
  if (!clasificacion) return null
  return <VistaResultado clasificacion={clasificacion} onActualizada={setActualizada} />
}

function VistaResultado({
  clasificacion: c,
  onActualizada,
}: {
  clasificacion: ClasificacionDetalle
  onActualizada: (actualizada: ClasificacionDetalle) => void
}) {
  const { color, dominio: buscarDominio } = useCategorias()
  const [corrigiendo, setCorrigiendo] = useState(false)
  const documento = c.documento
  const titulo = documento.titulo || documento.nombre_archivo || 'Texto sin título'
  const colorDominio = color(c.dominio.nombre)

  return (
    <section className="space-y-6">
      <EncabezadoPagina
        titulo={titulo}
        descripcion={[
          documento.nombre_archivo && documento.titulo ? documento.nombre_archivo : null,
          fechaHora(c.creado_en),
          `${c.modelo.nombre} · ${c.modelo.version}`,
        ]
          .filter(Boolean)
          .join(' · ')}
        acciones={
          <div className="flex gap-2">
            <Link
              to="/"
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
            >
              Clasificar otro
            </Link>
            <Link
              to="/historial"
              className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
            >
              Historial
            </Link>
          </div>
        }
      />

      <div className="space-y-3">
        {c.requiere_revision && (
          <Aviso tono="advertencia" titulo="Requiere revisión">
            La confianza del modelo es baja para este documento. Revisa las alternativas antes de
            usar la categoría.
          </Aviso>
        )}
        {c.advertencias.map((advertencia) => (
          <Aviso key={advertencia.codigo} tono="info">
            {advertencia.mensaje}
          </Aviso>
        ))}
        {c.correccion && (
          <Aviso tono="exito" titulo="Corregida por el usuario">
            Categoría correcta: <strong>{c.correccion.dominio_correcto}</strong>
            {c.correccion.area_correcta && (
              <>
                {' '}
                / <strong>{c.correccion.area_correcta}</strong>
              </>
            )}
            {c.correccion.comentario && <> — «{c.correccion.comentario}»</>}
          </Aviso>
        )}
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <TarjetaNivel
          titulo="Dominio"
          nivel={c.dominio}
          color={colorDominio}
          subtitulo={buscarDominio(c.dominio.nombre)?.nombre_es ?? undefined}
        />
        <TarjetaNivel titulo="Área" nivel={c.area} color={colorDominio} />
      </div>

      <Tarjeta className="flex flex-wrap items-center justify-between gap-4">
        <div className="min-w-60 flex-1">
          <p className="text-sm text-slate-600 dark:text-slate-400">
            Confianza conjunta (dominio × área)
          </p>
          <BarraConfianza valor={c.confianza_conjunta} etiqueta="Confianza conjunta" />
        </div>
        {!corrigiendo && (
          <Boton variante="secundario" onClick={() => setCorrigiendo(true)}>
            {c.correccion ? 'Cambiar corrección' : '¿No es correcto?'}
          </Boton>
        )}
      </Tarjeta>

      {corrigiendo && (
        <FormularioCorreccion
          clasificacion={c}
          onCancelar={() => setCorrigiendo(false)}
          onGuardado={(actualizada) => {
            onActualizada(actualizada)
            setCorrigiendo(false)
          }}
        />
      )}

      <div className="grid gap-4 md:grid-cols-2">
        <Alternativas titulo="Alternativas de dominio" nivel={c.dominio} />
        <Alternativas titulo="Alternativas de área" nivel={c.area} />
      </div>

      <Tarjeta>
        <TituloSeccion>Términos que más pesaron</TituloSeccion>
        {c.terminos_clave.length === 0 ? (
          <p className="mt-2 text-sm text-slate-500">El modelo no reporta términos para este texto.</p>
        ) : (
          <ul className="mt-3 flex flex-wrap gap-2" aria-label="Términos clave">
            {c.terminos_clave.map((t) => (
              <li
                key={t.termino}
                title={`Peso ${t.peso}`}
                className="rounded-full bg-indigo-50 px-3 py-1 text-sm text-indigo-800 dark:bg-indigo-950 dark:text-indigo-200"
              >
                {t.termino}
              </li>
            ))}
          </ul>
        )}
      </Tarjeta>

      <Tarjeta>
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <TituloSeccion>Texto que leyó el sistema</TituloSeccion>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {etiquetaFuente(documento.fuente_texto)} · {documento.num_terminos} términos · idioma{' '}
            {nombreIdioma(documento.idioma)} · {Math.round(c.tiempo_ms)} ms
          </p>
        </div>
        <p className="mt-3 text-sm leading-relaxed whitespace-pre-line text-slate-700 dark:text-slate-300">
          {resaltar(
            documento.texto_extraido,
            c.terminos_clave.map((t) => t.termino),
          ).map((fragmento, i) =>
            fragmento.resaltado ? (
              <mark
                key={i}
                className="rounded bg-amber-100 px-0.5 text-inherit dark:bg-amber-900/60"
              >
                {fragmento.texto}
              </mark>
            ) : (
              <span key={i}>{fragmento.texto}</span>
            ),
          )}
        </p>
        {documento.palabras_clave.length > 0 && (
          <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">
            Palabras clave del documento: {documento.palabras_clave.join(', ')}
          </p>
        )}
      </Tarjeta>
    </section>
  )
}

function TarjetaNivel({
  titulo,
  nivel,
  color,
  subtitulo,
}: {
  titulo: string
  nivel: Nivel
  color: string
  subtitulo?: string
}) {
  return (
    <Tarjeta className="border-t-4" style={{ borderTopColor: color }}>
      <TituloSeccion>{titulo}</TituloSeccion>
      <p className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">{nivel.nombre}</p>
      {subtitulo && <p className="text-sm text-slate-500 dark:text-slate-400">{subtitulo}</p>}
      <div className="mt-4">
        <BarraConfianza valor={nivel.confianza} etiqueta={`Confianza del ${titulo.toLowerCase()}`} grande />
      </div>
    </Tarjeta>
  )
}

function Alternativas({ titulo, nivel }: { titulo: string; nivel: Nivel }) {
  return (
    <Tarjeta>
      <TituloSeccion>{titulo}</TituloSeccion>
      <ul className="mt-3 space-y-3">
        {nivel.alternativas.map((alternativa, i) => (
          <li key={alternativa.nombre}>
            <div className="mb-1 flex justify-between gap-2 text-sm">
              <span className={i === 0 ? 'font-semibold' : 'text-slate-600 dark:text-slate-400'}>
                {alternativa.nombre}
                {i === 0 && <span className="sr-only"> (elegida)</span>}
              </span>
              <span className="tabular-nums text-slate-500">{porcentaje(alternativa.confianza)}</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800" aria-hidden="true">
              <div
                className={`h-full rounded-full ${i === 0 ? 'bg-indigo-600' : 'bg-slate-400 dark:bg-slate-500'}`}
                style={{ width: `${alternativa.confianza * 100}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
    </Tarjeta>
  )
}
