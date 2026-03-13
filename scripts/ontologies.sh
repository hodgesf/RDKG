#!/usr/bin/env bash
set -euo pipefail

# directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# repo root (one level up from scripts/)
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

parser="$ROOT_DIR/extract/owl_parser.py"
inventory="$ROOT_DIR/yaml/ont-load-inventory.yaml"
output="$ROOT_DIR/jsonl/ontologies.jsonl"
owl_dir="$ROOT_DIR/owl_files"

mkdir -p "$owl_dir"

echo "Starting ontology extraction"
date

python "$parser" "$inventory" "$owl_dir" "$output"

echo "Finished ontology extraction"
date