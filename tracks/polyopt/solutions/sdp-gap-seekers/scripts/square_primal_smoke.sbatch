#!/bin/bash
#SBATCH --partition=xhacnormalb
#SBATCH --job-name=square-primal-g0
#SBATCH --time=00:30:00
#SBATCH --cpus-per-task=16
#SBATCH --mem-per-cpu=3800M
#SBATCH --output=results/slurm-square-primal-%j.out

set -euo pipefail

export PATH="$HOME/julia-1.11.5/bin:$PATH"
export MOSEKBINDIR="$HOME/mosek/mosek/11.2/tools/platform/linux64x86/bin"
export LD_LIBRARY_PATH="$HOME/julia-1.11.5/lib/julia:${LD_LIBRARY_PATH:-}"
export JULIA_NUM_THREADS="${SLURM_CPUS_PER_TASK:-16}"

cd "$SLURM_SUBMIT_DIR"

SOURCE_BUNDLE="tracks/polyopt/solutions/sdp-gap-seekers/results/square-primal-gate-b-20260728-r1"
SOURCE_POINT="${SOURCE_BUNDLE}/gamma-0"
RUN_ID="square-primal-smoke-${SLURM_JOB_ID}"
RUN_DIR="results/${RUN_ID}"
RESULT_PATH="${RUN_DIR}/result.toml"

mkdir -p "$RUN_DIR"

echo "[square-primal-sbatch] run_id=${RUN_ID}"
echo "[square-primal-sbatch] host=$(hostname)"
echo "[square-primal-sbatch] started=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "[square-primal-sbatch] source_point=${SOURCE_POINT}"
echo "[square-primal-sbatch] cpus=${SLURM_CPUS_PER_TASK:-unavailable}"
flush_output() {
    sync
}
flush_output

test -f "${SOURCE_POINT}/model.mof.json"
test -f "${SOURCE_POINT}/runmeta.toml"
test -f "${SOURCE_POINT}/SHA256SUMS"
(
    cd "$SOURCE_POINT"
    sha256sum -c SHA256SUMS
)

cp "${SOURCE_POINT}/runmeta.toml" "${RUN_DIR}/input-runmeta.toml"
cp "${SOURCE_POINT}/SHA256SUMS" "${RUN_DIR}/input-SHA256SUMS"
git rev-parse HEAD > "${RUN_DIR}/harness-commit.txt"
git status --porcelain --untracked-files=all > "${RUN_DIR}/git-status.txt"
env | LC_ALL=C sort > "${RUN_DIR}/environment.txt"

set +e
julia \
    --project=julia-env \
    --startup-file=no \
    --history-file=no \
    tracks/polyopt/solutions/sdp-gap-seekers/scripts/solve_square_primal_mof.jl \
    --model "${SOURCE_POINT}/model.mof.json" \
    --runmeta "${SOURCE_POINT}/runmeta.toml" \
    --output "$RESULT_PATH" \
    --time-limit-seconds 1800 \
    --threads "${SLURM_CPUS_PER_TASK:-16}"
solver_exit=$?
set -e

echo "$solver_exit" > "${RUN_DIR}/solver-exit-code.txt"
sacct \
    -j "$SLURM_JOB_ID" \
    --format=JobID,State,ExitCode,MaxRSS,Elapsed,AllocCPUS \
    -P > "${RUN_DIR}/sacct-provisional.txt" || true

(
    cd "$RUN_DIR"
    sha256sum \
        result.toml \
        input-runmeta.toml \
        input-SHA256SUMS \
        harness-commit.txt \
        git-status.txt \
        environment.txt \
        solver-exit-code.txt \
        sacct-provisional.txt > SHA256SUMS
)

echo "[square-primal-sbatch] solver_exit=${solver_exit}"
echo "[square-primal-sbatch] finished=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
flush_output
exit "$solver_exit"
