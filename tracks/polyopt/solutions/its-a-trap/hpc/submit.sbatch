#!/bin/bash
#SBATCH --job-name=t1q-scnet
#SBATCH --partition=xhhgnormal
#SBATCH --cpus-per-task=16
#SBATCH --mem=120G
#SBATCH --time=12:00:00
#SBATCH --array=1-23%4
#SBATCH --output=slurm-%A_%a.out
# One overnight_harness cell per array task; cells.txt line = task id.
# Every cell writes its OWN outdir (results.csv append is not concurrency-safe)
# — merge rows after fetch with merge_results.sh.
set -u
cd "$HOME/quantum.harness"
export PATH="$HOME/julia/bin:$PATH"   # mirror-installed 1.12.6 (bootstrap_remote.sh)
export MAX_WALL_S=42000 MAX_RSS_GB=110 MAX_PROC_SWAP_GB=2 MOSEK_THREADS=8

RUN="${RUN_NAME:?set RUN_NAME via sbatch --export}"
SPEC=$(grep -v '^#' tracks/polyopt/solutions/its-a-trap/hpc/cells.txt \
       | sed -n "${SLURM_ARRAY_TASK_ID}p")
[ -n "$SPEC" ] || { echo "no cell for task ${SLURM_ARRAY_TASK_ID}"; exit 64; }
LABEL="${SPEC%%:*}"
OUT="tracks/polyopt/results/${RUN}/cell_${LABEL}"
mkdir -p "$OUT"
# per-cell reference copies (harness reads bethe_ref.json from its OUTDIR)
cp tracks/polyopt/solutions/its-a-trap/hpc/refs/bethe_ref.json   "$OUT/" 2>/dev/null || true
cp tracks/polyopt/solutions/its-a-trap/hpc/refs/table4_refs.json "$OUT/" 2>/dev/null || true

echo "=== cell $LABEL spec=$SPEC start $(date -Is) node=$(hostname)"
julia -t 4 --project=julia-env \
  tracks/polyopt/solutions/its-a-trap/overnight_harness.jl "$OUT" t1q-scnet "$SPEC"
rc=$?
echo "=== cell $LABEL exit=$rc $(date -Is)"
exit $rc
