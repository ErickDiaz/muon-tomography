# Colaboración con INSIVUMEH — sitios candidatos para muografía

Documento que captura el hallazgo del 2026-05-26: la red de estaciones meteorológicas
automáticas de INSIVUMEH ya cubre los 4 volcanes objetivo del proyecto, y la estación
`Fg16` está a 3.73 km del cráter del Fuego — esencialmente la misma geometría que ya
está simulada en el paper actual.

Este documento es la fuente de verdad para el pivote estratégico del Paper 1:
**"validación de visibilidad de la sombra muónica desde la red INSIVUMEH"** en vez
del genérico "estudio de feasibility de muografía en Guatemala".

## Origen del dataset

INSIVUMEH publica el mapa interactivo en
[insivumeh.gob.gt/mapa-de-estaciones-automaticas-en-colaboracion-con-sesores-remotos/](https://insivumeh.gob.gt/mapa-de-estaciones-automaticas-en-colaboracion-con-sesores-remotos/).
El mapa embebe un iframe con un archivo HTML generado por Folium (Python + Leaflet);
no hay API REST pública. Los markers de las estaciones tienen sus coordenadas
inline en JavaScript y los popups con nombre + fuente en base64.

El script `scripts/fetch_insivumeh_stations.py` automatiza la extracción:

```bash
python3 scripts/fetch_insivumeh_stations.py
```

Output: `data/insivumeh_stations.csv` con 212 estaciones (snapshot 2026-05-26).
Re-ejecutar mensualmente para mantener actualizado.

## Operadores en la red

| Operador | Estaciones | Hardware típico | Notas |
|---|---|---|---|
| **Davis** | mayoría | Davis Vantage Pro2 | red distribuida INSIVUMEH/comunitaria |
| **ICC** | ~30 | mixto | Instituto Privado de Investigaciones sobre el Cambio Climático; concentradas en la franja cañera al sur de la cadena volcánica |
| **Sutron** | ~20 | Sutron telemetric | estaciones hidrológicas más grandes |

## Estaciones a ≤15 km de cada volcán

Calculado vía Haversine con coords del cráter de cada volcán.

### Fuego (14.473°N, 90.880°W) — 8 estaciones

| dist [km] | nombre | fuente | coords |
|---:|---|---|---|
| **3.73** | **`Fg16`** | **Davis** | (14.4550, -90.8508) |
| 5.03 | `Fg17 Insivumeh Finca Asuncion` | Davis | (14.4439, -90.9158) |
| 7.52 | `Fg8` | Davis | (14.4324, -90.9359) |
| 7.89 | `Fg 12 Insivumeh` | Davis | (14.4333, -90.8192) |
| 8.85 | `Yepocapa (Fca-Catie)` | ICC | (14.4831, -90.9615) |
| 10.55 | `San Miguel Dueñas` | Davis | (14.5239, -90.7973) |
| 11.48 | `El Platanar` | ICC | (14.5597, -90.9379) |
| 13.99 | `Ciudad Vieja` | Davis | (14.5248, -90.7615) |

Las estaciones `Fg##` (Fg8, Fg12, Fg16, Fg17) son la subred dedicada de INSIVUMEH para
monitoreo del Fuego. Acceso logístico ya resuelto, infraestructura desplegada, datos
publicados en tiempo real en el portal de INSIVUMEH. Candidatas naturales para hospedar
un futuro detector de muones.

### Acatenango (14.501°N, 90.876°W) — 9 estaciones

`Fg16` también es la más cercana acá (5.79 km), por la geometría del complejo volcánico
Acatenango–Fuego. Las demás superan los 8 km.

### Pacaya (14.380°N, 90.601°W) — 2 estaciones

Cobertura más débil: `Santa Teresa` (ICC, 10.80 km) y `San Miguel Petapa` (Davis, 14.16 km).
Para una eventual fase de deployment en Pacaya sería razonable proponer a INSIVUMEH una
estación adicional más cercana, como contraparte de la colaboración.

### Volcán de Agua (14.466°N, 90.743°W) — 6 estaciones

`Saob` (Davis, 5.94 km) es la más cercana. Buena cobertura para el cono.

## Hallazgo clave: `Fg16`

**Coords**: (14.4550, -90.8508), Davis, **3.73 km SE del cráter del Fuego**.

**Geometría relativa al cráter:**

| Magnitud | Valor |
|---|---|
| Distancia horizontal | 3.73 km |
| Desplazamiento N–S | $\Delta y \approx -2.0$ km (al sur del cráter) |
| Desplazamiento E–O | $\Delta x \approx +3.07$ km (al este del cráter) |
| Azimut del cráter visto desde la estación | $\sim 303°$ (NW) |
| Ángulo de elevación de la cima | $\sim 29°$ (depende de la altitud exacta de `Fg16`, pendiente confirmar con DEM) |

**Por qué importa:**

El paper actual (sección Results 3.2/3.3) usa un detector virtual a 3 km al este del
cráter, mirando con azimut $\phi \in [120°, 240°]$ (campo de visión centrado en
$\phi = 180°$ = oeste). Eso corresponde a una geometría *similar pero no idéntica* a
la real de `Fg16`. Las diferencias:

1. `Fg16` está al SE, no al E puro → la cima queda al NW ($\phi \sim 303°$),
   no al W ($\phi = 270°$). El campo de visión del muograma rota ~33°.
2. La distancia es 3.73 km vs 3.00 km → la opacidad máxima a través del edificio
   aumenta marginalmente (el rayo cruza un poquito más de roca, ~24% más de espesor
   geométrico en la dirección de máxima opacidad).
3. La altitud del terreno en `Fg16` (a confirmar con DEM Copernicus GLO-30) será
   menor que los 2,500 m del observable actual, lo cual afecta el flujo absoluto pero
   no la *forma* del muograma (ver discusión abajo).

**Implicación para el paper:** el muograma del paper es esencialmente válido para
`Fg16` modulo una rotación del campo de visión y un ajuste menor de altitud. El
trabajo inmediato es **re-correr el ray-tracing en `notebook 05` con las coords
exactas de `Fg16`** y confirmar que la firma topográfica (residuo $\Delta L$ con
Acatenango contaminando al norte, etc.) se mantiene cualitativamente.

## ¿Necesitamos re-correr CORSIKA por cada estación?

**Respuesta corta: no, en general.** Una sola corrida CORSIKA por altitud de observación
sirve para todas las estaciones a esa altitud. Lo que sí cambia por estación es el
ray-tracing topográfico y el cómputo del muograma (todo analítico, en notebooks).

**Por qué.** CORSIKA simula cascadas atmosféricas: primarios cósmicos entran, se
desarrollan en lluvias, y la simulación corta cuando las partículas cruzan el plano
`OBSLEV`. El output es una *distribución estadística* de muones $\{(p, \theta, \phi, x, y)\}$
en ese plano. Esa distribución depende de:

- El espectro y composición de primarios (`PRMPAR`, `ESLOPE`, `ERANGE`)
- El modelo atmosférico (`ATMOD`, eventualmente `ATMFILE` con perfil ERA5 local)
- El campo geomagnético local (`MAGNET`)
- **La altitud del plano de observación (`OBSLEV`)**
- Los modelos hadrónicos y umbrales (`ECUTS`)

Pero **no depende** de la latitud/longitud específica del detector *dentro de una
región pequeña* (kilómetros). Las cascadas son estadísticamente isotrópicas en azimut
y la composición/espectro de primarios cambia con escala continental, no con kilómetros.

Lo que **sí** depende de la posición específica del detector:

| Componente | Depende de coords detector | Implementación |
|---|---|---|
| Cascadas CORSIKA (DAT) | No (compartido) | reusar la corrida existente |
| Opacidad direccional $L(\theta, \phi)$ | Sí | re-correr ray-tracing por estación |
| Energía mínima $E_{\min}(\theta, \phi)$ | Sí (vía $L$) | re-cálculo CSDA por estación |
| Transmisión $T(\theta, \phi)$ | Sí (vía $E_{\min}$) | re-integración Reyna por estación |
| Residuo $\Delta L$ vs cono | Sí | re-cálculo por estación |

Todo lo de la columna derecha es trabajo de `notebook 05` y `analysis/muograma.py`, no
de CORSIKA. **Una sola corrida CORSIKA por volcán (a `OBSLEV` apropiado) sirve para
todas sus estaciones cercanas.**

### Caveat de altitud

Cada estación está a una altitud distinta del terreno. La corrida actual del Fuego
usa `OBSLEV = 2,500 m`. Si `Fg16` está, digamos, a 1,500 m de altitud, dos opciones:

1. **(Rigoroso)** Correr una segunda corrida CORSIKA a `OBSLEV = 1,500 m` y usarla
   para `Fg16`. Más CPU, ~5 min en alcyon para 100k cascadas. Worth it si el paper
   reporta flujos absolutos.
2. **(Pragmático)** Reusar la corrida a 2,500 m. La *forma* del muograma
   (que es lo que valida el Paper 1) cambia <5% en este rango de altitudes porque
   el ratio $\Phi_{\text{obs}}/\Phi_{\text{libre}}$ es robusto frente a la
   normalización absoluta del flujo. El error sistemático dominante sigue siendo la
   asunción de densidad uniforme de roca.

Para Paper 1, **opción 2 alcanza**. Para Paper 2 (que depende de ML sobre flujos
absolutos para super-resolución temporal), podríamos revisitar.

Lo que sí podemos hacer (low effort) es **cubrir el rango de altitudes con
2–3 corridas**:

| `OBSLEV` | Cubre estaciones a | Costo extra |
|---|---|---|
| 1,500 m | apron volcánico (Fg16, Fg17, Saob, Cengicaña, ...) | 1 corrida nueva |
| 2,500 m | media altura (ya está, RUNNR=1 en alcyon) | 0 |
| 3,500 m | flancos altos (si las hay) | 1 corrida nueva |

Y para estaciones intermedias, interpolar. Esto se decide cuando confirmemos las
altitudes reales de cada estación (próximo paso: cruzar las coords contra el DEM).

## Próximos pasos

1. **Re-correr `notebook 05` con coords de `Fg16`** (en vez del detector virtual a
   3 km E) y confirmar que el muograma residual del Fuego se ve consistente. Si
   pasa: el paper queda fortalecido con una geometría realista.
2. **Extraer altitud del terreno por estación** del DEM Copernicus GLO-30 (ya
   tenemos el tile localmente). Agregar columna `elev_m` al CSV.
3. **Generar muograma desde 4 estaciones del Fuego** (Fg16, Fg17, Fg8, Fg12) en un
   panel comparativo. Resultado visual fuerte para Section 3.4 del Paper 1.
4. **Si las estaciones varían >1 km en altitud**, correr una segunda corrida CORSIKA
   a `OBSLEV` adicional (estimar primero el rango).
