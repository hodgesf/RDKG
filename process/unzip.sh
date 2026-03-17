#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

INPUT_DIR="$ROOT_DIR/files/data"

echo "Looking in: $INPUT_DIR"

shopt -s nullglob
files=("$INPUT_DIR"/*/*.tar.zst)

echo "Found ${#files[@]} .tar.zst files"

for file in "${files[@]}"; do
    echo "Processing: $file"

    outdir="$(dirname "$file")"

    tar -I zstd -xvf "$file" -C "$outdir"
done