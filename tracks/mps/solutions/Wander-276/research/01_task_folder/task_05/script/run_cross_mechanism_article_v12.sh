#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
MANUSCRIPT_DIR="$REPO_DIR/overleaf_sync/cross_mechanism_geometric_eth"
PYTHON_BIN="${PYTHON_BIN:-python3}"

export PYTHONPATH="$SCRIPT_DIR${PYTHONPATH:+:$PYTHONPATH}"

"$PYTHON_BIN" "$SCRIPT_DIR/make_cross_mechanism_manuscript_assets_v12.py"
(
  cd "$MANUSCRIPT_DIR"
  latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
  latexmk -pdf -interaction=nonstopmode -halt-on-error supplement.tex
)
cp "$MANUSCRIPT_DIR/main.pdf" "$SCRIPT_DIR/output/mechanism_dependent_geometric_eth_v12.pdf"
cp "$MANUSCRIPT_DIR/supplement.pdf" "$SCRIPT_DIR/output/mechanism_dependent_geometric_eth_supplement_v12.pdf"
"$PYTHON_BIN" "$SCRIPT_DIR/verify_cross_mechanism_manuscript_v12.py"
