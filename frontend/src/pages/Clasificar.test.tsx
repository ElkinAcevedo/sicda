import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { expect, test } from 'vitest'
import { EJEMPLO } from '@/lib/ejemplo'
import { CATEGORIAS, CLASIFICACION, error, fila, pagina, simularApi } from '@/test/api-falsa'
import { renderizarEn } from '@/test/renderizar'

const BASE = {
  'GET /salud': { cuerpo: { estado: 'activo', version: '0.1.0', modelo_activo: null } },
  'GET /categorias': { cuerpo: CATEGORIAS },
  'GET /clasificaciones': { cuerpo: pagina([]) },
  'GET /clasificaciones/:id': { cuerpo: CLASIFICACION },
}

const RESUMEN = Array.from({ length: 25 }, (_, i) => `word${i}`).join(' ')

function pegarTexto(texto: string, titulo = '') {
  fireEvent.click(screen.getByRole('tab', { name: 'Pegar texto' }))
  if (titulo) fireEvent.change(screen.getByLabelText('Título (opcional)'), { target: { value: titulo } })
  fireEvent.change(screen.getByLabelText('Resumen (abstract) en inglés'), { target: { value: texto } })
}

test('clasifica un texto pegado y abre el resultado', async () => {
  const llamadas = simularApi({ ...BASE, 'POST /clasificaciones/texto': { estado: 201, cuerpo: CLASIFICACION } })
  renderizarEn('/')

  pegarTexto(RESUMEN, 'Mi artículo')
  expect(screen.getByText('25 palabras')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Clasificar' }))

  expect(await screen.findByRole('heading', { name: 'Redes ligeras' })).toBeInTheDocument()
  const envio = llamadas.find((l) => l.metodo === 'POST')
  expect(envio?.cuerpo).toEqual({ texto: RESUMEN, titulo: 'Mi artículo' })
  expect(llamadas.some((l) => l.ruta === '/clasificaciones/7')).toBe(true)
})

test('avisa cuando el texto es corto', () => {
  simularApi(BASE)
  renderizarEn('/')
  pegarTexto('solo cinco palabras de texto')
  expect(screen.getByText(/se necesitan al menos 20/)).toBeInTheDocument()
})

test('un error de la API se muestra con una acción sugerida', async () => {
  simularApi({
    ...BASE,
    'POST /clasificaciones/texto': error('TEXTO_INSUFICIENTE', 'El texto tiene 5 términos.', 422),
  })
  renderizarEn('/')
  pegarTexto('uno dos tres cuatro cinco')
  fireEvent.click(screen.getByRole('button', { name: 'Clasificar' }))

  const alerta = await screen.findByRole('alert')
  expect(alerta).toHaveTextContent('El texto tiene 5 términos.')
  expect(alerta).toHaveTextContent('Pega el resumen completo')
})

test('«Probar con un ejemplo» llena el formulario sin clasificar', async () => {
  const llamadas = simularApi({ ...BASE, 'POST /clasificaciones/texto': { estado: 201, cuerpo: CLASIFICACION } })
  renderizarEn('/')
  fireEvent.click(screen.getByRole('button', { name: 'Probar con un ejemplo' }))

  // El ejemplo queda a la vista para leerlo; todavía no se envía nada.
  const resumen = screen.getByLabelText('Resumen (abstract) en inglés')
  expect(resumen).toHaveValue(EJEMPLO.texto)
  expect(resumen).toHaveFocus()
  expect(screen.getByLabelText('Título (opcional)')).toHaveValue(EJEMPLO.titulo)
  expect(llamadas.some((l) => l.metodo === 'POST')).toBe(false)

  // Se clasifica solo cuando el usuario lo pide.
  fireEvent.click(screen.getByRole('button', { name: 'Clasificar' }))
  expect(await screen.findByRole('heading', { name: 'Redes ligeras' })).toBeInTheDocument()
  expect(llamadas.find((l) => l.metodo === 'POST')?.cuerpo).toEqual({
    texto: EJEMPLO.texto,
    titulo: EJEMPLO.titulo,
  })
})

test('sube un archivo elegido y lo envía como multipart', async () => {
  const llamadas = simularApi({ ...BASE, 'POST /clasificaciones/archivo': { estado: 201, cuerpo: CLASIFICACION } })
  renderizarEn('/')
  const archivo = new File(['%PDF-1.4 contenido'], 'articulo.pdf', { type: 'application/pdf' })
  fireEvent.change(screen.getByLabelText('Archivo a clasificar'), { target: { files: [archivo] } })

  expect(await screen.findByRole('heading', { name: 'Redes ligeras' })).toBeInTheDocument()
  const envio = llamadas.find((l) => l.metodo === 'POST')!
  expect(envio.ruta).toBe('/clasificaciones/archivo')
  expect((envio.cuerpo as FormData).get('archivo')).toBeInstanceOf(File)
})

test('rechaza en el navegador un formato no soportado', async () => {
  const llamadas = simularApi(BASE)
  renderizarEn('/')
  const archivo = new File(['x'], 'foto.png', { type: 'image/png' })
  fireEvent.change(screen.getByLabelText('Archivo a clasificar'), { target: { files: [archivo] } })

  expect(await screen.findByRole('alert')).toHaveTextContent('«foto.png» no es un PDF, DOCX ni TXT.')
  expect(llamadas.some((l) => l.metodo === 'POST')).toBe(false)
})

test('acepta archivos arrastrados', async () => {
  simularApi({ ...BASE, 'POST /clasificaciones/archivo': { estado: 201, cuerpo: CLASIFICACION } })
  renderizarEn('/')
  const archivo = new File(['texto'], 'notas.txt', { type: 'text/plain' })
  fireEvent.drop(screen.getByText('Arrastra aquí tu documento'), { dataTransfer: { files: [archivo] } })
  expect(await screen.findByRole('heading', { name: 'Redes ligeras' })).toBeInTheDocument()
})

test('muestra las últimas clasificaciones o un estado vacío', async () => {
  simularApi({ ...BASE, 'GET /clasificaciones': { cuerpo: pagina([fila(1), fila(2)]) } })
  renderizarEn('/')
  const lista = await screen.findByRole('list')
  expect(within(lista).getAllByRole('link')).toHaveLength(2)
  expect(within(lista).getByText('Artículo 1').closest('a')).toHaveAttribute('href', '/resultado/1')
})

test('sin clasificaciones invita a probar el ejemplo', async () => {
  const llamadas = simularApi(BASE)
  renderizarEn('/')
  expect(await screen.findByText('Todavía no hay clasificaciones')).toBeInTheDocument()
  await waitFor(() =>
    expect(llamadas.find((l) => l.ruta === '/clasificaciones')?.parametros.get('tamano')).toBe('5'),
  )
})
