import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { expect, test } from 'vitest'
import { CATEGORIAS, MODELOS, metricas, simularApi } from '@/test/api-falsa'
import { renderizarEn } from '@/test/renderizar'

function api() {
  return simularApi({
    'GET /salud': { cuerpo: { estado: 'activo', version: '0.1.0', modelo_activo: null } },
    'GET /categorias': { cuerpo: CATEGORIAS },
    'GET /modelos': { cuerpo: MODELOS },
    'GET /modelos/:id/metricas': (url) => ({
      cuerpo: metricas(
        url.searchParams.get('particion') === 'validacion'
          ? { particion: 'validacion', documentos: 7047 }
          : {},
      ),
    }),
  })
}

test('muestra los KPI del modelo activo con sus metas', async () => {
  const llamadas = api()
  renderizarEn('/metricas')
  expect(await screen.findByText('0,910')).toBeInTheDocument()
  expect(screen.getByText('0,790')).toBeInTheDocument()
  expect(screen.getAllByText(/✓ Cumple la meta/)).toHaveLength(3)
  expect(screen.getByText('215 ms')).toBeInTheDocument()
  expect(llamadas.some((l) => l.ruta === '/modelos/3/metricas')).toBe(true)
})

test('compara los modelos en una tabla', async () => {
  api()
  renderizarEn('/metricas')
  const tabla = await screen.findByRole('table', { name: 'Métricas de validación de cada modelo' })
  const filas = within(tabla).getAllByRole('row').slice(1)
  expect(filas[0]).toHaveTextContent('TF-IDF + SVM lineal (plano)activo')
  expect(filas[1]).toHaveTextContent('0,600')
})

test('cambia de partición y de modelo', async () => {
  const llamadas = api()
  renderizarEn('/metricas')
  fireEvent.click(await screen.findByRole('button', { name: 'Validación' }))
  await waitFor(() =>
    expect(llamadas.at(-1)?.parametros.get('particion')).toBe('validacion'),
  )
  expect(await screen.findByText(/7047|7\.047/)).toBeInTheDocument()

  fireEvent.change(screen.getByLabelText('Modelo'), { target: { value: '1' } })
  await waitFor(() => expect(llamadas.some((l) => l.ruta === '/modelos/1/metricas')).toBe(true))
})

test('la matriz de confusión explica cada celda', async () => {
  api()
  renderizarEn('/metricas')
  const matriz = await screen.findByRole('table', { name: 'Matriz de confusión de dominios' })
  const celdas = within(matriz).getAllByRole('cell')
  expect(celdas.map((c) => c.textContent)).toEqual(['90', '10', '17', '83'])
  fireEvent.focus(celdas[1])
  expect(
    screen.getByText('10 de 100 documentos de «Computer Science» se enviaron a «Medical Sciences» (10,0 %).'),
  ).toBeInTheDocument()
  fireEvent.click(within(matriz.parentElement!.parentElement!).getByRole('button', { name: 'Documentos' }))
  expect(within(matriz).getAllByRole('cell').map((c) => c.textContent)).toEqual(['90', '10', '5', '25'])
})

test('la tabla de áreas se ordena y se filtra', async () => {
  api()
  renderizarEn('/metricas')
  const buscar = await screen.findByPlaceholderText('Buscar área')
  const tabla = buscar.closest('div')!.parentElement!.querySelector('table')!
  const nombres = () => within(tabla)
      .getAllByRole('row')
      .slice(1)
      .map((f) => within(f).getAllByRole('cell')[0].textContent)

  expect(nombres()).toEqual(['Machine learning', 'Cancer', 'Computer vision']) // peor F1 primero
  fireEvent.click(within(tabla).getByRole('button', { name: /^F1/ }))
  expect(nombres()).toEqual(['Computer vision', 'Cancer', 'Machine learning'])
  fireEvent.click(within(tabla).getByRole('button', { name: /^Área/ }))
  expect(nombres()).toEqual(['Cancer', 'Computer vision', 'Machine learning'])

  fireEvent.change(buscar, { target: { value: 'vision' } })
  expect(nombres()).toEqual(['Computer vision'])
})

test('sin modelos registrados explica cómo obtenerlos', async () => {
  simularApi({ 'GET /modelos': { cuerpo: [] }, 'GET /categorias': { cuerpo: CATEGORIAS } })
  renderizarEn('/metricas')
  expect(await screen.findByText('No hay modelos registrados')).toBeInTheDocument()
  expect(await screen.findByText(/1.000 documentos en 2 dominios y 3 áreas/)).toBeInTheDocument()
})
