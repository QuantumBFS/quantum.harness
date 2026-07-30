#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-.venv-py312/bin/python}"
TARGET="${1:-all}"
OUTPUT_DIR="${OUTPUT_DIR:-results/paper}"
CACHE_DIR="${CACHE_DIR:-results/cache/uniform_tempo}"
FIGURE_DIR="${FIGURE_DIR:-figures/paper}"
FULL_KAC="${FULL_KAC:-0}"

run_n3() {
  "$PYTHON_BIN" -m floquet_if_manybody.cli n3-heat-grid \
    --output "$OUTPUT_DIR" --cache "$CACHE_DIR" --figures "$FIGURE_DIR"
}

run_errors() {
  "$PYTHON_BIN" -m floquet_if_manybody.cli error-map \
    --output "$OUTPUT_DIR" --cache "$CACHE_DIR" --figures "$FIGURE_DIR"
}

run_models() {
  local extra=()
  if [[ "$FULL_KAC" == "1" ]]; then
    extra+=(--full-kac)
  fi
  "$PYTHON_BIN" -m floquet_if_manybody.cli model-comparison \
    --output "$OUTPUT_DIR" --cache "$CACHE_DIR" --figures "$FIGURE_DIR" \
    "${extra[@]}"
}

case "$TARGET" in
  n3) run_n3 ;;
  errors) run_errors ;;
  models) run_models ;;
  all)
    run_n3
    run_errors
    run_models
    "$PYTHON_BIN" -m floquet_if_manybody.cli paper-audit "$OUTPUT_DIR"
    ;;
  *)
    echo "usage: $0 {n3|errors|models|all}" >&2
    exit 2
    ;;
esac
