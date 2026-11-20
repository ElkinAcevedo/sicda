import { fireEvent, screen, within } from '@testing-library/react'
import { expect, test } from 'vitest'
import type { ClasificacionDetalle } from '@/api/cliente'
import { CATEGORIAS, CLASIFICACION, error, simularApi } from '@/test/api-falsa'
import { renderizarEn } from '@/test/renderizar'

function api(clasificacion: ClasificacionDetalle = CLASIFICACION, extra = {}) {
  return simularApi({
    'GET /salud': { cuerpo: { estado: 'activo', version: '0.1.0', modelo_activo: null } },
    'GET /categorias': { cuerpo: CATEGORIAS },
    'GET /clasificaciones/:id': { cuerpo: clasificacion },
    ...extra,
  })
}

test('muestra dominio, área, confianzas, alternativas y términos', async () => {
  api()
  renderizarEn('/resultado/7')

  expect(await screen.findByRole('heading', { name: 'Redes ligeras' })).toBeInTheDocument()
  expect(screen.getByRole('meter', { name: 'Confianza del dominio' })).toHaveAttribute('aria-valuenow', '92')
  expect(screen.getByRole('meter', { name: 'Confianza del área' })).toHaveAttribute('aria-valuenow', '55')
  expect(screen.getByRole('meter', { name: 'Confianza conjunta' })).toHaveAttribute('aria-valuenow', '51')
  expect(await screen.findByText('Ciencias de la computación')).toBeInTheDocument()
  expect(screen.getAllByText('Machine learning').length).toBeGreaterThan(0)
  const terminos = screen.getByRole('list', { name: 'Términos clave' })
  expect(within(terminos).getAllByRole('listitem').map((t) => t.textContent)).toEqual(['convolutional', 'train'])
})

test('resalta en el texto los términos que pesaron', async () => {
  api()
  const { container } = renderizarEn('/resultado/7')
  await screen.findByRole('heading', { name: 'Redes ligeras' })
  const marcas = [...container.querySelectorAll('mark')].map((m) => m.textContent)
  expect(marcas).toEqual(['Convolutional', 'trained'])
})

test('avisa si requiere revisión y muestra las advertencias de la API', async () => {
  api({
    ...CLASIFICACION,
    requiere_revision: true,
    advertencias: [{ codigo: 'IDIOMA_NO_SOPORTADO', mensaje: 'El texto parece estar en «es».' }],
  })
  renderizarEn('/resultado/7')
  expect(await screen.findByText('Requiere revisión')).toBeInTheDocument()
  expect(screen.getByText('El texto parece estar en «es».')).toBeInTheDocument()
})

test('guarda una corrección y la muestra', async () => {
  const corregida: ClasificacionDetalle = {
    ...CLASIFICACION,
    correccion: {
      dominio_correcto: 'Medical Sciences',
      area_correcta: 'Cancer',
      comentario: null,
      creado_en: '2026-11-19T16:00:00',
    },
  }
  const llamadas = api(CLASIFICACION, { 'POST /clasificaciones/:id/correccion': { cuerpo: corregida } })
  renderizarEn('/resultado/7')

  fireEvent.click(await screen.findByRole('button', { name: '¿No es correcto?' }))
  const formulario = screen.getByRole('form', { name: 'Corregir clasificación' })
  const dominio = within(formulario).getByLabelText('Dominio correcto')
  await within(dominio).findByRole('option', { name: /Medical Sciences/ })
  fireEvent.change(dominio, { target: { value: 'Medical Sciences' } })
  // El área solo ofrece las del dominio elegido.
  const area = within(formulario).getByLabelText('Área correcta (opcional)')
  expect(within(area).getAllByRole('option').map((o) => o.textContent)).toEqual(['No lo sé', 'Cancer'])
  fireEvent.change(area, { target: { value: 'Cancer' } })
  fireEvent.click(within(formulario).getByRole('button', { name: 'Guardar corrección' }))

  expect(await screen.findByText('Corregida por el usuario')).toBeInTheDocument()
  expect(screen.queryByRole('form', { name: 'Corregir clasificación' })).not.toBeInTheDocument()
  expect(llamadas.find((l) => l.metodo === 'POST')).toMatchObject({
    ruta: '/clasificaciones/7/correccion',
    cuerpo: { dominio_correcto: 'Medical Sciences', area_correcta: 'Cancer', comentario: null },
  })
})

test('un error al corregir se muestra sin cerrar el formulario', async () => {
  api(CLASIFICACION, {
    'POST /clasificaciones/:id/correccion': error('ENTRADA_INVALIDA', 'El dominio no existe.', 400),
  })
  renderizarEn('/resultado/7')
  fireEvent.click(await screen.findByRole('button', { name: '¿No es correcto?' }))
  const dominio = screen.getByLabelText('Dominio correcto')
  await within(dominio).findByRole('option', { name: /Medical Sciences/ })
  fireEvent.change(dominio, { target: { value: 'Medical Sciences' } })
  fireEvent.click(screen.getByRole('button', { name: 'Guardar corrección' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('El dominio no existe.')
  expect(screen.getByRole('form', { name: 'Corregir clasificación' })).toBeInTheDocument()
})

test('una clasificación inexistente muestra el error y permite reintentar', async () => {
  simularApi({ 'GET /clasificaciones/:id': error('NO_ENCONTRADO', 'No existe la clasificación 99.', 404) })
  renderizarEn('/resultado/99')
  const alerta = await screen.findByRole('alert')
  expect(alerta).toHaveTextContent('No existe la clasificación 99.')
  expect(within(alerta).getByRole('button', { name: 'Reintentar' })).toBeInTheDocument()
})
