# CORSIKA 7.8050 — Instalación y Ejecución

CORSIKA (COsmic Ray SImulations for KAscade) es el estándar de oro para simular cascadas
atmosféricas extensas (EAS). Genera el flujo de partículas secundarias —especialmente muones—
producidas por la interacción de rayos cósmicos primarios con la atmósfera.

**Versión:** 7.8050 | **Archivo:** `corsika-78050.tar.gz` | **Distribuidor:** KIT Campus North

Para la selección de parámetros físicos específicos de Guatemala ver
[`corsika_parametros.md`](corsika_parametros.md).
Para los steering files de cada volcán ver [`../sim/steering/`](../sim/steering/).

---

## Obtención del Código

El servidor de CORSIKA requiere credenciales que se obtienen por correo al equipo KIT:

- **URL:** https://web.iap.kit.edu/corsika/download/
- **Usuario:** `corsika`
- **Contraseña:** solicitarla a tanguy.pierog@kit.edu

Una vez descargado:

```bash
tar -xzf corsika-78050.tar.gz
cd corsika-78050/
```

---

## Requisitos del Sistema

- Linux x86_64 (probado en Ubuntu 20.04+, Debian 11+)
- `gfortran` >= 4.8 o `ifort`
- `gcc`, `g++`
- `make`, `bzip2`
- Python 3 (post-procesamiento, no requerido para compilar)
- ROOT (opcional, solo para salida ROOTOUT)

```bash
# Ubuntu / Debian
sudo apt-get install gfortran gcc g++ make bzip2
```

---

## Estructura del Paquete

```
corsika-78050/
├── coconut               # Script de instalación — USAR ESTE, nunca ./configure
├── INSTALL               # Guía detallada de uso de coconut
├── doc/
│   ├── CORSIKA_GUIDE78000.pdf    # Manual completo
│   ├── CORSIKA_PHYSICS.pdf       # Descripción física (FZKA 6019)
│   └── MPI-Runner_GUIDE.pdf      # Ejecución paralela en cluster
├── src/
│   ├── corsika.F                 # Código fuente principal (Fortran + CPP)
│   ├── qgsjet-II-04.f            # Modelo hadrónico alta energía
│   ├── gheisha_2002d.f           # Modelo hadrónico baja energía
│   └── sibyll2.3e.f              # Modelo hadrónico alternativo
├── run/                          # Directorio de ejecución
│   ├── all-inputs*               # Steering files de ejemplo
│   └── QGSDAT*, SECTNU, ...      # Tablas de sección eficaz (requeridas en runtime)
├── coast/                        # Interfaz C++ para lectura de salida
└── src/utils/
    ├── coast/                    # Mejor opción para leer salida (Python/ROOT/ASCII)
    └── gdastool                  # Convierte perfiles GDAS/ERA5 al formato CORSIKA
```

---

## Instalación con `coconut`

`coconut` es un script interactivo que configura y compila CORSIKA. Reemplaza a `./configure`.

```bash
cd corsika-78050/
./coconut
```

### Opciones para este proyecto

Cuando `coconut` pregunte, seleccionar:

| Pregunta | Selección | Por qué |
|----------|-----------|---------|
| High-energy hadronic model | **QGSJET-II-04** | Calibrado con LHC, estándar en muografía volcánica |
| Low-energy hadronic model | **GHEISHA-2002** | Bien validado, complementa QGSJET por debajo de 80 GeV |
| Geometry | **CURVED** | Obligatorio para θ > 70° (muones casi horizontales) |
| Output format | **Particle output** (default) | Compatible con `corsika-panama` y COAST |
| Atmosphere | Standard | Se reemplaza por ERA5 en el steering file |

Después de confirmar las opciones, `coconut` compila automáticamente. El binario queda en:

```
corsika-78050/run/corsika78050Linux_QGSII_gheisha
```

### Verificar la compilación

