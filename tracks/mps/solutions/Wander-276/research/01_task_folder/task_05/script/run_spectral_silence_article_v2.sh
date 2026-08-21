#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
ARTICLE_DIR="$REPO_ROOT/overleaf_sync/geometric_eth_large_scale"
OUTPUT_DIR="$SCRIPT_DIR/output"
PYTHON_BIN="/Users/thomasjwang/miniforge3/bin/python3.12"

cd "$SCRIPT_DIR"
"$PYTHON_BIN" run_spectral_silence_v2.py
"$PYTHON_BIN" run_spectral_silence_statistics_v2.py
"$PYTHON_BIN" make_spectral_silence_figures_v2.py

cd "$ARTICLE_DIR"
latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex
cp main.pdf \
  "$OUTPUT_DIR/spectral_silence_and_geometric_chaos_v2.pdf"

cd "$SCRIPT_DIR"
"$PYTHON_BIN" -m pytest -q tests \
  | tee "$OUTPUT_DIR/pytest_v2.txt"
"$PYTHON_BIN" verify_spectral_silence_article_v2.py
