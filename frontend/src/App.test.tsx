import { fireEvent, render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'
import App from '@/App'
import { renderizarEn } from '@/test/renderizar'
import { pagina, simularApi } from '@/test/api-falsa'

test('muestra la navegación principal', () => {
  vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('sin API'))
  render(<App />)
  for (const nombre of ['Clasificar', 'Historial', 'Métricas']) {
    expect(screen.getByRole('link', { name: nombre })).toBeInTheDocument()
  }
})

test('indica si la API está activa y qué modelo tiene', async () => {
  simularApi({
    'GET /salud': { cuerpo: { estado: 'activo', version: '0.1.0', modelo_activo: 'SVM v1' } },
    'GET /clasificaciones': { cuerpo: pagina([]) },
  })
  renderizarEn('/')
  expect(await screen.findByText('API: activa')).toBeInTheDocument()
  expect(screen.getByText('Modelo: SVM v1')).toBeInTheDocument()
})

test('avisa cuando la API no responde', async () => {
  vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'))
  renderizarEn('/')
  expect(await screen.findByText('API: sin conexión')).toBeInTheDocument()
})

test('el modo oscuro se activa y se recuerda', () => {
  vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('sin API'))
  renderizarEn('/')
  fireEvent.click(screen.getByRole('button', { name: /modo oscuro/i }))
  expect(document.documentElement).toHaveClass('dark')
  expect(localStorage.getItem('sicda-tema')).toBe('oscuro')
  fireEvent.click(screen.getByRole('button', { name: /modo claro/i }))
  expect(document.documentElement).not.toHaveClass('dark')
})

test('una ruta desconocida muestra un aviso', async () => {
  vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('sin API'))
  renderizarEn('/no-existe')
  expect(await screen.findByText('Esta página no existe')).toBeInTheDocument()
})
