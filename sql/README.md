# Extracción de datos (`data/*.csv`)

Los CSV de `data/` no se versionan (regenerables, ~83 MB). Aquí están las tablas,
los filtros y los queries para volver a generarlos desde la base **Guatecompras**
(`guatecompras_dev`, PostgreSQL) accesible por SSH.

## Requisito
Acceso SSH al host de la base (`guatecompras-dev` en tu `~/.ssh/config`). **Sin ese
acceso los queries no se pueden correr** desde otra máquina — es el punto a resolver
para trabajar en otra computadora.

## Tablas usadas
- **`estado_oferta`** — 1 fila por oferta `(nog, producto, nit)`. Tabla materializada
  con `precio_unitario, precio_total, ranking_de_precio, ofertas_por_producto,
  unidades_demanda, unidades_oferta, marca, estado` (desenlace de la oferta).
- **`concurso`** — 1 fila por concurso (`nog`): `fecha_publicacion, modalidad,
  entidad, tipo_recepcion, estatus`.
- **`concurso_categoria`** — categoría por concurso (salud = 26).
- **`estatus`** — mapa de estatus crudo (`estatus_gc`) → canónico (`estatus_kemok`).
- **`producto`** — descriptor del renglón: `id, nombre, caracteristicas, unidad_medida`.

## Segmento (filtros verificados contra la base)
- salud: `exists (select 1 from concurso_categoria cc where cc.nog=c.nog and cc.categoria=26)`
- recepción electrónica: `c.tipo_recepcion = 'Sólo electrónicas'`
- adjudicado: `c.estatus in (select estatus_gc from estatus where estatus_kemok='Adjudicado')`
- fechas: `c.fecha_publicacion >= '2022-01-01' and < '2026-01-01'`
- IGSS (solo Gen-2): `c.entidad = '52'`
- ganó la oferta: `estado_oferta.estado like 'Adjudicaci%'`

## Archivos, query y verificación
| CSV | Query | Ámbito | Verificación |
|---|---|---|---|
| `renglones_salud.csv` | `01_renglones_salud.sql` | todas las entidades | 558,019 renglones ✅ |
| `ofertas_muestra.csv` | `02_ofertas_muestra.sql` | todas · muestra `mod(producto,10)=0` | 113,369 ofertas ✅ |
| `nit_features.csv` | `03_nit_features.sql` | NIT del segmento · features globales | 2,775 NIT ✅ |
| `propuestas.csv` | `04_propuestas.sql` | IGSS (superconjunto) | columnas ✅ · ver nota |
| `insumo_series.csv` | `05_insumo_series.sql` | IGSS + Sitagliptina/Trastuzumab | 8,887 ofertas ✅ |
| `areas_uso.csv` | `06_areas_uso.sql` | IGSS (superconjunto) | columnas ✅ · ver nota |

**Nota Gen-2:** `propuestas` y `areas_uso` originales estaban filtrados por una lista
curada de medicamentos que no quedó registrada. Las queries 04/06 traen el segmento
IGSS completo; los scripts (`p1_precio.py`, `p2_ahorro.py`, `09_areas.py`) re-filtran
por nombre, así que reproducen los análisis. `n_pos` (en `renglones_salud`) se
reconstruye como `count(distinct nit)`.

## Cómo dumpear
```bash
# requiere SSH a guatecompras-dev
./sql/dump_data.sh
# o con otra config:
SSH_HOST=guatecompras-dev DB=guatecompras_dev ./sql/dump_data.sh
```
Cada query se envía como `COPY (<query>) TO STDOUT WITH CSV HEADER` por SSH, sin dejar
archivos en el servidor. Los CSV se escriben en `data/`.

## Extensiones (para trabajo futuro, no usadas en la extracción actual)

Tablas para enriquecer o refinar el modelo más adelante. No cambian los CSV actuales.

- **`mapeo_producto` → `catalogo_producto`** — normalización de productos. En salud los
  `producto.nombre` ya son genéricos limpios (por eso el filtro por nombre crudo reprodujo
  el dato exacto) y `marca` guarda la marca; para comparar "el mismo producto" en otras
  categorías o por marca, mapear `producto.id` → `catalogo_producto` (trae clasificación y
  `palabras_clave`). Mejora de robustez, no arreglo.
- **`provider`** (registro RGAE/SAT, jsonb) — habilitado/inhabilitado, inconformidades,
  historial de adjudicación. Para una etapa de riesgo/admisión más rica (ej. inhabilitado
  ⇒ P(ganar)=0), en vez de solo la antigüedad de `nit_features`.
- **`historial`** (bitácora por `nog`: `accion`, `fecha`) — modelar TIEMPOS del proceso
  (publicación → evaluación → adjudicación) como variable simulable nueva.
- **`modalidad`** (catálogo, 86 filas) — estratificar por procedimiento (Compra Directa vs
  Licitación vs Cotización), con competencia y montos distintos. `concurso.modalidad` ya
  está en los CSV; hoy el análisis agrupa.
- **`producto_analisis_precio`** (~2.0M filas) — fact table alterna. OJO: es más chica que
  `estado_oferta` (7.4M), parece un subconjunto curado y NO está verificada para reproducir
  estos CSV; usar solo tras comparar.
- **`adjudicacion`** (`nit, nog`; monto, contrato, monto_pagado) — fuente alterna del
  ganador y el monto pagado. Acá el win se marca con `estado_oferta.estado LIKE
  'Adjudicaci%'` (verificado); si se usa `adjudicacion`, validar que coincida.

**Caveat transversal:** para "adjudicado" siempre pasar por la tabla `estatus`
(`estatus_kemok='Adjudicado'`), no por el texto literal de `concurso.estatus` — filtrar
`estatus='Adjudicado'` deja fuera `'Terminado adjudicado'` (~422 mil concursos) y otros.
