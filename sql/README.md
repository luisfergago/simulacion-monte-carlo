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
