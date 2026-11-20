import { useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api, type MetricasModelo, type Modelo, type Particion } from '@/api/cliente'
import { MatrizConfusion } from '@/components/MatrizConfusion'
import { TablaAreas } from '@/components/TablaAreas'
import {
  Aviso,
  Cargando,
  EncabezadoPagina,
  EstadoError,
  Tarjeta,
  TituloSeccion,
} from '@/components/ui'
import { colorDominio, decimal, porcentaje } from '@/lib/formato'
import { useCarga, useCategorias } from '@/lib/hooks'

// Metas del proyecto (RNF-01 y RNF-02).
const META_F1_DOMINIO = 0.85
const META_F1_AREA = 0.65
const META_TIEMPO_MS = 2000

const NOMBRES_PARTICION: Record<Particion, string> = { validacion: 'Validación', prueba: 'Prueba (test)' }
const COLOR_EJES = '#64748b'

export function Metricas() {
  const modelos = useCarga(api.modelos, [])

  return (
    <section className="space-y-6">
      <EncabezadoPagina
        titulo="Métricas de los modelos"
        descripcion="Cómo se desempeñan Naive Bayes, SVM y DistilBERT con el dataset WOS-46985."
      />
      {modelos.cargando && <Cargando />}
      {modelos.error !== null && <EstadoError error={modelos.error} reintentar={modelos.recargar} />}
      {modelos.datos?.length === 0 && (
        <Aviso tono="info" titulo="No hay modelos registrados">
          Entrena los modelos (ver ml/README.md) y reinicia la API para que aparezcan aquí.
        </Aviso>
      )}
      {modelos.datos && modelos.datos.length > 0 && <Panel modelos={modelos.datos} />}
      <DistribucionDataset />
    </section>
  )
}

function Panel({ modelos }: { modelos: Modelo[] }) {
  const [modeloId, setModeloId] = useState(() => (modelos.find((m) => m.activo) ?? modelos[0]).id)
  const [particion, setParticion] = useState<Particion | undefined>(undefined)
  const modelo = modelos.find((m) => m.id === modeloId) ?? modelos[0]
  const detalle = useCarga(() => api.metricas(modelo.id, particion), [modelo.id, particion])

  return (
    <>
      <Tarjeta className="flex flex-wrap items-end gap-4">
        <label className="flex flex-col gap-1 text-xs font-medium">
          Modelo
          <select
            value={modelo.id}
            onChange={(evento) => {
              setModeloId(Number(evento.target.value))
              setParticion(undefined)
            }}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
          >
            {modelos.map((m) => (
              <option key={m.id} value={m.id}>
                {m.nombre}
                {m.activo ? ' · activo' : ''}
              </option>
            ))}
          </select>
        </label>
        {detalle.datos && detalle.datos.particiones_disponibles.length > 1 && (
          <div role="group" aria-label="Partición" className="flex gap-1">
            {detalle.datos.particiones_disponibles.map((p) => (
              <button
                key={p}
                type="button"
                aria-pressed={detalle.datos?.particion === p}
                onClick={() => setParticion(p)}
                className={`rounded-lg px-3 py-2 text-sm ${
                  detalle.datos?.particion === p
                    ? 'bg-indigo-600 text-white'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300'
                }`}
              >
                {NOMBRES_PARTICION[p]}
              </button>
            ))}
          </div>
        )}
        <p className="text-xs text-slate-500 dark:text-slate-400">
          Versión {modelo.version}
          {detalle.datos &&
            ` · ${NOMBRES_PARTICION[detalle.datos.particion].toLowerCase()} · ${detalle.datos.documentos.toLocaleString('es-CO')} documentos`}
        </p>
      </Tarjeta>

      {detalle.cargando && <Cargando texto="Calculando métricas…" />}
      {detalle.error !== null && <EstadoError error={detalle.error} reintentar={detalle.recargar} />}
      {detalle.datos && !detalle.cargando && <Indicadores modelo={modelo} detalle={detalle.datos} />}

      <Comparacion modelos={modelos} />

      {detalle.datos && !detalle.cargando && <DetalleModelo detalle={detalle.datos} />}
    </>
  )
}

