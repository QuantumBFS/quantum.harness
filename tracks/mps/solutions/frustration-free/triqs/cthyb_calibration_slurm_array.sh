#!/bin/bash
set -euo pipefail
umask 077

for name in CTHYB_MICROMAMBA CTHYB_ENV CTHYB_CAL_PLAN CTHYB_CAL_RUN CTHYB_SOURCE; do
  value="${!name:-}"
  if [[ -z "$value" || "$value" != /* ]]; then
    printf '%s must be an absolute path\n' "$name" >&2
    exit 2
  fi
done
case "${SLURM_ARRAY_TASK_ID:-}" in
  ''|*[!0-9]*) exit 2 ;;
esac
if ((SLURM_ARRAY_TASK_ID > 111)); then exit 2; fi
for name in SLURM_NTASKS SLURM_CPUS_PER_TASK OMP_NUM_THREADS OPENBLAS_NUM_THREADS MKL_NUM_THREADS; do
  if [[ "${!name:-}" != 1 ]]; then
    printf '%s must equal 1\n' "$name" >&2
    exit 2
  fi
done
export XDG_CACHE_HOME="$CTHYB_CAL_RUN/.mamba-cache-$SLURM_ARRAY_TASK_ID"
exec "$CTHYB_MICROMAMBA" --offline run --prefix "$CTHYB_ENV" \
  python "$CTHYB_SOURCE/calibrate.py" run-cell \
  --plan "$CTHYB_CAL_PLAN" --run-directory "$CTHYB_CAL_RUN" \
  --cell-index "$SLURM_ARRAY_TASK_ID"
