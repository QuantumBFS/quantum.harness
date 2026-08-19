#!/usr/bin/env bash
#SBATCH --job-name=square-l1d3-solve
#SBATCH --partition=kshcnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=110G
#SBATCH --time=12:00:00
#SBATCH --output=tracks/polyopt/solutions/sdp-gap-seekers/results/slurm-%j.out

set -euo pipefail

: "${SQUARE_L1D3_SOLVE_RUN_ID:?set a unique solve-record directory name}"
: "${SQUARE_L1D3_INPUT:?set the repository-relative input directory}"

JULIA_BIN="${JULIA_BIN:-$HOME/julia-1.11.5/bin/julia}"
MOSEK_BIN_DIR="${MOSEK_BIN_DIR:-$HOME/mosek/mosek/11.2/tools/platform/linux64x86/bin}"
JULIA_LIB_DIR="${JULIA_LIB_DIR:-$HOME/julia-1.11.5/lib/julia}"

REPOSITORY_ROOT="$(git rev-parse --show-toplevel)"
EXPECTED_ROOT="${SQUARE_L1D3_EXPECTED_REPOSITORY_ROOT:-$REPOSITORY_ROOT}"
[[ "$REPOSITORY_ROOT" == "$EXPECTED_ROOT" ]] || {
    echo "[square-l1d3-solve] refusing checkout: $REPOSITORY_ROOT" >&2
    exit 2
}
cd "$REPOSITORY_ROOT"

JULIA_PROJECT="${JULIA_PROJECT:-$REPOSITORY_ROOT/julia-env}"
[[ -x "$JULIA_BIN" ]]
[[ -d "$JULIA_PROJECT" ]]
[[ -d "$MOSEK_BIN_DIR" ]]
[[ -f "$SQUARE_L1D3_INPUT/model.mof.json" ]]
[[ -f "$SQUARE_L1D3_INPUT/runmeta.toml" ]]
[[ -f "$SQUARE_L1D3_INPUT/SHA256SUMS" ]]
[[ -z "$(git status --porcelain --untracked-files=all)" ]] || {
    echo "[square-l1d3-solve] refusing dirty checkout" >&2
    exit 2
}

RUN_DIR="tracks/polyopt/solutions/sdp-gap-seekers/results/${SQUARE_L1D3_SOLVE_RUN_ID}"
[[ ! -e "$RUN_DIR" ]] || {
    echo "[square-l1d3-solve] refusing existing run directory: $RUN_DIR" >&2
    exit 2
}
mkdir -p "$RUN_DIR"

export PATH="${MOSEK_BIN_DIR}:${PATH}"
export LD_LIBRARY_PATH="${JULIA_LIB_DIR}:${MOSEK_BIN_DIR}:${LD_LIBRARY_PATH:-}"
export JULIA_NUM_THREADS="${SLURM_CPUS_PER_TASK:-32}"
export SQUARE_L1D3_DYNAMIC_INPUT=1

git rev-parse HEAD > "$RUN_DIR/runner-commit.txt"
git rev-parse 'HEAD^{tree}' > "$RUN_DIR/runner-tree.txt"
git status --porcelain --untracked-files=all > "$RUN_DIR/git-status.txt"
printf '%s\n' "$JULIA_PROJECT" > "$RUN_DIR/julia-project.txt"

echo "[square-l1d3-solve] run_id=$SQUARE_L1D3_SOLVE_RUN_ID"
echo "[square-l1d3-solve] job_id=${SLURM_JOB_ID:-missing}"
echo "[square-l1d3-solve] host=$(hostname)"
echo "[square-l1d3-solve] cpus=${SLURM_CPUS_PER_TASK:-missing}"
echo "[square-l1d3-solve] mem_per_node=${SLURM_MEM_PER_NODE:-missing}"
echo "[square-l1d3-solve] input=$SQUARE_L1D3_INPUT"
echo "[square-l1d3-solve] started=$(date -u +%Y-%m-%dT%H:%M:%SZ)"

runner=(
    "$JULIA_BIN"
    --project="$JULIA_PROJECT"
    --startup-file=no
    --history-file=no
    tracks/polyopt/solutions/sdp-gap-seekers/scripts/solve_square_l1d3_spatial_reflection_reduced_mof.jl
    --model "$SQUARE_L1D3_INPUT/model.mof.json"
    --runmeta "$SQUARE_L1D3_INPUT/runmeta.toml"
    --checksums "$SQUARE_L1D3_INPUT/SHA256SUMS"
    --expected-gamma 2
    --repository-root "$REPOSITORY_ROOT"
    --output "$RUN_DIR/solve-result.toml"
    --time-limit-seconds 39600
    --threads "${SLURM_CPUS_PER_TASK:-32}"
    --audit-tolerance 1e-7
)

set +e
/usr/bin/time -v -o "$RUN_DIR/solve-process-time.txt" \
    "${runner[@]}" 2>&1 | tee "$RUN_DIR/solve.log"
solve_exit="${PIPESTATUS[0]}"
set -e
printf '%s\n' "$solve_exit" > "$RUN_DIR/solve-exit-code.txt"
printf '%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$RUN_DIR/finished-at-utc.txt"

(
    cd "$RUN_DIR"
    find . -type f ! -name SHA256SUMS -print0 |
        sort -z |
        xargs -0 sha256sum > SHA256SUMS
)

echo "[square-l1d3-solve] solve_exit=$solve_exit"
echo "[square-l1d3-solve] finished=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
sync
exit "$solve_exit"
