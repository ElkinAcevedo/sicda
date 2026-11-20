import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

// Recharts mide su contenedor con ResizeObserver, que jsdom no trae.
class ResizeObserverFalso {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverFalso as unknown as typeof ResizeObserver

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  document.documentElement.classList.remove('dark')
  localStorage.clear()
})
