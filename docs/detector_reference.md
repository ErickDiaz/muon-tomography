# Detector virtual de referencia — especificación y conceptos

Este documento explica **qué es el detector que aparece implícito en el paper**, qué
es el **área de detección**, qué significa **ángulo de observación**, y cómo se
relacionan esos números con lo que las simulaciones de muograma producen.

El detector no existe físicamente todavía. Es un modelo geométrico copiado del
diseño **MuTe** del paper colombiano [Vesga-Ramírez et al. 2019](https://arxiv.org/abs/1705.09884),
que sirve únicamente como referencia para estimar tiempos de exposición y para
dar al lector una visualización concreta de "con qué hardware se mediría esto".

---

## 1. Área de detección

> **Definición.** El área física del detector que intercepta los muones. Se mide
> en cm² o m². Para nuestro detector (hodoscopio de 2 paneles), el área de
> detección es la del **panel sensible**.

| Parámetro | Valor de referencia |
|---|---|
| Tipo de detector | Hodoscopio de 2 paneles centelladores + tanque Cherenkov (WCD) |
| Tamaño del panel | $L = 120 \times 120$ cm |
| **Área activa por panel** | $A = 1.44$ m² $= 1.44 \times 10^{4}$ cm² |
| Pixelación | 30 × 30 tiras → 900 píxeles independientes |
| Ancho de cada píxel | $\ell = L/30 = 4$ cm |

Un muón cuenta como detectado solo si **atraviesa ambos paneles** (cobra una traza
recta). El WCD agrega rechazo electromagnético — descarta partículas más blandas
que un muón GeV.

---

## 2. Ángulo de observación

La frase "ángulo de observación" mezcla dos conceptos distintos. Conviene
nombrarlos por separado.

### 2a. Campo de visión (Field of View, FoV)

> **Definición.** El ángulo sólido en el cielo que el detector es capaz de "ver".
> Determinado por la **geometría** de los dos paneles: tamaño y separación entre
> ellos.

Para un hodoscopio de dos paneles cuadrados coaxiales de lado $L$, separados una
distancia $D$, el rango de ángulos $\theta$ (medidos respecto al eje del detector)
para los cuales un muón puede atravesar ambos:

$$
\theta_{\max} = \arctan\left(\frac{L}{D}\right) \quad \text{(extremo geométrico)}
$$

y la región efectiva donde la aceptancia es alta:

$$
\theta_{\text{eff}} \approx \arctan\left(\frac{L}{2D}\right)
$$

Numéricamente, con $L = 120$ cm:

| Separación $D$ | $\theta_{\text{eff}}$ (semi-ángulo efectivo) | $\theta_{\max}$ (extremo) |
|---:|---:|---:|
| 100 cm | $\arctan(0.6) \approx 31°$ | $\arctan(1.2) \approx 50°$ |
| 150 cm | $\arctan(0.4) \approx 22°$ | $\arctan(0.8) \approx 39°$ |
| 250 cm | $\arctan(0.24) \approx 13°$ | $\arctan(0.48) \approx 26°$ |

**Trade-off práctico**: paneles más cercanos $\Rightarrow$ FoV más amplio pero
peor resolución angular; paneles más lejos $\Rightarrow$ FoV más estrecho pero
mejor resolución (puedes diferenciar más píxeles en la cara del volcán).

### 2b. Dirección de apuntamiento

> **Definición.** Hacia dónde mira el eje del telescopio (la línea perpendicular
> a los paneles, que une los centros). No es parte de la "geometría del
> detector" sino de la **instalación**.

Para muografía volcánica, el telescopio se **inclina** para apuntar al cráter,
no al cenit. Esto significa:

- El eje del detector forma un ángulo $\theta_0$ con la vertical igual al ángulo
  cenital del cráter desde la estación (típicamente $\theta_0 \in [60°, 75°]$).
- El azimut del eje apunta hacia el cráter.

**Para la estación `Fg16`** (sitio principal del paper, ver
[`insivumeh_collaboration.md`](insivumeh_collaboration.md)):

| Magnitud | Valor |
|---|---|
| Distancia horizontal al cráter | 3.73 km |
| Cráter visto a $\theta$ (cenital) | $\sim 60°$ – $65°$ *(depende de altitud exacta de Fg16, pendiente del DEM)* |
| Equivalente en elevación | $\sim 25°$ – $30°$ sobre el horizonte |
| Azimut del cráter (convención meteorológica, 0°=N, 90°=E) | $\sim 303°$ (al NW de Fg16) |
| Azimut en convención matemática (atan2, 0°=E, 90°=N) | $\sim 147°$ |

---

## 3. Aceptancia geométrica

> **Definición.** El producto $A \cdot \Omega$ (área × ángulo sólido), en cm²·sr.
> Es la cantidad que multiplica al flujo de muones para dar la **tasa de cuentas**.

Para nuestro detector de referencia:

$$\boxed{\langle A\Omega\rangle_{\max} \approx 6 \text{ cm}^2\cdot\text{sr}}$$

(en la dirección normal al panel; cae con $\cos\theta$ al alejarse del eje).

La tasa de cuentas en una dirección $(\theta, \phi)$ se calcula como:

$$
\frac{dN}{dt}(\theta, \phi) = \Phi_\mu^{\text{libre}}(\theta) \cdot \langle A\Omega\rangle(\theta) \cdot T(\theta, \phi)
$$

donde $\Phi_\mu^{\text{libre}}$ es el flujo de muones de cielo abierto (de la
parametrización de Reyna a la altitud del detector) y $T(\theta, \phi)$ es el
mapa de transmisión que producen los notebooks 04 y 05.

---

## 4. Resolución angular

> **Definición.** El tamaño angular del píxel más pequeño que el detector puede
> distinguir.

Cada par de píxeles opuestos (uno por panel) define una "línea de vista". El
tamaño angular de un píxel proyectado:

$$
\delta\theta \approx \frac{\ell}{D} = \frac{4 \text{ cm}}{D}
$$

| Separación $D$ | Resolución angular $\delta\theta$ |
|---:|---:|
| 100 cm | 40 mrad $\approx 2.3°$ |
| 150 cm | 27 mrad $\approx 1.5°$ |
| 250 cm | 16 mrad $\approx 0.9°$ |

El paper de referencia colombiano cita **15 – 20 mrad** como resolución típica
de operación, lo que implica que MuTe normalmente opera con $D$ cercano a
200 – 250 cm.

---

## 5. Relación con los muogramas del paper

Los mapas que generan los notebooks 04 y 05 cubren una ventana angular
deliberadamente **más amplia que el FoV físico del detector**:

| Cantidad | Notebook 05 (software) | Detector real (hardware) |
|---|---|---|
| Rango cenital $\theta$ | $[40°, 85°]$ (45° de ventana) | $\pm 13°$ a $\pm 31°$ alrededor del eje (según $D$) |
| Rango azimutal $\phi$ | $[\phi_{\text{summit}} \pm 60°]$ (120° de ventana) | Limitado por el FoV cónico |
| Paso angular | $0.5°$ | depende de $\delta\theta$ (16 – 40 mrad) |

**¿Por qué la ventana del software es mayor?** Para que cualquier elección
razonable de $D$ (y por tanto de FoV) caiga *dentro* del mapa que ya tenemos
calculado. Si el detector real tiene $\theta_{\text{eff}} = 22°$, miramos la
porción central de nuestro mapa que cae dentro de ese cono; el resto del mapa
es información extra, gratis, por si más adelante variamos el diseño.

---

## 6. Cómo contestar si te lo preguntan

> *"El detector virtual de referencia es un hodoscopio MuTe-like:
> dos paneles centelladores de **1.44 m²** (120 × 120 cm, pixelados en 30 × 30
> tiras), separados $D \in [100, 250]$ cm, con **resolución angular de
> ~15 mrad** y **aceptancia máxima de ~6 cm²·sr**. El detector se apunta al
> cráter del Fuego desde la estación INSIVUMEH **Fg16** (3.73 km SE del cráter),
> donde el cráter queda a una elevación de ~29° sobre el horizonte (azimut
> ~303°). El campo de visión físico del detector es un cono de semi-ángulo
> efectivo entre 13° y 31° según la separación entre paneles; los muogramas
> del paper cubren deliberadamente una ventana más amplia ($\theta \in [40°,
> 85°]$ × $\Delta\phi = 120°$) para que cualquier elección de $D$ caiga
> contenida."*

---

## Referencias

- Vesga-Ramírez et al. 2019, *Muon Tomography sites for Colombian volcanoes*, arXiv:1705.09884 — diseño MuTe y números de aceptancia/resolución que adoptamos como referencia.
- Sullivan 1971, *Geometric factor and directional response of single and multi-element particle telescopes*, Nucl. Instr. Meth. 95(1):5 — fórmula clásica del factor geométrico de telescopios cuadrados coaxiales.
- [`insivumeh_collaboration.md`](insivumeh_collaboration.md) — por qué `Fg16` es la estación principal del paper actual.
