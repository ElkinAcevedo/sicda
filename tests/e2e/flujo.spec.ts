import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { expect, test, type Page } from '@playwright/test'

/**
 * Flujo del plan de pruebas: cargar un PDF real → ver el resultado → encontrarlo en el
 * historial → corregirlo. Corre contra la API real con el modelo diminuto de `preparar.py`
 * (2 dominios y 4 áreas), así que las predicciones son de verdad, no simuladas.
 *
 * Chromium y Firefox comparten la base, y la API reutiliza los documentos con el mismo
 * contenido: por eso cada navegador sube su propio PDF y su propio texto.
 */
const aqui = path.dirname(fileURLToPath(import.meta.url))

async function subir(page: Page, nombre: string, buffer: Buffer, mimeType: string) {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Clasificar documento' })).toBeVisible()
  await page.getByLabel('Archivo a clasificar').setInputFiles({ name: nombre, mimeType, buffer })
}

/** Busca en el historial (por título o nombre de archivo) y devuelve las filas con `textoFila`. */
async function buscarEnHistorial(page: Page, busqueda: string, textoFila: string) {
  await page.getByRole('navigation', { name: 'Principal' }).getByRole('link', { name: /Historial/ }).click()
  await page.getByRole('searchbox').fill(busqueda)
  await page.getByRole('button', { name: 'Filtrar' }).click()
  return page.getByRole('row').filter({ hasText: textoFila })
}

test('clasifica un PDF, lo encuentra en el historial y lo corrige', async ({ page }, info) => {
  const nombre = `articulo-${info.project.name}.pdf`
  // El título lo genera `preparar.py`; la API lo extrae de la primera línea del PDF.
  const titulo = `Camera based object detection and segmentation in video (${info.project.name})`
  const pdf = readFileSync(path.join(aqui, '.recursos', nombre))

  // 1. Cargar el PDF: el sistema extrae el título, encuentra el «Abstract» y lo clasifica.
  await subir(page, nombre, pdf, 'application/pdf')
  await expect(page).toHaveURL(/\/resultado\/\d+$/)
  await expect(page.getByRole('heading', { level: 1, name: titulo })).toBeVisible()
  await expect(page.getByText(nombre)).toBeVisible()
  await expect(page.getByText('Computer Science').first()).toBeVisible()
  await expect(page.getByText('Computer vision').first()).toBeVisible()
  await expect(page.getByText('Resumen (Abstract) encontrado')).toBeVisible()
  await expect(page.getByRole('list', { name: 'Términos clave' })).toBeVisible()

  // 2. Encontrarlo en el historial y abrirlo de nuevo.
  const fila = await buscarEnHistorial(page, nombre, titulo)
  await expect(fila).toHaveCount(1)
  await expect(fila).toContainText('Computer vision')
  await fila.getByRole('link', { name: titulo }).click()
  await expect(page).toHaveURL(/\/resultado\/\d+$/)

  // 3. Corregirlo: la corrección se guarda junto a la predicción original.
  await page.getByRole('button', { name: '¿No es correcto?' }).click()
  const formulario = page.getByRole('form', { name: 'Corregir clasificación' })
  await formulario.getByLabel('Dominio correcto').selectOption('Medical')
  await formulario.getByLabel('Área correcta (opcional)').selectOption('Cancer')
  await formulario.getByLabel('Comentario (opcional)').fill('Prueba de extremo a extremo')
  await formulario.getByRole('button', { name: 'Guardar corrección' }).click()
  await expect(page.getByText('Corregida por el usuario')).toBeVisible()
  await expect(page.getByText('Prueba de extremo a extremo')).toBeVisible()

  // 4. El historial marca la clasificación como corregida, también tras recargar.
  await page.reload()
  await expect(page.getByText('Corregida por el usuario')).toBeVisible()
  await expect(await buscarEnHistorial(page, nombre, titulo)).toContainText('Corregida')
})

test('clasifica un texto pegado', async ({ page }, info) => {
  const titulo = `Texto de prueba ${info.project.name}`
  await page.goto('/')
  await page.getByRole('tab', { name: 'Pegar texto' }).click()
  await page.getByLabel('Título (opcional)').fill(titulo)
  await page
    .getByLabel('Resumen (abstract) en inglés')
    .fill(
      'Coronary artery disease and hypertension increase blood pressure in the heart. ' +
        'This cardiac study measures valve function, artery stiffness and blood pressure ' +
        `in patients with hypertension and coronary heart disease (${info.project.name}).`,
    )
  await page.getByRole('button', { name: 'Clasificar', exact: true }).click()
  await expect(page).toHaveURL(/\/resultado\/\d+$/)
  await expect(page.getByRole('heading', { level: 1, name: titulo })).toBeVisible()
  await expect(page.getByText('Medical').first()).toBeVisible()
  await expect(page.getByText('Cardiology').first()).toBeVisible()
})

test('muestra el error de la API cuando el texto no alcanza', async ({ page }, info) => {
  const corto = Buffer.from('Too short to classify.')
  await subir(page, `corto-${info.project.name}.txt`, corto, 'text/plain')
  await expect(page.getByText(/al menos 20 palabras/)).toBeVisible()
  await expect(page).toHaveURL(/\/$/)
})
