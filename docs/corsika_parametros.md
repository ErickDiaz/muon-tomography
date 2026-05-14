# Parámetros CORSIKA para Volcanes Guatemaltecos

Documentación técnica de cada parámetro del steering file con justificación física.
Aplica a CORSIKA 7.8050 compilado con QGSJET-II-04 + GHEISHA-2002 + geometría CURVED.

---

## Convenciones y Unidades

| Cantidad | Unidad en CORSIKA | Nota |
|----------|-------------------|------|
| Energía primaria | GeV | 1 GeV = 10⁹ eV |
| Altitud de observación | cm sobre nivel del mar | 1 m = 100 cm |
| Campo geomagnético | µT (microtesla) | 1 µT = 10 nT |
| Ángulos | grados decimales | |
| Profundidad atmosférica | g/cm² | |

---

## Parámetros Geofísicos por Volcán

### Campo Geomagnético (MAGNET Bx Bz)

CORSIKA define el campo con dos componentes:
- **Bx**: componente horizontal apuntando al norte geográfico (positivo hacia el norte), en µT
- **Bz**: componente vertical apuntando **hacia abajo** (positivo hacia el suelo), en µT

En el hemisferio norte (Guatemala, ~14°N), el campo magnético apunta hacia arriba y hacia
el norte → Bx positivo, Bz positivo.

> **Verificación obligatoria:** estos valores son aproximados para época 2025.
> Calcular valores exactos en: https://www.ngdc.noaa.gov/geomag/calculators/magcalc.shtml
> Seleccionar modelo IGRF-13, introducir coordenadas y altitud de cada volcán.

| Volcán | Lat | Lon | Alt (m) | Bx (µT) | Bz (µT) | Declinación | Inclinación |
|--------|-----|-----|---------|---------|---------|-------------|-------------|
| Fuego | 14.47°N | 90.88°W | 3763 | ~28.6 | ~30.5 | ~-2.8° | ~46.5° |
| Acatenango | 14.50°N | 90.88°W | 3976 | ~28.6 | ~30.4 | ~-2.8° | ~46.5° |
| Pacaya | 14.38°N | 90.60°W | 2552 | ~28.4 | ~30.2 | ~-2.7° | ~46.3° |
| Volcán de Agua | 14.46°N | 90.74°W | 3760 | ~28.5 | ~30.4 | ~-2.8° | ~46.4° |

**Nota:** Los cuatro volcanes están dentro de un radio de ~60 km, por lo que el campo
geomagnético es prácticamente idéntico. La corrección geomagnética afecta principalmente
muones de baja energía (<10 GeV) y posiblemente es despreciable a esta latitud (como ocurrió
en Colombia, donde la corrección resultó menor al 2%). Esto debe verificarse cuantitativamente.

### Altitud de Observación (OBSLEV)

El telescopio no se coloca en la cima del volcán sino en un punto adyacente con línea de
visión al edificio volcánico. Para el estudio de selección de sitio se prueban múltiples
puntos de observación candidatos. Las altitudes listadas son para la corrida de cielo abierto
(open sky); la topografía volcánica se incorpora en el ray-tracing posterior.

| Volcán | Punto candidato | Alt. estimada (m) | OBSLEV (cm) |
|--------|----------------|-------------------|-------------|
| Fuego | Flanco N de Acatenango | ~2500 | 250000 |
| Fuego | Cresta La Reunión (SE) | ~1800 | 180000 |
| Fuego | Finca Monte Obscuro (N) | ~2000 | 200000 |
| Acatenango | Valle SW (calibración) | ~2000 | 200000 |
| Pacaya | Cerro Chiquito (N) | ~1500 | 150000 |
| Volcán de Agua | San Juan del Obispo (N) | ~1700 | 170000 |

---

## Parámetros Físicos del Steering File

### PRMPAR — Tipo de partícula primaria

```
PRMPAR  14
```

| Código | Partícula | Abundancia en RC | Uso |
|--------|-----------|-----------------|-----|
| 1 | Protón (p) | ~90% | Primera aproximación |
| 402 | Helio (α) | ~8% | Estudio completo |
| 1407 | Nitrógeno (N) | ~1% | Estudio completo |
| 5626 | Hierro (Fe) | ~1% | Estudio completo |
| 14 | Nitrógeno (código alternativo) | — | Ver manual |

**Justificación:** Para el estudio de factibilidad inicial usar protones (PRMPAR 1).
El flujo de muones a nivel del suelo tiene una dependencia débil con la composición
del primario para energías > 100 GeV. Un estudio de sistemáticas posterior puede
comparar la composición mixta con el flujo de protón solo.

### ESLOPE — Índice espectral diferencial

```
ESLOPE  -2.7
```

El flujo diferencial de rayos cósmicos sigue una ley de potencia:

```
dN/dE ∝ E^γ,   γ = ESLOPE
```

El valor -2.7 es la medición del índice espectral entre 10 GeV y el knee (~3×10⁶ GeV).
Es el valor estándar en simulaciones de muografía volcánica.

