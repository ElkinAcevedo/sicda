#!/usr/bin/env bash
# Empaqueta lo mínimo para ejecutar SICDA en otra máquina sin entrenar:
#   - el .joblib del modelo activo (models/activo.json) y su carpeta de versión;
#   - metadatos y predicciones de los demás modelos, para el panel de métricas
#     (sin sus .joblib ni los pesos de DistilBERT, que pesan cientos de MB);
#   - data/processed/{categorias.json,val.parquet,test.parquet}.
# Uso: ./scripts/empaquetar_modelos.sh [salida.zip]   (por defecto sicda-modelos.zip)
set -euo pipefail
cd "$(dirname "$0")/.."

salida="$(realpath -m "${1:-sicda-modelos.zip}")"
activo="$(python3 -c 'import json; print(json.load(open("models/activo.json"))["archivo"])')"
[ -f "models/$activo" ] || { echo "No existe models/$activo" >&2; exit 1; }

archivos=(models/activo.json "models/$activo" data/processed/categorias.json
          data/processed/val.parquet data/processed/test.parquet)
# Solo carpetas de versión con fecha (AAAAMMDD-HHMM); se omiten las de prueba.
while IFS= read -r f; do archivos+=("$f"); done < <(
  find models -mindepth 3 -maxdepth 3 -type f \( -name '*.json' -o -name '*.parquet' \) \
    -regextype posix-extended -regex 'models/[^/]+/[0-9]{8}-[0-9]{4}/[^/]+' | sort)

rm -f "$salida"
zip -q "$salida" "${archivos[@]}"
echo "Paquete: $salida ($(du -h "$salida" | cut -f1), ${#archivos[@]} archivos)"
