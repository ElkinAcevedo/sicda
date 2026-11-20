import { expect, test } from 'vitest'
import { palabrasDeTerminos, resaltar } from '@/lib/resaltado'

function marcadas(texto: string, terminos: string[]) {
  return resaltar(texto, terminos)
    .filter((f) => f.resaltado)
    .map((f) => f.texto)
}

test('resalta las formas de un término lematizado', () => {
  expect(marcadas('The model was trained and training continues.', ['train'])).toEqual([
    'trained',
    'training',
  ])
})

test('los bigramas resaltan cada palabra y se ignoran mayúsculas y tildes', () => {
  expect(marcadas('Neural Networks for imágenes', ['neural network', 'imagen'])).toEqual([
    'Neural',
    'Networks',
    'imágenes',
  ])
})

test('acepta hasta tres letras de más tras la raíz', () => {
  expect(marcadas('A trainee and a train', ['train'])).toEqual(['trainee', 'train'])
  expect(marcadas('Cartography', ['car'])).toEqual([])
})

test('sin términos el texto queda igual', () => {
  expect(resaltar('Hola mundo', [])).toEqual([{ texto: 'Hola mundo', resaltado: false }])
  expect(palabrasDeTerminos(['ab', 'deep learning'])).toEqual(['deep', 'learning'])
})

test('reconstruye el texto completo', () => {
  const texto = 'Deep learning, (2026): networks!'
  expect(
    resaltar(texto, ['network'])
      .map((f) => f.texto)
      .join(''),
  ).toBe(texto)
})
