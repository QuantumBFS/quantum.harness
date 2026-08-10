#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:-test}"
PYTHON_BIN="${LEARNING_MIT_PYTHON:-$ROOT/.venv/bin/python}"
CARGO_PROFILE="${LEARNING_MIT_CARGO_PROFILE:---release}"

case "$MODE" in
  test)
    CONFIG="$ROOT/configs/test.toml"
    RESULT_PREFIX="learning-mit"
    ;;
  pilot)
    CONFIG="$ROOT/configs/pilot.toml"
    RESULT_PREFIX="learning-mit"
    ;;
  production)
    CONFIG="$ROOT/configs/production.toml"
    RESULT_PREFIX="learning-mit"
    ;;
  production-v2)
    CONFIG="$ROOT/configs/production-v2.toml"
    RESULT_PREFIX="learning-mit-production-v2"
    ;;
  *)
    echo "usage: $0 {test|pilot|production|production-v2} [run-directory]" >&2
    exit 2
    ;;
esac

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python environment is unavailable: $PYTHON_BIN" >&2
  echo "Run 'make setup' or set LEARNING_MIT_PYTHON." >&2
  exit 1
fi

if [[ $# -ge 2 ]]; then
  RUN_DIR="$2"
else
  TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
  RUN_DIR="$ROOT/../../../results/$RESULT_PREFIX-$TIMESTAMP"
fi
mkdir -p "$RUN_DIR"
cp "$CONFIG" "$RUN_DIR/config.toml"
export MPLCONFIGDIR="${MPLCONFIGDIR:-$RUN_DIR/.matplotlib-cache}"
mkdir -p "$MPLCONFIGDIR"

run_rust() {
  local command=(cargo run --offline)
  if [[ -n "$CARGO_PROFILE" ]]; then
    command+=("$CARGO_PROFILE")
  fi
  command+=(-- "$@")
  "${command[@]}"
}

cd "$ROOT"
echo "[1/8] scientific oracles"
run_rust oracles --config "$RUN_DIR/config.toml" --run-dir "$RUN_DIR"

echo "[2/8] runtime benchmark"
run_rust benchmark --config "$RUN_DIR/config.toml" --run-dir "$RUN_DIR"
if [[ "$MODE" == "production-v2" ]]; then
  "$PYTHON_BIN" -c \
    'import json, math, sys; value=float(json.load(open(sys.argv[1], encoding="utf-8"))["forecast_seconds"]); raise SystemExit(0 if math.isfinite(value) and value <= 5100 else f"forecast_seconds={value} exceeds production-v2 hard stop 5100")' \
    "$RUN_DIR/raw/benchmark.json"
fi

echo "[3/8] coarse Born simulation"
run_rust simulate --config "$RUN_DIR/config.toml" --run-dir "$RUN_DIR"

echo "[4/8] phase-only analysis and refinement request"
"$PYTHON_BIN" -m analysis.run_analysis --phase-only "$RUN_DIR"
REQUEST="$RUN_DIR/processed/refinement_request.json"
REQUEST_STATUS="$("$PYTHON_BIN" -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["status"])' "$REQUEST")"

if [[ "$REQUEST_STATUS" == "bracketed" || "$REQUEST_STATUS" == "exploratory" ]]; then
  echo "[5/8] hash-checked refinement simulation"
  run_rust simulate \
    --config "$RUN_DIR/config.toml" \
    --run-dir "$RUN_DIR" \
    --task-request "$REQUEST"
else
  echo "[5/8] no defensible bracket; preserving inconclusive coarse result"
fi

echo "[6/8] nonphysical IID negative control"
run_rust negative-control --config "$RUN_DIR/config.toml" --run-dir "$RUN_DIR"

echo "[7/8] final frozen-data analysis and bilingual reports"
"$PYTHON_BIN" -m analysis.run_analysis --final "$RUN_DIR"

echo "[8/8] structural report verification"
"$PYTHON_BIN" -c \
  'import sys; from pathlib import Path; from analysis.verify_outputs import verify_report_pair; r=verify_report_pair(Path(sys.argv[1])); print(r); raise SystemExit(0 if r.passed else 1)' \
  "$RUN_DIR"

echo "completed result: $RUN_DIR"
