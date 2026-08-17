# Simulación Monte Carlo sobre Guatecompras — compras de salud del IGSS

Proyecto del curso *Modelos y Simulación de Sistemas*. Simulación Monte Carlo de
licitaciones de compra pública (portal **Guatecompras**) en el segmento de salud
del **IGSS**. Modela cómo se forma el precio ganador cuando compiten varios
proveedores y responde dos preguntas: **a qué precio conviene ofertar** (óptica
del proveedor) y **cuánto vale la competencia** para el Estado.

## El modelo en una línea

Licitación competitiva tipo Friedman: en un renglón compiten N proveedores, cada
uno presenta una oferta y el modelo toma la **oferta mínima** como base,
ponderada por una **probabilidad de admisión**.

> **Sobre el precio.** El modelo **no supone que gane el precio más bajo por
> regla.** La adjudicación depende de la evaluación de requisitos y puede ganar
> cualquier oferente. Se modela como la oferta mínima ponderada por una
> probabilidad de admisión estimada en **0.99**, porque empíricamente en este
> segmento el más barato gana ~99% de las veces (`p_win_by_rank` en
> `output/params.json`).

## Dos enfoques

El repositorio tiene dos iteraciones que comparten la idea de licitación
competitiva:

**A. Ideas — segmento salud completo** (`engine.py`, `00`–`07`).
Motor abstracto: cópula gaussiana de un factor en espacio normalizado
(mediana = 1), con dispersión `sigma = 0.209` y correlación `rho = 0` calibradas
contra todo el segmento (557,710 renglones). Responde la Idea 1 (precio óptimo del
proveedor) y la Idea 3 (ahorro por competencia), con etapa de admisión y análisis
de sensibilidad.

**B. Propuestas — IGSS, productos concretos** (`p1_*`, `p2_*`, `08`, `09`,
`p_export_*`). Enfoque directo sobre productos con nombre. Ajusta una LogNormal al
histórico de precios reales (en quetzales) sin cópula. Es el entregable pulido,
con presentación HTML interactiva y Excel con calculadoras.

## Estructura

```
src/                          código (ver "Cómo reproducir")
data/                         CSV de entrada — NO versionados (ver "Datos")
output/                       resultados, figuras y entregables — NO versionados
requirements.txt
README.md
RESUMEN_Y_PROCEDIMIENTO.md    procedimiento detallado
```

## Datos

Los CSV de `data/` **no se versionan** (pesan ~83 MB y son extractos
regenerables). Se obtienen del PostgreSQL de Guatecompras vía SSH con
`COPY ... TO STDOUT`. Los **queries exactos** (verificados contra la base) y el
script `dump_data.sh` para regenerarlos están en [`sql/`](sql/README.md). Archivos
esperados en `data/`:

| Archivo | Usado por | Contenido |
|---|---|---|
| `renglones_salud.csv` | Ideas (`01`, `engine`) | 1 fila por renglón: nº ofertas y precios min/avg/sd/max |
| `ofertas_muestra.csv` | Ideas (`engine`, `06`) | 1 fila por oferta (muestra de 1/10 renglones) |
| `nit_features.csv` | Ideas (`06`) | 1 fila por proveedor: antigüedad, participaciones, ganados |
| `propuestas.csv` | Propuestas (`p1`, `p2`, `p_export`) | ofertas del IGSS con nombre de producto |
| `insumo_series.csv` | `08_insumo` | serie temporal de insumos (Sitagliptina, Trastuzumab) |
| `areas_uso.csv` | `09_areas` | ofertas clasificadas por área clínica |

## Cómo reproducir

```bash
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt
# 1) generar los CSV de data/ por SSH (COPY) — ver RESUMEN_Y_PROCEDIMIENTO.md, Paso 2

# --- A. Ideas (segmento completo) ---
.venv/bin/python src/01_calibrate.py     # crea output/params.json
.venv/bin/python src/engine.py           # estima sigma, calibra rho, valida
.venv/bin/python src/06_admision.py      # etapa de admisión
.venv/bin/python src/03_idea3.py         # ahorro (Estado)
.venv/bin/python src/04_idea1.py         # precio óptimo (proveedor)
.venv/bin/python src/07_sensibilidad.py  # tornados
.venv/bin/python src/05_export_excel.py  # Excel Ideas

# --- B. Propuestas (IGSS) ---
.venv/bin/python src/p1_precio.py        # precio para ganar (Insulina glargina)
.venv/bin/python src/p2_ahorro.py        # valor de la competencia (cardiometabólicos)
.venv/bin/python src/08_insumo.py        # precio del mismo insumo en el tiempo
.venv/bin/python src/09_areas.py         # comparación por área clínica
.venv/bin/python src/p_export_html.py    # presentación HTML
.venv/bin/python src/p_export_excel.py   # Excel Propuestas
```

El orden importa: `engine.py` y los scripts `03`/`04`/`06`/`08`/`09` leen
`output/params.json`, que crea `01_calibrate.py`.

## Resultados principales

**Propuesta 1 — Insulina glargina (proveedor).** Precio óptimo Q391.64,
P(ganar | hay competencia) 0.65, ganancia esperada Q55.94/unidad (costo = margen
bruto 30% sobre la mediana); 50% de concursos sin competencia (rivales = N−1,
óptimo condicional a N≥2). Correlación precio–competidores
−0.41.

**Propuesta 2 — Cardiometabólicos (Estado).** 40% de renglones sin competencia;
ahorro anual mediano Q89.6 M frente al 2º postor; potencial +Q61.9 M/año si los
renglones sin competencia la tuvieran.

**Ideas (segmento salud).** 54.4% de renglones con una sola oferta; `sigma = 0.209`,
`rho = 0` (sin evidencia de colusión en promedio); ahorro 15–17% donde hay
competencia.

## Notas y limitaciones

- El **costo del proveedor es una entrada** (supuesto), no un dato del portal: en
  la Propuesta 1 se usa 75% del precio mediano.
- El precio no decide por ley (ver "Sobre el precio"); el modelo lo captura vía la
  probabilidad de admisión.
- Los entregables interactivos (HTML/Excel) usan **fórmulas cerradas** equivalentes
  a la simulación.
- Fuente: Guatecompras, entidad IGSS, salud, recepción electrónica, concursos
  adjudicados 2022–2025.
