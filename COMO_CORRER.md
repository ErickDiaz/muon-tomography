# Cómo correr la simulación completa — paso a paso

Pipeline end-to-end: desde un repo recién clonado hasta el notebook `02_inspect_muons.ipynb` mostrando muones de 50,000 cascadas.

El proyecto está pensado para que la **simulación corra en un servidor dedicado** (por el costo de tiempo: la corrida de producción son ~13 h) y que el **análisis se haga localmente** después de sincronizar los outputs. Pero también podés correr todo en local si tenés Docker y paciencia.

---

## Mapa rápido

```
[laptop] --rsync/scp--> [servidor] --Docker--> [CORSIKA] --rsync<-- [laptop] --> [notebook]
   |          |                |          |             |              |
   .env    deploy.sh      server-setup    Make      sim/output/      analysis/
```

| Fase | Dónde corre | Comando | Tiempo |
|---|---|---|---|
| 0. Setup local | laptop | `cp .env.example .env` + editar | 2 min |
| 1. Setup servidor | servidor (vía SSH) | `make server-setup` | 5 min |
| 2. Deploy | local → servidor | `make deploy` | 20 min |
| 3. Validar | servidor | `make server-verify` | 1 min |
| 4. Test | servidor | `make server-test` | ~8 min |
| 5. Producción | servidor (tmux) | `make server-prod` | ~13 h |
| 6. Sync | servidor → local | `make sync-output` | minutos |
| 7. Análisis | local | abrir `notebooks/02_inspect_muons.ipynb` | — |

Todos los comandos `make ...` se corren desde la raíz del repo en la **laptop** (el Makefile sabe cómo hablarle al servidor por SSH). Sólo hay que entrar manualmente al servidor para inspeccionar tmux o hacer debug.

---

## Fase 0 — Prerrequisitos locales

**Software:**
- Docker Engine ≥ 24.0 (`docker --version`)
- Make, rsync, ssh (vienen con cualquier Linux/macOS estándar)
- Python ≥ 3.10 con pandas / matplotlib / corsikaio (para el notebook)

