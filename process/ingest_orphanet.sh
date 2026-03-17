#!/usr/bin/env bash

set -euo pipefail

# ===============================
# ORPHANET DATA DOWNLOAD
# ===============================
# This script downloads the required Orphanet XML files for the rare disease
# knowledge graph. These files are NOT part of the standard S3 ingest bucket.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
DATA_DIR="$ROOT_DIR/files/data/orphanet"

# Create orphanet data directory
mkdir -p "$DATA_DIR"

echo "Downloading Orphanet XML files..."

# Download individual Orphanet XML product files
ORPHANET_BASE_URL="https://www.orphadata.com/data/xml"

FILES_TO_DOWNLOAD=(
  "en_product6.xml"  # Disease-gene associations
  "en_product1.xml"  # Disease metadata and external identifiers
  "en_product4.xml"  # Disease-phenotype (HPO) associations
  "en_funct_consequences.xml"  # Disease-disability associations
)

for file in "${FILES_TO_DOWNLOAD[@]}"; do
  echo "Downloading $file..."
  if ! curl -f -L -o "$DATA_DIR/$file" "$ORPHANET_BASE_URL/$file" 2>/dev/null; then
    echo "Warning: Failed to download $file. This file may be optional."
  fi
done

echo "Orphanet XML files downloaded successfully to $DATA_DIR"
