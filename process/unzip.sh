#!/usr/bin/env bash

set -euo pipefail

INPUT_DIR="files/zip"

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

    # safer: let tar handle zstd directly
    tar -I zstd -xvf "$file" -C "$outdir"
done