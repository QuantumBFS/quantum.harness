#!/bin/bash
set -euo pipefail
umask 077

for name in CTHYB_MICROMAMBA CTHYB_ENV CTHYB_INPUT CTHYB_ROOT; do
  value="${!name:-}"
  if [[ -z "$value" || "$value" != /* ]]; then
    printf '%s must be an absolute path\n' "$name" >&2
    exit 2
  fi
done
case "${SLURM_ARRAY_TASK_ID:-}" in
  ''|*[!0-9]*) exit 2 ;;
esac
if ((SLURM_ARRAY_TASK_ID > 3)); then exit 2; fi
for name in SLURM_NTASKS SLURM_CPUS_PER_TASK OMP_NUM_THREADS OPENBLAS_NUM_THREADS MKL_NUM_THREADS; do
  if [[ "${!name:-}" != 1 ]]; then
    printf '%s must equal 1\n' "$name" >&2
    exit 2
  fi
done
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
exec "$CTHYB_MICROMAMBA" --offline run --prefix "$CTHYB_ENV" \
  python "$SCRIPT_DIR/run_chain.py" --input "$CTHYB_INPUT" \
  --chain-index "$SLURM_ARRAY_TASK_ID" --output-root "$CTHYB_ROOT"
