import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Rutas } from '@/App'

/** Monta la aplicación completa en una ruta, con un router en memoria. */
export function renderizarEn(ruta: string) {
  return render(
    <MemoryRouter initialEntries={[ruta]}>
      <Rutas />
    </MemoryRouter>,
  )
}
