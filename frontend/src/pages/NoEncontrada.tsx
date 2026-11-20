import { Link } from 'react-router-dom'
import { Aviso } from '@/components/ui'

export function NoEncontrada() {
  return (
    <Aviso tono="info" titulo="Esta página no existe">
      <Link to="/" className="font-medium underline">
        Volver a Clasificar
      </Link>
    </Aviso>
  )
}
