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

- [`docs/idea_principal.md`](docs/idea_principal.md) — Propuesta de tesis refinada
- [`docs/plan_implementacion.md`](docs/plan_implementacion.md) — Plan de implementación por fases

---

## CORSIKA 7.8010 — Instrucciones de Instalación y Uso

### ¿Qué es CORSIKA?

CORSIKA (COsmic Ray SImulations for KAscade) es el estándar de oro para simular cascadas
atmosféricas extensas (EAS). Genera el flujo de partículas secundarias —especialmente muones—
producidas por la interacción de rayos cósmicos primarios con la atmósfera. En este proyecto
se usa para calcular el flujo de muones atmosférico a nivel del suelo en los volcanes guatemaltecos.

**Versión utilizada:** 7.8010  
**Archivo fuente:** `corsika-78050.tar.gz`  
**Distribuidor:** Karlsruhe Institute of Technology (KIT), Campus North

---

### Requisitos del Sistema

- Linux (x86_64 recomendado)
- Fortran compiler: `gfortran` >= 4.8 o `ifort`
- C compiler: `gcc`
- C++ compiler: `g++`
- `make`, `bzip2`, `gunzip`
- Opcional: ROOT (para salida ROOTOUT), Python 3 (para post-procesamiento)

```bash
# Ubuntu/Debian
sudo apt-get install gfortran gcc g++ make bzip2
```

---

### Obtención del Código

El acceso al servidor de CORSIKA requiere credenciales:

- **URL:** https://web.iap.kit.edu/corsika/download/
- **Usuario:** corsika
- **Contraseña:** (se obtiene por correo electrónico al equipo de KIT)

Una vez descargado:

```bash
tar -xzf corsika-78050.tar.gz
cd corsika-78050/
```

---

### Estructura de Directorios

```
corsika-78050/
├── coconut           # Script de instalación interactivo (USAR ESTE, no ./configure)
├── README            # Instrucciones oficiales breves
├── INSTALL           # Guía detallada de uso de coconut
├── doc/
│   ├── CORSIKA_GUIDE78000.pdf   # Manual completo de uso
│   ├── CORSIKA_PHYSICS.pdf      # Descripción física (FZKA 6019)
│   └── coreas-manual.pdf        # Manual opción COREAS
├── src/
│   ├── corsika.F                # Código fuente principal (Fortran + CPP)
│   ├── qgsjet-II-04.f           # Modelo hadrónico alta energía
│   ├── gheisha_2002d.f          # Modelo hadrónico baja energía
│   └── sibyll2.3e.f             # Modelo hadrónico alternativo
├── run/                         # Directorio de ejecución y ejemplos
│   ├── all-inputs*              # Ejemplos de steering files
│   └── QGSDAT*, SECTNU, ...     # Tablas de sección eficaz
├── bernlohr/                    # Paquete para telescopios Cherenkov
├── coast/                       # COAST: interfaz C++ para salida
└── utils/                       # Utilidades de post-procesamiento
    ├── coast/                   # Mejor opción para principiantes (Python/ROOT/ASCII)
    └── gdastool                 # Crea perfiles atmosféricos desde GDAS/ERA5
```

---

### Instalación con `coconut`

**IMPORTANTE:** No usar `./configure` directamente. Siempre usar `./coconut`.

```bash
cd corsika-78050/
./coconut
```

El script `coconut` es interactivo. Para este proyecto seleccionar:

| Opción | Selección | Justificación |
|--------|-----------|---------------|
| High-energy hadronic model | **QGSJET-II-04** | Mejor precisión para fragmentación de núcleos pesados |
| Low-energy hadronic model | **GHEISHA-2002** | Validado para rangos de GeV, compatibilidad probada |
| Geometry | **CURVED** | Necesario para ángulos cenitales grandes (muografía) |
| Output | **Particle output** (default) | Binario estándar compatible con corsika-panama |
| Atmosphere | Standard (luego se reemplaza con ERA5) | |
| Site | **Guatemala** coordinates | Ver parámetros geomagnéticos abajo |

Después de seleccionar opciones, coconut compila automáticamente. El binario queda en `run/`.

---

### Parámetros Críticos para Guatemala

Estos parámetros van en el **steering file** (archivo de entrada de CORSIKA):

```
RUNNR   1                        ! Número de run
EVTNR   1                        ! Primer número de evento
NSHOW   1000                     ! Número de showers a simular
PRMPAR  14                       ! Primario: protón (14=nitrógeno, 1=protón)
ESLOPE  -2.7                     ! Índice espectral del flujo de rayos cósmicos
ERANGE  1.E1 1.E5                ! Rango de energía: 10 GeV a 100 TeV
THETAP  0.  89.                  ! Ángulo cenital: 0°-89° (horizontal para muografía)
PHIP    0.  360.                 ! Ángulo azimutal: todos
SEED    1 0 0                    ! Semillas random
OBSLEV  2552.E2                  ! Altitud de observación en cm (Pacaya: 2552 msnm)
FIXHEI  0. 0                     ! Primera interacción: libre
FIXCHI  0.                       ! Profundidad atmosférica primera interacción: libre
MAGNET  27.3 -13.6               ! Campo geomagnético Guatemala (Bx, Bz en µT)
HADFLG  0 1 0 1 0 2              ! Flags modelos hadrónicos
ECUTS   0.3 0.3 0.003 0.003      ! Energías de corte: hadrones, muones, e±, γ (GeV)
MUADDI  T                        ! Información adicional de muones (para muografía)
MUMULT  T                        ! Interacciones múltiples de muones
LONGI   T 20. T T                ! Perfil longitudinal del shower
MAXPRT  1                        ! Máximo de eventos impresos en .lst
PAROUT  T F                      ! Salida de partículas: activada
TELESCOPE 0. 0. 0. 0. 1. 5.E2   ! Definición del área del detector (para IACT)
EXIT                             ! Fin del steering file
```

