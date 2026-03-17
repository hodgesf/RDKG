#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

BASE_URL="https://translator-ingests.s3.us-east-1.amazonaws.com/releases"
OUT_DIR="$ROOT_DIR/files/data"

SOURCES=(
  bindingdb
  chembl
  dgidb
  gene2phenotype
  goa
  hpoa
  icees
  intact
  ncbi_gene
  panther
  sider
  signor
  ubergraph
)

mkdir -p "$OUT_DIR"

for src in "${SOURCES[@]}"; do
  url="${BASE_URL}/${src}/latest/${src}.tar.zst"
  out_dir="${OUT_DIR}/${src}"
  out_file="${out_dir}/${src}.tar.zst"

  # Check if directory already has files (skip if it does)
  if [ -d "$out_dir" ] && [ "$(ls -A "$out_dir")" ]; then
    echo "Skipping ${src} (already downloaded)"
    continue
  fi

  mkdir -p "$out_dir"

  echo "Downloading ${src}..."
  curl -L "$url" -o "$out_file"
done

echo "All downloads complete."