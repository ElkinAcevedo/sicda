# Frontend · Dashboard web

Aplicación de una sola página con **React 19 + TypeScript + Vite**, estilizada con **Tailwind CSS 4**
y con gráficos de **Recharts**. Sigue la sección 8 del documento de diseño.

## Vistas

| Ruta | Vista | Contenido |
| --- | --- | --- |
| `/` | Clasificar | Arrastrar y soltar PDF/DOCX/TXT (≤ 10 MB), pestaña «Pegar texto», «Probar con un ejemplo», progreso por etapas y las 5 últimas clasificaciones. |
| `/resultado/:id` | Resultado | Tarjetas de dominio y área con su confianza (verde ≥ 70 %, ámbar 40–70 %, rojo < 40 %), confianza conjunta, top 3 de alternativas por nivel, términos clave, texto leído con los términos resaltados, avisos de revisión e idioma y «¿No es correcto?» para corregir. |
| `/historial` | Historial | Tabla paginada (fecha, documento, dominio, área, confianza, estado) con búsqueda y filtros por dominio, estado y fechas. Los filtros van en la URL; cada fila abre su resultado. |
| `/metricas` | Métricas | KPI del modelo elegido con sus metas, validación o prueba, comparación de los 3 modelos, matriz de confusión de dominios y de áreas por dominio (interactivas), F1 por área ordenable y distribución del dataset. |

Además: modo oscuro (recordado en el navegador), diseño adaptable desde 360 px, navegación por
teclado (enlace «Saltar al contenido», celdas de la matriz enfocables) y un color fijo por
dominio en etiquetas, gráficos y matrices.

## Estructura

```text
frontend/src/
├── api/
│   ├── tipos.ts          # tipos del contrato de la API (sincronizar con backend/app/schemas)
│   └── cliente.ts        # cliente HTTP; los errores llegan como ErrorApi(codigo, mensaje)
├── components/           # Layout, ui (tarjetas, botones, avisos), ZonaArchivo, ProgresoEtapas,
│                         # FormularioCorreccion, MatrizConfusion, TablaAreas
├── lib/                  # formato, colores, resaltado de términos, hooks, errores, ejemplo
├── pages/                # Clasificar, Resultado, Historial, Metricas (+ sus pruebas)
├── test/                 # setup de Vitest, API falsa y renderizado con MemoryRouter
├── App.tsx               # rutas (Métricas se carga bajo demanda: trae Recharts)
└── index.css             # Tailwind, modo oscuro por clase y fuente Inter
```

Importa siempre con el alias `@/`, por ejemplo `import { api } from '@/api/cliente'`.

## Comandos

| Comando | Qué hace |
| --- | --- |
| `npm install` | Instala dependencias. |
| `npm run dev` | Servidor de desarrollo en <http://localhost:5173>. La API debe estar en el puerto 8000: `/api` se redirige a ella. |
| `npm run build` | Verifica tipos y compila a `dist/`. |
| `npm test` | Pruebas con Vitest y Testing Library (la API se simula, no hace falta el backend). |
| `npm run lint` | Revisión de estilo con oxlint. |

## Decisiones

- **Sin shadcn/ui.** El diseño lo menciona, pero las vistas solo necesitan unos pocos componentes
  (tarjetas, botones, avisos, barras), escritos directamente con Tailwind en
  `components/ui.tsx`. Así no se suman Radix ni la configuración de shadcn.
- **Inter se incluye en el paquete** (`@fontsource-variable/inter`): no se piden fuentes a Google y
  el dashboard funciona sin internet.
- **Progreso por etapas.** La API responde en una sola solicitud, así que las etapas
  (extrayendo → analizando → clasificando) avanzan por tiempo mientras se espera la respuesta.
- **Resaltado aproximado.** Los términos clave vienen lematizados («train»); se resaltan las
  palabras del texto que empiezan por el término con hasta 3 letras más («trained», «trains»).
