#!/usr/bin/env bash
# Regenera los 6 CSV de data/ desde la base Guatecompras vía SSH + COPY TO STDOUT.
# No deja archivos en el servidor. Requiere acceso SSH al host de la base.
#
# Uso:
#   ./sql/dump_data.sh
#   SSH_HOST=guatecompras-dev DB=guatecompras_dev ./sql/dump_data.sh
set -euo pipefail

SSH_HOST="${SSH_HOST:-guatecompras-dev}"   # host SSH (ver ~/.ssh/config)
DB="${DB:-guatecompras_dev}"               # base de datos PostgreSQL
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$(cd "$HERE/.." && pwd)/data"
mkdir -p "$OUT"

dump() {  # dump <archivo.sql> <salida.csv>
  local sql="$HERE/$1" dst="$OUT/$2"
  echo ">> $2"
  { printf 'COPY (\n'; cat "$sql"; printf '\n) TO STDOUT WITH CSV HEADER;\n'; } \
    | ssh "$SSH_HOST" "psql -X -q -d '$DB' -v ON_ERROR_STOP=1 -f -" > "$dst"
  echo "   $(( $(wc -l < "$dst") - 1 )) filas -> $dst"
}

dump 01_renglones_salud.sql renglones_salud.csv
dump 02_ofertas_muestra.sql ofertas_muestra.csv
dump 03_nit_features.sql    nit_features.csv
dump 04_propuestas.sql      propuestas.csv
dump 05_insumo_series.sql   insumo_series.csv
dump 06_areas_uso.sql       areas_uso.csv
echo "Listo. CSV en $OUT"
