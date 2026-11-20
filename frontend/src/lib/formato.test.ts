import { expect, test } from 'vitest'
import { aFecha, colorDominio, COLOR_SIN_DOMINIO, decimal, nivelConfianza, porcentaje } from '@/lib/formato'

test('porcentaje y decimal en formato español', () => {
  expect(porcentaje(0.734)).toBe('73 %')
  expect(porcentaje(0.734, 1)).toBe('73,4 %')
  expect(porcentaje(null)).toBe('—')
  expect(decimal(0.78125)).toBe('0,781')
  expect(decimal(undefined)).toBe('—')
})

test('la confianza se clasifica en verde, ámbar y rojo', () => {
  expect(nivelConfianza(0.7)).toBe('alta')
  expect(nivelConfianza(0.69)).toBe('media')
  expect(nivelConfianza(0.4)).toBe('media')
  expect(nivelConfianza(0.39)).toBe('baja')
})

test('las fechas de la API se leen como UTC', () => {
  expect(aFecha('2026-11-19T15:00:00').toISOString()).toBe('2026-11-19T15:00:00.000Z')
  expect(aFecha('2026-11-19T15:00:00+02:00').toISOString()).toBe('2026-11-19T13:00:00.000Z')
})

test('cada dominio tiene un color fijo', () => {
  expect(colorDominio(0)).not.toBe(colorDominio(1))
  expect(colorDominio(0)).toBe(colorDominio(0))
  expect(colorDominio(undefined)).toBe(COLOR_SIN_DOMINIO)
})