```bash
cd corsika-78050/run/
./corsika78050Linux_QGSII_gheisha < all-inputs > validation.lst 2>&1
grep "END OF RUN" validation.lst
# Salida esperada: " END OF RUN   EVENT:  10 ..."
```

---

## Ejecución

El binario lee un steering file desde stdin y escribe el log a stdout:

```bash
cd corsika-78050/run/

./corsika78050Linux_QGSII_gheisha \
    < /ruta/al/steering_file.inp \
    > /ruta/al/output.lst
```

### Salida generada

| Archivo | Descripción | Tamaño típico |
|---------|-------------|---------------|
| `DAT{RUNNR}` | Partículas al nivel de observación (binario) | 500 MB – 50 GB |
| `output.lst` | Log del run con info de cada shower | 1–100 MB |

El archivo DAT va al directorio especificado en `DIRECT` dentro del steering file.

### Ejecución paralela (cluster)

Para corridas de producción con miles de showers usar los scripts MPI incluidos:

```bash
# Ver instrucciones en:
cat corsika-78050/doc/MPI-Runner_GUIDE.pdf
# Scripts en:
ls corsika-78050/src/parallel/
```

Cada proceso paralelo debe tener un `RUNNR` y `SEED` distintos para evitar correlaciones.

---

## Post-procesamiento en Python

El formato binario de CORSIKA 7 requiere una librería para leerlo. La opción más simple:

```bash
pip install corsika-panama
```

```python
import corsika_panama as cp
import numpy as np

with cp.reader("DAT001001") as f:
    for event in f:
        p = event.particles
        # IDs: 5=µ+, 6=µ-, 1=fotón, 2=e+, 3=e-
        muons = p[np.isin(p.particle_id, [5, 6])]
        print(f"Event {event.header.event_number}: {len(muons)} muones")
        # Columnas: x, y, px, py, pz, t, particle_id, weight
```

**Alternativa sin guardar el DAT completo:** usar COAST (`corsika-78050/coast/`),
que permite procesar eventos al vuelo durante la simulación, útil cuando el
almacenamiento es limitado.

---

## Modelos Hadrónicos Disponibles

| Modelo | Rango de energía | Estado en este proyecto |
|--------|-----------------|------------------------|
| QGSJET-II-04 | > 80 GeV | **Seleccionado** — alta energía |
| GHEISHA-2002 | < 80 GeV | **Seleccionado** — baja energía |
| SIBYLL 2.3e | > 80 GeV | Disponible para comparación sistemática |
| EPOS-LHC | > 80 GeV | Disponible, mayor costo computacional |
| FLUKA | < 80 GeV | Mayor precisión que GHEISHA; requiere licencia separada |

---

## Estimación de Recursos

| Corrida | NSHOW | Tiempo (CPU único) | Almacenamiento DAT |
|---------|-------|--------------------|--------------------|
| Prueba | 500 | ~8 min | ~250 MB |
| Estadística mínima | 10,000 | ~3 horas | ~5 GB |
| Producción por volcán | 50,000 | ~15 horas | ~25 GB |
| Dataset ML completo | 500,000 | ~6 días | ~250 GB |

---

## Archivos de Ejemplo Incluidos

En `corsika-78050/run/` hay 11 steering files de ejemplo:

```
all-inputs            Configuración básica, sin opciones especiales
all-inputs-thin       Con THIN (energías > 10¹⁵ eV, no aplica aquí)
conex-*-inputs        Con módulo CONEX (híbrido analítico-Monte Carlo)
parallel-inputs       Ejecución distribuida con MPI
```

---

## Referencias

- D. Heck et al., *CORSIKA: A Monte Carlo Code to Simulate Extensive Air Showers*,
  Report FZKA 6019, Forschungszentrum Karlsruhe (1998).
- T. Pierog et al., *EPOS LHC*, Phys. Rev. C 92, 034906 (2015).
- Manual oficial: `corsika-78050/doc/CORSIKA_GUIDE78000.pdf`

**Soporte técnico CORSIKA 7.8xxx:** tanguy.pierog@kit.edu
