#!/usr/bin/env bash
#SBATCH --job-name=square-rat-witness
#SBATCH --partition=kshcnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=12G
#SBATCH --time=00:30:00
#SBATCH --output=tracks/polyopt/solutions/sdp-gap-seekers/results/slurm-%j.out

set -euo pipefail

: "${SQUARE_INPUT_POINT:?set SQUARE_INPUT_POINT to the immutable gamma=2 input}"
: "${SQUARE_SOLVE_POINT:?set SQUARE_SOLVE_POINT to the exported gamma=2 solve}"
: "${SQUARE_RUN_ID:?set SQUARE_RUN_ID to a unique result directory name}"

JULIA_BIN="${JULIA_BIN:-$HOME/julia-1.11.5/bin/julia}"

REPOSITORY_ROOT="$(git rev-parse --show-toplevel)"
JULIA_PROJECT="${JULIA_PROJECT:-$REPOSITORY_ROOT/julia-env}"
EXPECTED_ROOT="${SQUARE_EXPECTED_REPOSITORY_ROOT:-$REPOSITORY_ROOT}"
[[ "$REPOSITORY_ROOT" == "$EXPECTED_ROOT" ]] || {
    echo "[square-isotypic-rational-witness] refusing checkout: $REPOSITORY_ROOT" >&2
    exit 2
}
cd "$REPOSITORY_ROOT"

[[ -x "$JULIA_BIN" ]]
[[ -d "$JULIA_PROJECT" ]]
[[ -f "$SQUARE_INPUT_POINT/model.mof.json" ]]
[[ -f "$SQUARE_INPUT_POINT/runmeta.toml" ]]
[[ -f "$SQUARE_INPUT_POINT/SHA256SUMS" ]]
[[ -f "$SQUARE_SOLVE_POINT/result.toml" ]]
[[ -f "$SQUARE_SOLVE_POINT/primal-values.tsv" ]]
[[ -z "$(git status --porcelain --untracked-files=all)" ]] || {
    echo "[square-isotypic-rational-witness] refusing dirty checkout" >&2
    exit 2
}

RUN_DIR="tracks/polyopt/solutions/sdp-gap-seekers/results/${SQUARE_RUN_ID}"
[[ ! -e "$RUN_DIR" ]] || {
    echo "[square-isotypic-rational-witness] refusing existing run directory: $RUN_DIR" >&2
    exit 2
}
mkdir -p "$RUN_DIR/certificate"

export JULIA_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"

git rev-parse HEAD > "$RUN_DIR/runner-commit.txt"
git status --porcelain --untracked-files=all > "$RUN_DIR/git-status.txt"

echo "[square-isotypic-rational-witness] run_id=$SQUARE_RUN_ID"
echo "[square-isotypic-rational-witness] job_id=${SLURM_JOB_ID:-missing}"
echo "[square-isotypic-rational-witness] host=$(hostname)"
echo "[square-isotypic-rational-witness] started=$(date -u +%Y-%m-%dT%H:%M:%SZ)"

set +e
/usr/bin/time -v -o "$RUN_DIR/process-time.txt" \
    "$JULIA_BIN" \
    --project="$JULIA_PROJECT" \
    --startup-file=no \
    --history-file=no \
    tracks/polyopt/solutions/sdp-gap-seekers/scripts/replay_square_isotypic_rational_witness.jl \
    --input-directory "$SQUARE_INPUT_POINT" \
    --solve-directory "$SQUARE_SOLVE_POINT" \
    --output "$RUN_DIR/certificate" \
    2>&1 | tee "$RUN_DIR/replay.log"
replay_exit="${PIPESTATUS[0]}"
set -e

printf '%s\n' "$replay_exit" > "$RUN_DIR/replay-exit-code.txt"
printf '%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$RUN_DIR/finished-at-utc.txt"
(
    cd "$RUN_DIR"
    checksum_files=(
        replay.log
        process-time.txt
        runner-commit.txt
        git-status.txt
        replay-exit-code.txt
        finished-at-utc.txt
    )
    [[ -f certificate/exact-replay.toml ]] &&
        checksum_files+=(certificate/exact-replay.toml)
    [[ -f certificate/rational-witness.tsv ]] &&
        checksum_files+=(certificate/rational-witness.tsv)
    [[ -f certificate/SHA256SUMS ]] &&
        checksum_files+=(certificate/SHA256SUMS)
    sha256sum "${checksum_files[@]}" > SHA256SUMS
)

echo "[square-isotypic-rational-witness] replay_exit=$replay_exit"
echo "[square-isotypic-rational-witness] finished=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
sync
exit "$replay_exit"
