#!/usr/bin/env bash

# run_convert.sh
# Executes convert.py with the required inputs.

set -e

INPUT_FILE="ontologies.jsonl"
CURIES_TO_CATEGORIES="curies-to-categories.yaml"
CURIES_TO_URLS="curies-to-urls-map.yaml"
BIOLINK_VERSION="4.3.5"

OUTPUT_NODES="nodes.jsonl"
OUTPUT_EDGES="edges.jsonl"

python3 convert.py \
    "$INPUT_FILE" \
    "$CURIES_TO_CATEGORIES" \
    "$CURIES_TO_URLS" \
    "$BIOLINK_VERSION" \
    "$OUTPUT_NODES" \
    "$OUTPUT_EDGES"