# Modelos físicos de la simulación

Documento de referencia para entender **por qué** cada parámetro del steering CORSIKA está donde está. Cada decisión balancea precisión física, costo computacional, y compatibilidad con la literatura de muografía volcánica.

Para ver los parámetros concretos del run cargado, ver la sección "Parámetros físicos de la simulación" del notebook `02_inspect_muons.ipynb`.

---

## 1. CORSIKA 7.8050 — el código de simulación

[CORSIKA](https://www.iap.kit.edu/corsika/) es el estándar para cascadas atmosféricas de rayos cósmicos: ~40 años de desarrollo en KIT, validado contra todos los experimentos modernos (Auger, IceCube, KASCADE-Grande). La versión 7.8050 es la última de la rama estable; CORSIKA 8 es una reescritura en C++ pero aún en maduración.

**Por qué no GEANT4**: GEANT4 es excelente para detectores pero ineficiente para cascadas atmosféricas extendidas (60+ km de propagación). CORSIKA tiene optimizaciones específicas (thinning, NKG, transporte muónico aproximado) que lo hacen 100–1000× más rápido para EAS.

---

## 2. Modelos hadrónicos

CORSIKA invoca dos modelos hadrónicos distintos según la energía:

### Alta energía (E > 80 GeV): **DPMJET-III**

DPMJET-III ([Roesler, Engel, Ranft 2001](https://arxiv.org/abs/hep-ph/0012252); revisado por Fedynitch 2015) implementa el **Dual Parton Model** con extensiones para colisiones de iones pesados.

**Por qué este y no otro:**
- Es el modelo **default** de la imagen Docker (build-arg `HE_MODEL=1` en `docker/coconut.expect`).
- Está calibrado con los datos LHC más recientes (cross sections inelásticas, multiplicidad de hadrones secundarios).
- Para muografía volcánica el flujo de muones depende sobre todo de la producción de piones y kaones en interacciones en aire — DPMJET-III, EPOS-LHC y SIBYLL 2.3e dan acuerdos ~10% entre sí en esa observable.
- Alternativas disponibles (cambiar `HE_MODEL` en `.env`):
  - `2 = EPOS-LHC` (Pierog et al. 2015): considerado más preciso para multiplicidad de muones en EAS muy energéticos, pero ~2× más lento. Recomendable para ablation cuando importe robustez de baja energía.
  - `3 = QGSJET-II-04` (Ostapchenko 2011): popular en Auger y IceCube. Acuerdo similar.
  - `4 = SIBYLL 2.3e` (Riehn et al. 2020): el más rápido, validado para muones de alta energía.

**Cuándo cambiar**: si querés cuantificar incerteza sistemática del modelo en el muograma final → correr 4 sets idénticos cambiando `HE_MODEL` y comparar la dispersión.

### Baja energía (E < 80 GeV): **URQMD 1.3cr**

[URQMD](https://urqmd.org/) (Ultra-relativistic Quantum Molecular Dynamics, Bass et al. 1998) es un modelo microscópico de transporte que sigue cada nucleón individualmente.

**Por qué este**:
- Es el LE model más físicamente motivado disponible en CORSIKA.
- A bajas energías la mayor parte de los hadrones secundarios provienen de cascadas ya desarrolladas — la producción y propagación detallada en este régimen afecta directamente el espectro de muones blandos que llegan al suelo.
- Alternativa: **GHEISHA** (más antiguo, parametrización empírica). URQMD es preferido en la literatura moderna.

### Transición 80 GeV

La energía de transición HE↔LE se elige en CORSIKA de modo que ambos modelos den predicciones consistentes. 80 GeV es el default robusto; cambiarla requiere validación cuidadosa.

---

## 3. Cascada electromagnética: **EGS4**

EGS4 (Electron Gamma Shower, Nelson et al. 1985) simula la propagación de electrones, positrones y fotones acoplados. Versión moderna: EGS5, pero CORSIKA mantiene EGS4 por estabilidad probada.

**Por qué EGS y no NKG**: la opción NKG (Nishimura-Kamata-Greisen) es una **parametrización analítica** que es ~10× más rápida pero pierde el detalle por evento. Para muografía no necesitamos la cascada EM con detalle de partícula individual — los muones son hijos directos de piones/kaones, no de la componente EM — pero usar EGS4 nos permite el cross-check del perfil longitudinal y la razón μ/e al suelo.

---

## 4. Modo de trazado: **CURVED + MUPROD**

### `CURVED` (compilación)

CORSIKA por defecto asume **atmósfera plana** (slab geometry). A ángulos cenitales pequeños esto es buena aproximación, pero **a θ > 70°** la longitud real del recorrido se desvía de la aproximación plana por más de 1% por la curvatura de la Tierra.

Para muografía volcánica los muones más relevantes son los **casi-horizontales** (θ > 70° o incluso > 80°). Sin `CURVED` los muones de θ = 85° tendrían profundidad atmosférica predicha por la fórmula plana ($X = X_v \sec\theta$) que diverge a θ → 90° — no físico.

**Build-arg en la imagen Docker**: `BUILD_CURVED=true`.

### `MUPROD` (compilación)

Activa el seguimiento detallado de la producción muónica: cada muon registra su **profundidad de origen** y la **partícula padre** que lo generó (π⁺, π⁻, K⁺, K⁻, μ⁺/⁻ from decay chain). Esta info es esencial para validar el balance de la cascada y para diagnosticar si el flujo muónico está dominado por piones vs kaones.

---

## 5. Atmósfera: **ATMOD 1 (US Standard, Linsley)**

CORSIKA implementa varios modelos atmosféricos pre-tabulados:
- `1 = US Standard` (parametrización de Linsley, ~1962, válida globalmente)
- `2..9 = atmósferas estacionales en Karlsruhe`
- `0 = ATMFILE` (perfil custom, p.ej. ERA5 reanálisis)

**Por qué ATMOD 1**:
- Es la atmósfera estándar usada en TODA la literatura comparable de muografía (Vesga-Ramírez 2019, Lesparre 2010, Procureur 2017). Hace el resultado directamente comparable.
- Guatemala (latitud 14.5°N) está cerca del trópico donde la atmósfera real difiere modestamente del US Standard en el perfil de altura, pero la **profundidad total** (g/cm²) es similar y eso es lo que CORSIKA usa.
- **Diferimos** el uso de ERA5 (`ATMFILE`) hasta tener motivo: el efecto estacional sobre la tasa de muones a nivel del suelo es ~1–2%, irrelevante frente a las incertezas de modelos hadrónicos (~10%).

---

## 6. Campo geomagnético: **MAGNET (componentes horizontal y vertical)**

`MAGNET 28.6 30.5` da (B_horizontal, B_vertical) en µT. Valores específicos del Fuego (14.47°N, 90.88°W) según IGRF-13 ~ 2025.

**Por qué importa**:
- Las partículas cargadas se desvían en el campo (radio de Larmor). A bajas energías (E < 1 GeV) los electrones y muones blandos pueden curvar varios grados.
- Genera **asimetría este-oeste** observable en el flujo: muones positivos llegan preferencialmente desde el oeste, negativos desde el este. Es un cross-check de que la simulación está coherente.
- Para muografía propiamente el efecto es pequeño (los muones útiles tienen E ≫ 1 GeV) pero la consistencia paga.

Los valores varían levemente entre los 4 volcanes (Acatenango, Pacaya, Agua) por estar a ~15–50 km de distancia. Cada `{volcan}_template.inp` tiene los valores apropiados.

---

## 7. Cortes de energía: **ECUTS 0.3 0.01 0.003 0.003**

Cuatro umbrales bajo los cuales se deja de propagar la partícula:
- **0.3 GeV** para hadrones (300 MeV)
- **0.01 GeV** para muones (10 MeV)
- **0.003 GeV** para electrones (3 MeV)
- **0.003 GeV** para fotones (3 MeV)

**Por qué estos valores**:
- El corte de **muones a 10 MeV** es agresivo: muones de esa energía apenas penetran un metro de agua/tierra. Para muografía esto es muy por debajo del umbral útil (~GeV para atravesar el edificio del Fuego), así que **no perdemos información** útil. Si subieras a 100 MeV podrías acelerar la simulación con costo cero para muografía.
- El corte de **e±/γ a 3 MeV** es estándar para EGS4. Subir esto ahorra mucho tiempo pero degrada el perfil longitudinal y el `μ/e` al suelo.
- El corte de **hadrones a 300 MeV** evita seguir partículas que tampoco van a producir muones significativos.

**Trade-off**: bajar los cortes (cortes "duros") da mejor precisión pero infla el tiempo de cómputo cuadráticamente. La elección actual está en la zona Pareto-óptima para este estudio.

---

## 8. Primario: **PRMPAR 14 (protón)**

Proton (CORSIKA ID = 14) es el ~85% del flujo de rayos cósmicos primarios a las energías relevantes. Los otros componentes:
- **Helio (~10%)**: idéntica fenomenología al protón pero spectrum corrido.
- **Núcleos más pesados (~3%)**: producen cascadas que se desarrollan más alto y son menos eficientes generando muones.

**Por qué solo protones por ahora**:
- Simplifica la validación inicial (un solo espectro).
- Para muografía las predicciones cambian <5% al pasar de "solo p" a "mezcla de Gaisser". Suficiente para validación física pero no para flujo absoluto.
- **Cuándo agregar mezcla**: cuando querramos flujo absoluto en lugar de solo shape. Procedimiento: 4–5 runs separados (p, He, CNO, MgSi, Fe), combinados con pesos del espectro all-particle ([Gaisser et al. 2013](https://arxiv.org/abs/1303.3565)).

---

## 9. Espectro y energía: **ESLOPE -2.7, ERANGE 10 GeV – 100 TeV**

### Pendiente espectral `-2.7`

El espectro diferencial de rayos cósmicos primarios sigue una ley de potencias $dN/dE \propto E^{-\gamma}$ con $\gamma \approx 2.7$ por debajo del *knee* (E ~ 3 PeV). Esta es la pendiente medida por todos los experimentos (BESS, AMS-02, PAMELA, ATIC, CREAM).

### Rango 10 GeV – 100 TeV

- **Cota inferior 10 GeV**: por debajo de eso el primario produce pocos o ningún muon que sobreviva al OBSLEV. Bajar a 1 GeV multiplica el tiempo de cómputo sin agregar muones útiles.
- **Cota superior 100 TeV**: cubre todos los muones que esperamos detectar. Primarios de >100 TeV son extremadamente raros (espectro cae como $E^{-2.7}$) y la estadística asintótica no aporta a la muografía de un edificio pequeño.

---

## 10. Geometría angular: **THETAP 0–89°, PHIP 0–360°**

- **Cenital 0–89°**: cobertura prácticamente completa. Excluye solo θ = 90° (horizontal estricto, no físico) y θ > 89° (rebote en superficie).
- **Azimut 0–360°**: isotrópico. El corte al cono del volcán se hace en post-procesamiento (notebook 04/05), no en la simulación.

**Por qué simular todo el hemisferio**: una vez simulado, los muones se pueden cortar a cualquier ventana angular en análisis. Una simulación que solo cubre el cono del volcán es no-reusable y obliga a re-simular cada vez que cambia la posición del detector.

---

## 11. Output: **MUADDI T, MUMULT T, LONGI F**

- **`MUADDI T`**: guarda el origen de cada muon (profundidad, padre). Crítico para validar la cascada.
- **`MUMULT T`**: scattering múltiple de Molière para muones, refleja la dispersión real del muon al atravesar la atmósfera.
- **`LONGI F` en producción**: el perfil longitudinal infla el log (~3× tamaño del .lst) y no se usa en muografía. Solo se activa en runs de validación (`fuego_test.inp` lo tiene en `T`).

---

## 12. Nivel de observación: **OBSLEV (cm)**

Altitud donde CORSIKA "detiene" la cascada y registra las partículas que cruzan el plano horizontal a esa cota.

| Volcán | OBSLEV (cm) | Altitud | Punto físico |
|---|---|---|---|
| Fuego | 250000 | 2.5 km | Flanco N de Acatenango |
| Acatenango | 200000 | 2.0 km | Valle SW |
| Pacaya | 150000 | 1.5 km | Cerro Chiquito N |
| Agua | 170000 | 1.7 km | San Juan del Obispo / Santa María de Jesús |

**Por qué importa**:
- El flujo de muones cambia con la profundidad atmosférica. A nivel del mar (~1030 g/cm²) hay menos muones que a 2.5 km (~764 g/cm²) — los blandos sobreviven mejor.
- Cada posición candidata de detector tiene una altitud distinta. Las simulaciones se hacen para esa altitud específica.

---

## 13. Decisiones explícitamente diferidas

Documentadas para que se sepa qué falta antes de "flujo absoluto":

- **Normalización absoluta**: para tener muones/(m²·s·sr) hace falta multiplicar por flujo asumido del primario × área de muestreo × tiempo. Hoy solo comparamos *forma*.
- **Mezcla de primarios**: ver §8. Necesario para flujo absoluto.
- **Atmósfera ERA5**: ver §5. Efecto <2%, lo dejamos para refinamiento futuro.
- **Corrección geomagnética estricta**: el `MAGNET` aproximado ya está; refinar a IGRF-14 cuando esté disponible (lanzamiento ~2025-2027).

---

## Referencias clave

- **CORSIKA manual**: [FZKA 6019, KIT 2025](https://web.iap.kit.edu/corsika/usersguide/usersguide.pdf)
- **DPMJET-III**: Roesler, Engel, Ranft, arXiv:[hep-ph/0012252](https://arxiv.org/abs/hep-ph/0012252)
- **URQMD**: Bass et al., Prog. Part. Nucl. Phys. 41:255 (1998)
- **EGS4**: Nelson, Hirayama, Rogers, SLAC-265 (1985)
- **Gaisser cosmic ray spectrum**: Gaisser et al., Frontiers of Physics 8(6) (2013), arXiv:[1303.3565](https://arxiv.org/abs/1303.3565)
- **Muografía volcánica metodológica**: Vesga-Ramírez et al. 2019, arXiv:[1705.09884](https://arxiv.org/abs/1705.09884) (Cerro Machín, Colombia). Lesparre, Procureur, Frontiers Earth Sci 2020 (Puy de Dôme, Francia).