**Archivos:**
- `corsika-78050.tar.gz` en la raíz del repo (descargado de [KIT](https://www.iap.kit.edu/corsika/), no se versiona)
- `.env` configurado:

```bash
cp .env.example .env
$EDITOR .env
```

Las variables clave son:

| Variable | Para qué | Ejemplo |
|---|---|---|
| `SERVER_HOST` | IP/hostname del servidor | `192.168.30.70` |
| `SERVER_USER` | usuario SSH | `jarjarbinks` |
| `SERVER_SSH_KEY` | llave privada | `~/.ssh/id_ed25519` |
| `SERVER_PROJECT_DIR` | dónde rsync copia el repo | `/home/jarjarbinks/thesis` |
| `HE_MODEL` | modelo hadrónico HE (1=DPMJET, 2=EPOS, 3=QGSJET, 4=SIBYLL) | `1` |
| `DEPLOY_STRATEGY` | `build` (default) / `load` / `pull` | `build` |

**Validación local rápida** (sin servidor) — opcional pero recomendado la primera vez:

```bash
make build-corsika     # construye thesis-corsika:latest (~20 min)
make verify-corsika    # corre el ejemplo all-inputs adentro del contenedor
make test-corsika      # corre fuego_test.inp en local (~8 min)
```

Si lo de arriba pasa, ya sabés que la imagen y los steering files están bien antes de subir nada al servidor.

---

## Fase 1 — Setup del servidor (una sola vez)

Servidor Debian/Ubuntu fresco. Instala paquetes base (rsync, tmux, git, curl) + Docker Engine + (opcional) NVIDIA toolkit:

```bash
make server-setup
```

Esto sube `scripts/server-setup.sh` al servidor y lo corre con `sudo`. Es **idempotente** — podés correrlo varias veces sin romper nada.

Si querés GPU (para la Fase 3 de ML, no para CORSIKA), poné `SERVER_HAS_GPU=true` en `.env` antes de correr este target.

**Validación:**

```bash
make ssh                           # entra al servidor
# adentro:
docker run hello-world             # confirma que Docker funciona sin sudo
exit
```

---

## Fase 2 — Deploy del proyecto

Sincroniza el repo + `corsika-78050.tar.gz` al servidor y construye la imagen Docker **allá** (estrategia `build`):

```bash
make deploy
```

Internamente esto hace:
1. `rsync` del repo a `${SERVER_PROJECT_DIR}` (excluyendo `sim/output/`, `.git`, etc.)
2. `scp` del tarball CORSIKA
3. SSH al servidor + `make build-corsika`

El primer build tarda **15–25 min**. Builds siguientes son segundos (capas cacheadas) salvo que cambies `HE_MODEL` o el Dockerfile.

**Estrategia alternativa** si no querés re-compilar en el servidor:

```bash
make deploy-load    # construye local, exporta a .tar, scp, docker load
```

Útil si el servidor es lento o sin internet, pero transfiere ~2.5 GB en lugar de ~100 MB del tarball.

---

## Fase 3 — Validación en el servidor

```bash
make server-verify
```

Corre el ejemplo `all-inputs` que viene con CORSIKA dentro del contenedor del servidor. Debe imprimir `END OF RUN`.

---

## Fase 4 — Corrida de prueba (500 showers)

```bash
make server-test
```

Esto ejecuta `fuego_test.inp` en el servidor (~8 min). Cuando termine, el servidor tendrá `sim/output/DAT001001`, `DAT001001.long`, y `fuego_test.lst`.

**Nota:** El test sí tiene `LONGI T` activado (genera el perfil longitudinal). La producción no — ver Fase 5.

---

## Fase 5 — Producción (50,000 showers, ~13 h)

```bash
make server-prod
```

Esto arranca la corrida **detached en una sesión tmux** del servidor, así podés cerrar la laptop y la simulación sigue corriendo.

**Monitorear sin entrar:**

```bash
make server-prod-status    # tail del log + estado de tmux
make server-logs           # tail -f del .lst en vivo
```

**Entrar a la sesión tmux** (para ver progreso en detalle, `Ctrl+B D` para detach sin matar):

```bash
make server-prod-attach
```

**Si algo sale mal:** entrar con `make ssh`, atacar la sesión (`tmux attach -t corsika-prod`), inspeccionar.

**¿Por qué `LONGI F` en producción?** Cada shower agrega ~150 líneas al `.long` (10 cols × 41 pasos). Con 50,000 showers serían ~7 millones de líneas — el archivo crece a varios GB y el parser tarda mucho. Para el perfil longitudinal el run de test (500 showers) ya es suficiente; los muones individuales sí los necesitamos en producción para la estadística angular.

---

## Fase 6 — Bajar los resultados

```bash
make sync-output
```

`rsync` del directorio `sim/output/` del servidor a la laptop. Lo que necesitamos para el análisis:

- `DAT001001` + `DAT001001.long` + `fuego_test.lst` (test)
- `DAT001101` + `fuego_prod.lst` (producción)

`DAT001101` pesa varios GB pero está en formato binario denso (no comprimible mucho). Considera espacio antes.

---

## Fase 7 — Análisis local

```bash
jupyter lab notebooks/02_inspect_muons.ipynb
```

El notebook está estructurado así:

| Sección | Qué muestra |
|---|---|
| 1 | Multiplicidad de muones por shower |
| 2 | Espectro de energía μ⁺ vs μ⁻ |
| 3 | Razón de cargas μ⁺/μ⁻ (esperado ≈ 1.27 a baja E) |
| 4 | Ángulo cenital θ |
| 5 | Azimut φ (debe ser uniforme) |
| 6 | Mapa 2D (θ, φ) — el cuadro relevante para apuntar al volcán |
| 7 | **Energía vs θ** — los muones laterales son los más energéticos |
| 8 | Posición de impacto (x, y) + LDF |
| 9 | **Perfil longitudinal** — cómo nace y muere la cascada (usa el `.long` del test) |

Por default carga la corrida de producción (`run_number=1101`); la sección 9 cambia internamente a `1001` porque sólo el test tiene `.long`.

**Tests rápidos del módulo de análisis:**

```bash
make test    # corre tests/ con pytest
```

23 tests sobre los parsers de `.lst`, `.long` y el binario DAT.

---

## Troubleshooting frecuente

| Síntoma | Probable causa | Fix |
|---|---|---|
| `ERROR: falta corsika-78050.tar.gz` | tarball no descargado | bajar de [KIT](https://www.iap.kit.edu/corsika/), poner en raíz |
| `ERROR: falta .env` | no copiaste de la plantilla | `cp .env.example .env` |
| `Permission denied (publickey)` en `make deploy` | llave SSH mal configurada | `ssh -i ${SERVER_SSH_KEY} ${SERVER_USER}@${SERVER_HOST}` para debug |
| Sesión `corsika-prod` ya existe | corrida anterior no terminó/no se limpió | `make server-prod-attach` → `Ctrl+C` o `make ssh` + `tmux kill-session -t corsika-prod` |
| `0 muones en el binario` en el notebook | `PRMPAR != 14` o run sin regenerar | revisar `sim/steering/*.inp`, re-correr |
| `.long` no encontrado | corrida de prod (que tiene `LONGI F`) | usar el run de test (1001) para la sección 9 |

---

## Reproducir en otra máquina (sin servidor remoto)

Si no tenés servidor y querés correrlo todo en la laptop, saltate las fases 1, 2, 5, 6. El equivalente local es:

```bash
make build-corsika      # construir imagen
make verify-corsika     # validar
make test-corsika       # 500 showers, ~8 min — esto sí es razonable en laptop
# La producción (make prod-corsika) son 13 h colgada — no recomendado
```

Para análisis después, las rutas de output ya están en `sim/output/`.

---

## Referencias dentro del repo

- [`README.md`](README.md) — overview general del proyecto
- [`docker/README.md`](docker/README.md) — detalle de las imágenes Docker
- [`sim/README.md`](sim/README.md) — formato de los outputs CORSIKA
- [`docs/corsika_parametros.md`](docs/corsika_parametros.md) — qué significa cada parámetro del steering
- [`docs/corsika_instalacion.md`](docs/corsika_instalacion.md) — compilación manual (sin Docker)
