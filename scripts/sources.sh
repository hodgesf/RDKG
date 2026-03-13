#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

inventory="$ROOT_DIR/yaml/ont-load-inventory.yaml"
data_dir="$ROOT_DIR/raw_sources"
jsonl_dir="$ROOT_DIR/jsonl"

mkdir -p "$data_dir"
mkdir -p "$jsonl_dir"

echo "Starting non-ontology extraction"
date

python "$ROOT_DIR/transform/convert.py" \
    --inventory "$inventory" \
    --data_dir "$data_dir" \
    --output "$jsonl_dir"

echo "Finished non-ontology extraction"
date