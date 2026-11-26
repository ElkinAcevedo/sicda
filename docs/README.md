# Documentación

| Documento | Descripción |
| --- | --- |
| Propuesta del proyecto | Objetivos, metodología y cronograma aprobados. |
| Documento de diseño | Requerimientos, arquitectura, datos, pipeline de ML, API, interfaz y plan de pruebas. |
| [`panorama-del-proyecto.md`](panorama-del-proyecto.md) | Guía completa del proyecto: qué se hizo, cómo funciona de principio a fin y dónde está cada cosa en el código. |
| [`pruebas.md`](pruebas.md) | Informe de pruebas: resultados del plan de pruebas (cobertura, e2e, rendimiento, usabilidad). |
| [`decisiones/`](decisiones/) | Registro de decisiones de arquitectura (ADR): qué se decidió, por qué y qué alternativas se descartaron. |

## Registro de decisiones (ADR)

| ADR | Decisión |
| --- | --- |
| [0001](decisiones/0001-stack-tecnologico.md) | Stack tecnológico |
| [0002](decisiones/0002-etiquetas-wos.md) | Etiquetas de dominio y área en WOS-46985 |
| [0003](decisiones/0003-seleccion-modelo.md) | Selección del modelo de clasificación |

Cada decisión importante se documenta en un archivo `NNNN-titulo.md` dentro de `decisiones/`, usando la plantilla de [`0000-plantilla.md`](decisiones/0000-plantilla.md).