function Kpi({
  titulo,
  valor,
  meta,
  cumple,
}: {
  titulo: string
  valor: string
  meta?: string
  cumple?: boolean
}) {
  return (
    <Tarjeta>
      <p className="text-sm text-slate-600 dark:text-slate-400">{titulo}</p>
      <p className="mt-1 text-3xl font-semibold tracking-tight tabular-nums">{valor}</p>
      {meta && (
        <p
          className={`mt-1 text-xs font-medium ${
            cumple ? 'text-emerald-700 dark:text-emerald-400' : 'text-rose-700 dark:text-rose-400'
          }`}
        >
          {cumple ? '✓ Cumple' : '✗ No cumple'} la meta ({meta})
        </p>
      )}
    </Tarjeta>
  )
}

function Indicadores({ modelo, detalle }: { modelo: Modelo; detalle: MetricasModelo }) {
  const { dominio, area, jerarquico } = detalle.metricas
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
      <Kpi
        titulo="F1-macro dominio"
        valor={decimal(dominio.f1_macro)}
        meta={`≥ ${decimal(META_F1_DOMINIO, 2)}`}
        cumple={dominio.f1_macro >= META_F1_DOMINIO}
      />
      <Kpi
        titulo="F1-macro área"
        valor={decimal(area.f1_macro)}
        meta={`≥ ${decimal(META_F1_AREA, 2)}`}
        cumple={area.f1_macro >= META_F1_AREA}
      />
      <Kpi titulo="Accuracy jerárquica" valor={porcentaje(jerarquico.accuracy, 1)} />
      <Kpi
        titulo="Requieren revisión"
        valor={porcentaje(detalle.revision.porcentaje, 1)}
        meta={undefined}
      />
      <Kpi
        titulo="Tiempo por resumen"
        valor={modelo.tiempo_ms === null ? '—' : `${Math.round(modelo.tiempo_ms)} ms`}
        meta={modelo.tiempo_ms === null ? undefined : '< 2 s'}
        cumple={modelo.tiempo_ms !== null && modelo.tiempo_ms < META_TIEMPO_MS}
      />
    </div>
  )
}

