# Directorio de Simulaciones

```
sim/
├── steering/           # Steering files (archivos de entrada para CORSIKA)
│   ├── fuego_test.inp      — Fuego, 500 showers, prueba rápida (~8 min)
│   ├── fuego_prod.inp      — Fuego, 50,000 showers, producción (~3 días)
│   ├── acatenango_test.inp — Acatenango, calibración primaria
│   ├── pacaya_test.inp     — Pacaya, candidato secundario
│   └── agua_test.inp       — Volcán de Agua, calibración secundaria
├── atmosphere/         — Perfiles ERA5 convertidos para CORSIKA (generar con gdastool)
└── output/             — Archivos DAT y .lst generados por CORSIKA (NO versionar)
```

## Cómo correr una simulación de prueba

El binario de CORSIKA queda en `corsika-78050/run/` después de compilar.
Desde ese directorio, apuntar al steering file de este proyecto:

```bash
cd corsika-78050/run/

# Prueba rápida (~8 min, 500 showers)
./corsika78050Linux_QGSII_gheisha \
    < /home/erick/Documents/ecfm/physics-master-thesis/sim/steering/fuego_test.inp \
    > /home/erick/Documents/ecfm/physics-master-thesis/sim/output/fuego_test_001.lst

# Verificar que terminó correctamente
grep "END OF RUN" sim/output/fuego_test_001.lst
```

## Convención de nombres de archivos de salida

CORSIKA genera archivos con el nombre `DATrrrrrr` donde `rrrrrr` es el RUNNR con ceros.

| Steering file | RUNNR | Archivo DAT generado |
|--------------|-------|----------------------|
| fuego_test.inp | 1001 | DAT001001 |
| acatenango_test.inp | 2001 | DAT002001 |
| pacaya_test.inp | 3001 | DAT003001 |
| agua_test.inp | 4001 | DAT004001 |
| fuego_prod.inp | 1101 | DAT001101 |

El archivo DAT va al directorio especificado en `DIRECT` del steering file
(configurado a `sim/output/`).

## Leer la salida con Python

```python
import corsika_panama as cp
import numpy as np

with cp.reader("sim/output/DAT001001") as f:
    for event in f:
        p = event.particles
        # IDs de muones: 5 = µ+, 6 = µ-
        muons = p[np.isin(p.particle_id, [5, 6])]
        print(f"Event {event.header.event_number}: {len(muons)} muons")
        # Columnas disponibles: x, y, px, py, pz, t, particle_id, weight
```

## Notas importantes

- Los archivos `sim/output/*.DAT` y `sim/output/*.lst` NO deben versionarse en git
  (pueden pesar decenas de GB). Están excluidos vía `.gitignore`.
- Los steering files SÍ se versionan — documentan exactamente qué se simuló.
- Cambiar `SEED` y `RUNNR` en cada corrida paralela independiente para evitar
  correlaciones estadísticas entre runs.
- Documentar cada corrida de producción en un registro (ver `docs/registro_corridas.md`
  cuando se cree).
