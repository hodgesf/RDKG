#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

INPUT_DIR="$ROOT_DIR/files/zip"

echo "Looking in: $INPUT_DIR"
ls -lh "$INPUT_DIR"

shopt -s nullglob
files=("$INPUT_DIR"/*.tar.zst)

echo "Found ${#files[@]} .tar.zst files"

for file in "${files[@]}"; do
    echo "Processing: $file"

    fname=$(basename "$file")
    name="${fname%.tar.zst}"
    outdir="$INPUT_DIR/$name"

    mkdir -p "$outdir"

    tar -I zstd -xvf "$file" -C "$outdir"
done