#### Campo geomagnético por volcán

| Volcán | Latitud | Longitud | Bx (µT) | Bz (µT) | Alt. (msnm) |
|--------|---------|----------|---------|---------|-------------|
| Fuego | 14.47°N | 90.88°W | ~27.5 | ~-14.1 | 3763 |
| Acatenango | 14.50°N | 90.88°W | ~27.5 | ~-14.1 | 3976 |
| Pacaya | 14.38°N | 90.60°W | ~27.3 | ~-13.6 | 2552 |
| Volcán de Agua | 14.46°N | 90.74°W | ~27.4 | ~-13.8 | 3760 |

> Los valores exactos de Bx/Bz se obtienen del IGRF-13 (International Geomagnetic Reference
> Field) en https://www.ngdc.noaa.gov/geomag/calculators/magcalc.shtml

#### Perfil atmosférico ERA5

CORSIKA incluye perfiles estándar (US Standard Atmosphere, etc.), pero para mayor precisión
en Guatemala se deben usar datos ERA5 de ECMWF. El proceso:

```bash
# 1. Descargar datos ERA5 para la región (requiere cuenta CDS Copernicus)
# 2. Convertir al formato CORSIKA usando gdastool (incluido en src/utils/)
cd corsika-78050/src/utils/
python gdastool --date YYYY-MM-DD --lat 14.5 --lon -90.9 --out atm_guatemala.dat

# 3. Referenciar el perfil en el steering file con la opción ATMOSPHERE
```

---

### Ejecución

```bash
cd corsika-78050/run/
./corsika7810Linux_QGSII_gheisha < steering_fuego.inp > fuego_run001.lst
```

La salida genera dos archivos:
- `DAT000001` — archivo binario con todas las partículas (puede ser de decenas de GB)
- `fuego_run001.lst` — log con información de cada shower

---

### Post-procesamiento en Python

El formato binario de CORSIKA 7 es complejo. Se recomienda `corsika-panama`:

```bash
pip install corsika-panama
```

```python
import corsika_panama as cp

# Leer archivo de partículas
with cp.reader("DAT000001") as f:
    for event in f:
        particles = event.particles
        muons = particles[particles.particle_id == 5]  # muones µ+
        # → DataFrame con: x, y, px, py, pz, t, energy
```

Alternativa: usar la interfaz COAST incluida en `coast/` para acceso al vuelo sin guardar
el binario completo en disco.

---

### Modelos Hadrónicos Disponibles

| Modelo | Rango | Uso recomendado |
|--------|-------|-----------------|
| QGSJET-II-04 | > 80 GeV | Alta energía — principal para este proyecto |
| GHEISHA-2002 | < 80 GeV | Baja energía — complementa QGSJET |
| SIBYLL 2.3e | > 80 GeV | Alternativa para estudios de incertidumbre |
| FLUKA | < 80 GeV | Alternativa de alta precisión (requiere licencia separada) |
| EPOS-LHC | > 80 GeV | Modelo más reciente, mayor costo computacional |

---

### Energías de Corte Recomendadas para Muografía

```
ECUTS   0.3   0.01   0.003   0.003
         ^      ^      ^       ^
      hadrones muones  e±      γ  (todos en GeV)
```

El umbral de 10 MeV para muones captura las contribuciones de baja energía relevantes
en volcanes de alta altitud (>2500 msnm), donde la profundidad atmosférica reducida
aumenta el flujo de muones de baja energía.

---

### Estimación de Recursos Computacionales

| Configuración | Showers | Tiempo estimado | Almacenamiento |
|--------------|---------|-----------------|----------------|
| Prueba rápida | 100 | ~10 min | ~500 MB |
| Estadística mínima | 10,000 | ~8 horas | ~50 GB |
| Dataset ML (training) | 100,000 | ~3-5 días | ~500 GB |
| Producción completa | 1,000,000 | ~semanas | ~5 TB |

Se recomienda usar el modo paralelo (opción PARALLEL o scripts MPI en `src/parallel/`)
para runs de producción en clusters.

---

### Archivos de Ejemplo

En `run/` se incluyen 11 ejemplos de steering files:

```
all-inputs          # Configuración básica sin opciones especiales
all-inputs-thin     # Con THIN (thinning) para grandes energías
conex-*-inputs      # Con módulo CONEX (híbrido)
parallel-inputs     # Para ejecución paralela MPI
```

---

### Referencias

- D. Heck et al., *CORSIKA: A Monte Carlo Code to Simulate Extensive Air Showers*,
  Report FZKA 6019, Forschungszentrum Karlsruhe (1998).
- T. Pierog et al., *EPOS LHC: Test of collective hadronization with data measured
  at the CERN Large Hadron Collider*, Phys. Rev. C 92, 034906 (2015).
- Vesga-Ramírez et al., *Muon Tomography sites for Colombian volcanoes*,
  arXiv:1705.09884v2 (2019). — Referencia principal de metodología para este proyecto.

---

### Contacto KIT para problemas con CORSIKA 7.8xxx

**T. Pierog** — tanguy.pierog@kit.edu