function Comparacion({ modelos }: { modelos: Modelo[] }) {
  const datos = modelos.map((m) => ({
    nombre: m.nombre.replace('TF-IDF + ', '').replace(' (plano)', '').replace(' (jerarquico)', ' (jer.)'),
    'F1 dominio': m.validacion?.f1_dominio ?? 0,
    'F1 área': m.validacion?.f1_area ?? 0,
    'F1 jerárquico': m.validacion?.f1_jerarquico ?? 0,
  }))
  return (
    <Tarjeta>
      <TituloSeccion>Comparación de modelos (validación)</TituloSeccion>
      <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
        Se elige el de mayor F1-macro jerárquico; si otro queda a menos de 2 puntos y es más rápido,
        gana el más rápido.
      </p>
      <div className="mt-4 h-72" role="img" aria-label="Gráfico de barras: F1 de cada modelo">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={datos} margin={{ top: 8, right: 8, bottom: 8, left: -16 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#cbd5e1" strokeOpacity={0.5} />
            <XAxis dataKey="nombre" tick={{ fill: COLOR_EJES, fontSize: 12 }} />
            <YAxis domain={[0, 1]} tick={{ fill: COLOR_EJES, fontSize: 12 }} />
            <Tooltip formatter={(valor) => decimal(Number(valor))} />
            <Legend />
            <Bar dataKey="F1 dominio" fill="#a5b4fc" radius={[4, 4, 0, 0]} />
            <Bar dataKey="F1 área" fill="#6366f1" radius={[4, 4, 0, 0]} />
            <Bar dataKey="F1 jerárquico" fill="#3730a3" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[560px] text-sm">
          <caption className="sr-only">Métricas de validación de cada modelo</caption>
          <thead>
            <tr className="text-left text-xs text-slate-500 uppercase">
              <th scope="col" className="py-2">Modelo</th>
              <th scope="col" className="py-2 text-right">F1 dominio</th>
              <th scope="col" className="py-2 text-right">F1 área</th>
              <th scope="col" className="py-2 text-right">F1 jerárquico</th>
              <th scope="col" className="py-2 text-right">ms / resumen</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {modelos.map((m) => (
              <tr key={m.id}>
                <td className="py-2">
                  {m.nombre}
                  {m.activo && (
                    <span className="ml-2 rounded-full bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300">
                      activo
                    </span>
                  )}
                </td>
                <td className="py-2 text-right tabular-nums">{decimal(m.validacion?.f1_dominio)}</td>
                <td className="py-2 text-right tabular-nums">{decimal(m.validacion?.f1_area)}</td>
                <td className="py-2 text-right font-semibold tabular-nums">
                  {decimal(m.validacion?.f1_jerarquico)}
                </td>
                <td className="py-2 text-right tabular-nums">
                  {m.tiempo_ms === null ? '—' : Math.round(m.tiempo_ms)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Tarjeta>
  )
}

function abreviarArea(nombre: string): string {
  return nombre.length > 14 ? `${nombre.slice(0, 12)}…` : nombre
}

function DetalleModelo({ detalle }: { detalle: MetricasModelo }) {
  const { codigo, color } = useCategorias()
  const matrices = detalle.confusion.area_por_dominio
  const [dominioArea, setDominioArea] = useState(matrices[0]?.dominio ?? '')
  const matrizArea = matrices.find((m) => m.dominio === dominioArea) ?? matrices[0]

  return (
    <>
      <Tarjeta>
        <TituloSeccion>Matriz de confusión de dominios</TituloSeccion>
        <div className="mt-4">
          <MatrizConfusion
            titulo="Matriz de confusión de dominios"
            matriz={detalle.confusion.dominio}
            abreviar={codigo}
            colorFila={color}
          />
        </div>
      </Tarjeta>

      {matrizArea && (
        <Tarjeta>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <TituloSeccion>Áreas dentro de un dominio</TituloSeccion>
            <label className="flex items-center gap-2 text-xs font-medium">
              Dominio real
              <select
                value={matrizArea.dominio}
                onChange={(evento) => setDominioArea(evento.target.value)}
                className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-950"
              >
                {matrices.map((m) => (
                  <option key={m.dominio} value={m.dominio}>
                    {m.dominio} ({m.etiquetas.length} áreas)
                  </option>
                ))}
              </select>
            </label>
          </div>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
            La última columna cuenta los documentos que se enviaron a otro dominio.
          </p>
          <div className="mt-4">
            <MatrizConfusion
              titulo={`Matriz de confusión de áreas de ${matrizArea.dominio}`}
              matriz={matrizArea}
              abreviar={abreviarArea}
            />
          </div>
        </Tarjeta>
      )}

      <Tarjeta>
        <TituloSeccion>F1 por área</TituloSeccion>
        <p className="mt-1 mb-4 text-sm text-slate-600 dark:text-slate-400">
          Ordenadas de peor a mejor: haz clic en un encabezado para cambiar el orden.
        </p>
        <TablaAreas areas={detalle.por_clase.area} color={color} />
      </Tarjeta>
    </>
  )
}

function DistribucionDataset() {
  const { categorias } = useCategorias()
  if (!categorias) return null
  const datos = categorias.dominios.map((d) => ({
    codigo: d.codigo,
    nombre: d.nombre,
    documentos: d.documentos ?? 0,
    areas: d.areas.length,
    id: d.id,
  }))
  const total = datos.reduce((suma, d) => suma + d.documentos, 0)

  return (
    <Tarjeta>
      <TituloSeccion>Distribución de clases del dataset</TituloSeccion>
      <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
        {total.toLocaleString('es-CO')} documentos en {categorias.total_dominios} dominios y{' '}
        {categorias.total_areas} áreas. Medical concentra casi un tercio, lo que explica por qué el
        F1-macro se reporta junto al ponderado.
      </p>
      <div className="mt-4 h-64" role="img" aria-label="Gráfico de barras: documentos por dominio">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={datos} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#cbd5e1" strokeOpacity={0.5} />
            <XAxis dataKey="codigo" tick={{ fill: COLOR_EJES, fontSize: 12 }} />
            <YAxis tick={{ fill: COLOR_EJES, fontSize: 12 }} />
            <Tooltip
              formatter={(valor, _nombre, item) => [
                `${Number(valor).toLocaleString('es-CO')} documentos · ${item.payload.areas} áreas`,
                item.payload.nombre,
              ]}
              labelFormatter={() => ''}
            />
            <Bar dataKey="documentos" radius={[4, 4, 0, 0]}>
              {datos.map((d) => (
                <Cell key={d.id} fill={colorDominio(d.id)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Tarjeta>
  )
}
