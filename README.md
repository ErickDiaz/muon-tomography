# Physics Master Thesis — Muon Tomography of Guatemalan Volcanoes

Simulación de flujos de muones con CORSIKA y aprendizaje profundo aplicado a la muografía
de edificios volcánicos en Guatemala.

---

## Resumen del Proyecto

La muografía es una técnica no invasiva que usa muones atmosféricos —partículas cargadas
producidas por rayos cósmicos— para obtener imágenes de densidad interna de grandes estructuras
geológicas. Este proyecto aplica esa técnica a cuatro volcanes guatemaltecos mediante una cadena
de simulación computacional, con el objetivo de identificar los sitios óptimos para colocar un
telescopio de muones y estimar los tiempos de exposición necesarios.

La contribución principal sobre el trabajo de referencia colombiano (Vesga-Ramírez et al., 2019)
es la integración de aprendizaje profundo para: (a) acelerar la simulación mediante modelos
subrogados y/o (b) mejorar la resolución espacial de los muogramas resultantes.

### Volcanes de Estudio

| Volcán | Rol en el Proyecto | Altitud | Composición | Estado |
|--------|--------------------|---------|-------------|--------|
| **Fuego** | Objetivo principal | 3,763 msnm | Basalto | Altamente activo |
| **Acatenango** | Calibración (masa conocida) | 3,976 msnm | Andesita | Dormido |
| **Pacaya** | Candidato secundario | 2,552 msnm | Basalto de Olivino | Persistente |
| **Volcán de Agua** | Candidato secundario / calibración | 3,760 msnm | Andesita | Dormido |

**Estrategia:** análisis de selección de sitio para los cuatro volcanes → análisis profundo
de Fuego como objetivo científico principal → Acatenango y Volcán de Agua como referencias
de calibración con composición petroquímica conocida.

### Documentación del Proyecto

| Documento | Descripción |
|-----------|-------------|
| [`docs/idea_principal.md`](docs/idea_principal.md) | Propuesta de tesis refinada, volcanes, hipótesis |
| [`docs/plan_implementacion.md`](docs/plan_implementacion.md) | Plan por fases y estructura de capítulos |
| [`docs/corsika_parametros.md`](docs/corsika_parametros.md) | Parámetros CORSIKA con justificación física detallada |
| [`docs/corsika_instalacion.md`](docs/corsika_instalacion.md) | Instalación, compilación y ejecución de CORSIKA 7.8010 |
| [`sim/README.md`](sim/README.md) | Cómo correr las simulaciones y leer la salida |
| [`sim/steering/`](sim/steering/) | Steering files listos para los 4 volcanes |
