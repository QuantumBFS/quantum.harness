#!/bin/bash
#SBATCH --partition=xhacnormalb
#SBATCH --job-name=square-conic
#SBATCH --time=00:15:00
#SBATCH --cpus-per-task=4
#SBATCH --mem-per-cpu=3800M
#SBATCH --output=slurm-square-conic-%j.out
#SBATCH --error=slurm-square-conic-%j.err

set -euo pipefail

export PATH="$HOME/julia-1.11.5/bin:$PATH"
export MOSEKBINDIR="$HOME/mosek/mosek/11.2/tools/platform/linux64x86/bin"
export LD_LIBRARY_PATH="$HOME/julia-1.11.5/lib/julia:${LD_LIBRARY_PATH:-}"
export JULIA_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"

cd "$SLURM_SUBMIT_DIR"

CONIC_BASIS="${CONIC_BASIS:-}"
CONIC_G="${CONIC_G:-}"
CONIC_GAMMA="${CONIC_GAMMA:-}"
CONIC_POS_DIM="${CONIC_POS_DIM:-}"
CONIC_GAP_DIM="${CONIC_GAP_DIM:-}"
CONIC_LABEL="${CONIC_LABEL:-}"

for var in CONIC_BASIS CONIC_G CONIC_GAMMA CONIC_POS_DIM CONIC_GAP_DIM CONIC_LABEL; do
    if [ -z "${!var:-}" ]; then
        echo "missing required env: $var" >&2
        exit 2
    fi
done

case "$CONIC_BASIS" in
    bare_weight_one|one_symbol_lift|bare_operator) ;;
    *) echo "CONIC_BASIS must be bare_weight_one, one_symbol_lift, or bare_operator" >&2; exit 2 ;;
esac

RUN_ID="square-conic-${CONIC_LABEL}-${SLURM_JOB_ID}"
RUN_DIR="results/${RUN_ID}"
BUILD_DIR="results/_build-${RUN_ID}"
RESULT_PATH="${RUN_DIR}/result.toml"
SUBMIT_STDOUT="slurm-square-conic-${SLURM_JOB_ID}.out"
SUBMIT_STDERR="slurm-square-conic-${SLURM_JOB_ID}.err"

mkdir -p "$RUN_DIR"
mv "$SUBMIT_STDOUT" "${RUN_DIR}/slurm.out"
mv "$SUBMIT_STDERR" "${RUN_DIR}/slurm.err"

echo "[square-conic-sbatch] run_id=${RUN_ID}"
echo "[square-conic-sbatch] host=$(hostname)"
echo "[square-conic-sbatch] started=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "[square-conic-sbatch] basis=${CONIC_BASIS} g=${CONIC_G} gamma=${CONIC_GAMMA}"
echo "[square-conic-sbatch] pos_dim=${CONIC_POS_DIM} gap_dim=${CONIC_GAP_DIM}"
echo "[square-conic-sbatch] cpus=${SLURM_CPUS_PER_TASK:-unavailable}"
sync

git rev-parse HEAD > "${RUN_DIR}/harness-commit.txt"
git status --porcelain --untracked-files=all > "${RUN_DIR}/git-status.txt"
env | LC_ALL=C sort > "${RUN_DIR}/environment.txt"

echo "[square-conic-sbatch] building SquareGapConic MOF (solver-free)"
julia \
    --project=julia-env \
    --startup-file=no \
    --history-file=no \
    tracks/polyopt/solutions/sdp-gap-seekers/scripts/build_square_conic_mof.jl \
    --basis "$CONIC_BASIS" \
    --g "$CONIC_G" \
    --gamma "$CONIC_GAMMA" \
    --output "$BUILD_DIR"

test -f "${BUILD_DIR}/model.mof.json"
test -f "${BUILD_DIR}/runmeta.toml"
( cd "$BUILD_DIR" && sha256sum -c SHA256SUMS )
cp "${BUILD_DIR}/runmeta.toml" "${RUN_DIR}/input-runmeta.toml"
cp "${BUILD_DIR}/SHA256SUMS" "${RUN_DIR}/input-build-SHA256SUMS"

echo "[square-conic-sbatch] solving via Mosek"
set +e
julia \
    --project=julia-env \
    --startup-file=no \
    --history-file=no \
    tracks/polyopt/solutions/sdp-gap-seekers/scripts/solve_square_primal_mof.jl \
    --model "${BUILD_DIR}/model.mof.json" \
    --runmeta "${BUILD_DIR}/runmeta.toml" \
    --output "$RESULT_PATH" \
    --expected-basis-family "$CONIC_BASIS" \
    --expected-positive-dimension "$CONIC_POS_DIM" \
    --expected-gap-dimension "$CONIC_GAP_DIM" \
    --expected-gamma "$CONIC_GAMMA" \
    --time-limit-seconds "${CONIC_TIME_LIMIT:-480}" \
    --threads "${SLURM_CPUS_PER_TASK:-4}"
solver_exit=$?
set -e

echo "$solver_exit" > "${RUN_DIR}/solver-exit-code.txt"
checksum_files=(
    input-runmeta.toml
    input-build-SHA256SUMS
    harness-commit.txt
    git-status.txt
    environment.txt
    solver-exit-code.txt
    sacct-provisional.txt
)
if test -f "$RESULT_PATH"; then
    checksum_files=(result.toml "${checksum_files[@]}")
else
    printf '%s\n' \
        "solver exited ${solver_exit} without producing result.toml" \
        > "${RUN_DIR}/result-missing.txt"
    checksum_files=(result-missing.txt "${checksum_files[@]}")
fi
for optional_artifact in preopt.toml mosek.log; do
    if test -f "${RUN_DIR}/${optional_artifact}"; then
        checksum_files=("${optional_artifact}" "${checksum_files[@]}")
    fi
done
sacct \
    -j "$SLURM_JOB_ID" \
    --format=JobID,State,ExitCode,MaxRSS,Elapsed,AllocCPUS \
    -P > "${RUN_DIR}/sacct-provisional.txt" || true

( cd "$RUN_DIR" && sha256sum "${checksum_files[@]}" > SHA256SUMS )

rm -rf "$BUILD_DIR"

echo "[square-conic-sbatch] solver_exit=${solver_exit}"
echo "[square-conic-sbatch] finished=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
sync
exit "$solver_exit"