**Referencia:** Gaisser & Honda, Ann. Rev. Nucl. Part. Sci. 52, 153 (2002).

### ERANGE — Rango de energía primaria

```
ERANGE  1.E1  1.E5
```

- **Límite inferior (10 GeV):** Los muones producidos por primarios de 10 GeV tienen
  energías de ~1-5 GeV. Un muón necesita al menos ~2 GeV para atravesar 300 m de roca
  estándar (680 g/cm²). Bajar a 1 GeV solo agrega muones que se detienen antes del detector.

- **Límite superior (100 TeV = 10⁵ GeV):** El flujo cae como E^(-2.7). Para estadística
  razonable (N > 100 showers/bin) en 10⁶ corridas, 100 TeV captura el rango útil.

**Para muografía concreta:** Los muones que pueden atravesar el Volcán de Fuego (~700 m
de roca basáltica, ρ ≈ 2.8 g/cm³ → opacidad ~1960 g/cm²) necesitan energía mínima:

```
E_min ≈ a × ρ(L) / (1 - b × ρ(L)) ≈ 200-400 GeV
```

Estos muones son producidos por primarios de > 1 TeV. El rango 10-100 TeV de primarios
es el más relevante para la muografía de este volcán.

### THETAP — Rango de ángulo cenital

```
THETAP  0.  89.
```

- **0°**: vertical (cénit) — establece la normalización del flujo de referencia.
- **89°**: casi horizontal — los muones de muografía llegan a ángulos cenitales de ~75°-85°
  dependiendo de la geometría volcán-detector.

**Por qué simular todos los ángulos:** La corrida de CORSIKA genera el flujo de cielo
abierto completo. El filtrado de cuáles direcciones atraviesan el volcán se hace
posteriormente en el ray-tracing con el DEM. Si solo se simulan ángulos grandes,
se pierde la normalización necesaria para calcular la opacidad relativa.

**Nota técnica:** Con geometría CURVED (necesaria para θ > 70°), CORSIKA calcula
correctamente la curvatura de la trayectoria del shower en la atmósfera.

### PHIP — Rango de ángulo azimutal

```
PHIP  0.  360.
```

Simula todas las direcciones azimutales. Alternativa para estudiar un flanco específico:

```
PHIP  270.  360.   ! Solo cuadrante Norte (para telescopio apuntando al norte del volcán)
```

Para la corrida de selección de sitio usar 0-360° y filtrar en análisis.

### ECUTS — Energías de corte (tracking threshold)

```
ECUTS  0.3  0.01  0.003  0.003
```

| Posición | Partícula | Valor | Justificación |
|----------|-----------|-------|---------------|
| 1 | Hadrones (p, n, π, K) | 0.3 GeV | Umbral mínimo útil para producción de muones |
| 2 | Muones (µ⁺, µ⁻) | 0.01 GeV | 10 MeV captura muones de baja E relevantes en altitud |
| 3 | Electrones/positrones | 0.003 GeV | Estándar EGS4 |
| 4 | Fotones | 0.003 GeV | Estándar EGS4 |

**Por qué 10 MeV para muones:** A altitudes > 2500 msnm la profundidad atmosférica
es menor (~750 g/cm² vs. ~1033 g/cm² al nivel del mar). Esto favorece el decaimiento
de mesones sobre su interacción, produciendo más muones de baja energía que al nivel del mar.
Bajar el umbral a 10 MeV (vs. el estándar de 300 MeV) aumenta el tiempo de cómputo
~15-20% pero captura estas contribuciones correctamente.

### MUADDI — Información adicional de muones

```
MUADDI  T
```

Activa el registro de información adicional para cada muón en la salida:
- Tiempo de llegada relativo al shower
- Dirección de llegada con mayor precisión
- Energía en el punto de producción

**Imprescindible para muografía:** sin esta bandera no es posible reconstruir la
trayectoria del muón con la precisión necesaria para el ray-tracing.

### MUMULT — Interacciones múltiples de muones

```
MUMULT  T
```

Activa el transporte preciso de muones incluyendo straggling en la pérdida de energía.
Importante para muones que atraviesan grandes espesores de roca (> 500 m w.e.).

### LONGI — Perfil longitudinal del shower

```
LONGI  T  20.  T  T
```

| Campo | Valor | Significado |
|-------|-------|-------------|
| 1 | T | Activar perfil longitudinal |
| 2 | 20. | Paso de profundidad: 20 g/cm² |
| 3 | T | Escribir perfil en archivo .lst |
| 4 | T | Incluir perfil de energía |

Útil para diagnóstico y validación del shower. Puede desactivarse (F) en corridas
de producción masiva para reducir tamaño del .lst.

### ATMOD — Modelo atmosférico

```
ATMOD  1
```

Modelos predefinidos en CORSIKA 7:

