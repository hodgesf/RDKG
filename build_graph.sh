#!/usr/bin/env bash

set -euo pipefail

# ===============================
# HELP
# ===============================
usage() {
  echo "Usage: ./build_graph [--setup | -s] [--help | -h]"
  echo ""
  echo "Options:"
  echo "  -s, --setup    Create/activate venv and install requirements"
  echo "  -h, --help     Show this help message"
  exit 0
}

# ===============================
# PARSE ARGS
# ===============================
SETUP=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    -s|--setup)
      SETUP=true
      shift
      ;;
    -h|--help)
      usage
      ;;
    *)
      echo "Unknown option: $1"
      usage
      ;;
  esac
done

# ===============================
# PATHS
# ===============================
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$ROOT_DIR/venv"

# ===============================
# SETUP VENV (optional)
# ===============================
if [ "$SETUP" = true ]; then
  if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
  fi

  echo "Activating virtual environment..."
  source "$VENV_DIR/bin/activate"

  echo "Installing requirements..."
  pip install -r "$ROOT_DIR/setup/requirements.txt"
fi

# ===============================
# PIPELINE
# ===============================
echo "Starting build pipeline..."

echo "1. Ingesting data..."
bash "$ROOT_DIR/process/ingest_data.sh"

echo "1b. Ingesting Orphanet..."
bash "$ROOT_DIR/process/ingest_orphanet.sh"

echo "2. Unzipping data..."
bash "$ROOT_DIR/process/unzip.sh"

echo "2b. Transforming Orphanet..."
python "$ROOT_DIR/process/transform_orphanet.py"

echo "3. Merging graphs..."
python "$ROOT_DIR/process/merge_graphs.py" \
  --outputNodesFile "$ROOT_DIR/files/all_nodes.jsonl" \
  --outputEdgesFile "$ROOT_DIR/files/all_edges.jsonl" \
  --kgFileOrphanEdges "$ROOT_DIR/files/orphan_edges.jsonl" \
  --kgNodesFiles "$ROOT_DIR/files/data"/*/nodes.jsonl \
  --kgEdgesFiles "$ROOT_DIR/files/data"/*/edges.jsonl

echo "4. Filtering graph..."
python "$ROOT_DIR/process/filter_graph.py"

echo "5. Computing stats..."
python "$ROOT_DIR/stats/stats.py"

echo "Build complete."