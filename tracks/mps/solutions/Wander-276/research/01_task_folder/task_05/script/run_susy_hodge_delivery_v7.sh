#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
MANUSCRIPT_DIR="$REPO_DIR/overleaf_sync/cohomological_geometric_eth"
PYTHON_BIN="${PYTHON_BIN:-python3}"

export PYTHONPATH="$SCRIPT_DIR${PYTHONPATH:+:$PYTHONPATH}"

"$PYTHON_BIN" "$SCRIPT_DIR/merge_susy_hodge_pilot_v7.py"
"$PYTHON_BIN" "$SCRIPT_DIR/make_susy_hodge_figure_v7.py"
"$PYTHON_BIN" "$SCRIPT_DIR/make_susy_hodge_manuscript_assets_v7.py"
(
  cd "$MANUSCRIPT_DIR"
  latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
  latexmk -pdf -interaction=nonstopmode -halt-on-error supplement.tex
)
cp "$MANUSCRIPT_DIR/main.pdf" "$SCRIPT_DIR/output/response_complex_memory_v7.pdf"
cp "$MANUSCRIPT_DIR/supplement.pdf" "$SCRIPT_DIR/output/response_complex_memory_supplement_v7.pdf"
"$PYTHON_BIN" "$SCRIPT_DIR/verify_susy_hodge_delivery_v7.py"
"$PYTHON_BIN" "$SCRIPT_DIR/verify_susy_hodge_manuscript_v7.py"