| Código | Modelo | Aplica a |
|--------|--------|----------|
| 1 | US Standard Atmosphere (1976) | Referencia universal |
| 2 | AT115 midlatitude summer | Latitudes medias |
| 3 | AT115 midlatitude winter | Latitudes medias |
| 4 | AT115 polar summer | Polar |
| 5 | AT115 polar winter | Polar |
| 6 | US Standard Atmosphere | Similar al 1 |

**Para este proyecto:**
- Corridas de prueba y selección inicial: `ATMOD 1` (estándar)
- Corridas de producción: usar `ATMFILE` con perfil ERA5 específico de Guatemala

```
ATMFILE  'atm_guatemala_enero.dat'   ! Perfil ERA5 convertido con gdastool
```

Los perfiles ERA5 se obtienen por mes para capturar la variación estacional
(época seca dic-abril vs. lluviosa mayo-nov en Guatemala).

### PAROUT — Control de salida de partículas

```
PAROUT  T  F
```

- Primera T: activar salida de partículas al nivel de observación (archivo DAT)
- Segunda F: no escribir archivo de partículas en otros niveles intermedios

### MAXPRT — Eventos impresos en el log

```
MAXPRT  1
```

Solo imprime detalle completo del primer shower en el .lst. Para corridas de producción
mantener en 0 o 1 para no inflar el log.

---

## Modelos Hadrónicos Seleccionados

### QGSJET-II-04 (alta energía, E > 80 GeV)

- Modelo quark-gluon string, versión II-04 (calibrado con datos LHC)
- Mejor descripción del espectro de muones en la región 100 GeV – 10 TeV
- El más usado en estudios de muografía volcánica (mismo que el paper colombiano)
- Compilado con coconut: selección `QGSJETII`

### GHEISHA-2002 (baja energía, E < 80 GeV)

- Modelo de interacciones hadrónicas de baja energía
- Incluido por defecto en CORSIKA, bien validado
- Complementa QGSJET-II-04 en el régimen de baja energía

**Nota sobre FLUKA:** FLUKA ofrece mayor precisión que GHEISHA a baja energía,
especialmente importante a alta altitud donde el umbral es relevante. Sin embargo,
requiere licencia separada y mayor complejidad de compilación. Considerar para el
análisis de incertidumbre sistemática en Fase 2.

---

## Geometría CURVED vs. FLAT

```
./coconut → seleccionar: CURVED geometry
```

| Geometría | Válida para | Nota |
|-----------|------------|------|
| FLAT | θ < 70° | Approximación de atmósfera plana |
| CURVED | θ hasta 89° | Necesaria para muografía (θ~75-85°) |

La muografía volcánica requiere ángulos cenitales grandes (muones casi horizontales
que atraviesan el edificio volcánico). CURVED es obligatorio.

---

## Estimación de Tiempo de Cómputo

Factores que más afectan el tiempo de cómputo:
1. Energía máxima del primario (dominante)
2. ECUTS bajos para muones
3. LONGI activado (+5%)
4. Geometría CURVED (+2%)

Estimaciones en CPU único moderno (Intel i7-12th gen, ~2024):

| NSHOW | ERANGE (GeV) | Tiempo estimado | Tamaño DAT |
|-------|-------------|-----------------|------------|
| 100 | 10–10⁵ | ~8 min | ~50 MB |
| 1,000 | 10–10⁵ | ~1.5 horas | ~500 MB |
| 10,000 | 10–10⁵ | ~15 horas | ~5 GB |
| 100,000 | 10–10⁵ | ~6 días | ~50 GB |

Para el dataset de entrenamiento del modelo ML (Opción A: surrogate model),
se necesitan ~50,000–100,000 corridas cortas (NSHOW=100–500) variando los parámetros
de entrada → esto requiere cluster o paralelización con los scripts MPI de CORSIKA.

---

## Flags del Compilador Importantes (coconut)

Al correr `./coconut`, verificar que estén activados:

| Flag | Descripción | Estado |
|------|-------------|--------|
| QGSJETII | Modelo hadrónico alta energía | Requerido |
| GHEISHA | Modelo hadrónico baja energía | Requerido |
| CURVED | Geometría de atmósfera curva | Requerido |
| MUON | Módulo de transporte de muones | Requerido |
| STACKIN | Permite inyectar partículas a media atmósfera | Opcional |
| THIN | Thinning para E > 10¹⁵ eV | No necesario (nuestra E es menor) |
| CONEX | Híbrido CORSIKA-CONEX | Opcional para producción rápida |

---

## Validación de la Instalación

Antes de correr las simulaciones de Guatemala, validar con el ejemplo incluido:

```bash
cd corsika-78050/run/
./corsika78050Linux_QGSII_gheisha < all-inputs > validation.lst 2>&1

# Verificar que el .lst termine con la línea:
grep "END OF RUN" validation.lst
# Debe aparecer: " END OF RUN   EVENT:  10   ..."
```

Verificar también que el archivo DAT se haya generado:
```bash
ls -lh DAT000001
# Tamaño esperado para 10 showers: ~5-10 MB
```
