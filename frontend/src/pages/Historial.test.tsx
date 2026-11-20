import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { expect, test } from 'vitest'
import { CATEGORIAS, CLASIFICACION, fila, pagina, simularApi } from '@/test/api-falsa'
import { renderizarEn } from '@/test/renderizar'

function api(respuesta = pagina([fila(1), fila(2, { requiere_revision: true })])) {
  return simularApi({
    'GET /salud': { cuerpo: { estado: 'activo', version: '0.1.0', modelo_activo: null } },
    'GET /categorias': { cuerpo: CATEGORIAS },
    'GET /clasificaciones': { cuerpo: respuesta },
    'GET /clasificaciones/:id': { cuerpo: CLASIFICACION },
  })
}

const ultimaConsulta = (llamadas: ReturnType<typeof api>) =>
  llamadas.filter((l) => l.ruta === '/clasificaciones').at(-1)!.parametros

test('lista las clasificaciones con su estado', async () => {
  api(pagina([fila(1), fila(2, { requiere_revision: true }), fila(3, { correccion: { dominio_correcto: 'X', area_correcta: null, comentario: null, creado_en: '2026-11-19T16:00:00' } })]))
  renderizarEn('/historial')
  const tabla = await screen.findByRole('table')
  const filas = within(tabla).getAllByRole('row').slice(1)
  expect(filas).toHaveLength(3)
  expect(filas[0]).toHaveTextContent('Confiable')
  expect(filas[1]).toHaveTextContent('Requiere revisión')
  expect(filas[2]).toHaveTextContent('Corregida')
  expect(within(filas[0]).getByRole('link')).toHaveAttribute('href', '/resultado/1')
})

test('al hacer clic en una fila se abre su resultado', async () => {
  api()
  renderizarEn('/historial')
  fireEvent.click((await screen.findAllByRole('row'))[1])
  expect(await screen.findByRole('heading', { name: 'Redes ligeras' })).toBeInTheDocument()
})

test('los filtros se envían a la API y vuelven a la página 1', async () => {
  const llamadas = api()
  renderizarEn('/historial?pagina=3')
  await screen.findByRole('table')
  expect(ultimaConsulta(llamadas).get('pagina')).toBe('3')

  const filtros = screen.getByRole('form', { name: 'Filtros del historial' })
  fireEvent.change(within(filtros).getByLabelText('Buscar'), { target: { value: 'redes' } })
  const dominio = within(filtros).getByLabelText('Dominio')
  await within(dominio).findByRole('option', { name: 'Medical Sciences' })
  fireEvent.change(dominio, { target: { value: 'Medical Sciences' } })
  fireEvent.change(within(filtros).getByLabelText('Estado'), { target: { value: 'true' } })
  fireEvent.change(within(filtros).getByLabelText('Desde'), { target: { value: '2026-11-01' } })
  fireEvent.click(within(filtros).getByRole('button', { name: 'Filtrar' }))

  await waitFor(() => expect(ultimaConsulta(llamadas).get('busqueda')).toBe('redes'))
  const consulta = ultimaConsulta(llamadas)
  expect(consulta.get('dominio')).toBe('Medical Sciences')
  expect(consulta.get('requiere_revision')).toBe('true')
  expect(consulta.get('desde')).toBe('2026-11-01')
  expect(consulta.get('pagina')).toBe('1')
  expect(consulta.get('tamano')).toBe('20')
})

test('la paginación pide la página siguiente', async () => {
  const llamadas = api(pagina([fila(1)], { total: 45, paginas: 3 }))
  renderizarEn('/historial')
  expect(await screen.findByText(/45 clasificaciones · página 1 de 3/)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '← Anterior' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Siguiente →' }))
  await waitFor(() => expect(ultimaConsulta(llamadas).get('pagina')).toBe('2'))
})

test('sin resultados con filtros sugiere limpiarlos', async () => {
  api(pagina([]))
  renderizarEn('/historial?dominio=Psychology')
  expect(await screen.findByText('Ningún resultado con estos filtros')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Limpiar' }))
  expect(await screen.findByText('Todavía no hay clasificaciones')).toBeInTheDocument()
})
