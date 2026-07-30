#!/usr/bin/env bash
#SBATCH --job-name=ss-conj-truth
#SBATCH --partition=xhacnormalb
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=12G
#SBATCH --time=00:30:00
#SBATCH --output=tracks/polyopt/solutions/sdp-gap-seekers/results/slurm-%j.out

set -euo pipefail

: "${SS_RUN_ID:?set SS_RUN_ID to a unique result directory name}"

JULIA_BIN="${JULIA_BIN:-$HOME/.julia/juliaup/julia-1.11.5+0.x64.linux.gnu/bin/julia}"
JULIA_PROJECT="${JULIA_PROJECT:-$HOME/quantum-hackson/challenge-88/repo-cb725ac3/julia-env}"

REPOSITORY_ROOT="$(git rev-parse --show-toplevel)"
EXPECTED_ROOT="$HOME/quantum-hackson/challenge-88/bohr-agent/ss-exact-reduction"
[[ "$REPOSITORY_ROOT" == "$EXPECTED_ROOT" ]] || {
    echo "[ss-conj-truth] refusing checkout: $REPOSITORY_ROOT" >&2
    exit 2
}
cd "$REPOSITORY_ROOT"

[[ -x "$JULIA_BIN" ]]
[[ -d "$JULIA_PROJECT" ]]

RUN_DIR="tracks/polyopt/solutions/sdp-gap-seekers/results/${SS_RUN_ID}"
[[ ! -e "$RUN_DIR" ]] || {
    echo "[ss-conj-truth] refusing existing run directory: $RUN_DIR" >&2
    exit 2
}
mkdir -p "$RUN_DIR"

export JULIA_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"

git rev-parse HEAD > "$RUN_DIR/runner-commit.txt"
git status --porcelain --untracked-files=all > "$RUN_DIR/git-status.txt"

echo "[ss-conj-truth] run_id=$SS_RUN_ID"
echo "[ss-conj-truth] job_id=${SLURM_JOB_ID:-missing}"
echo "[ss-conj-truth] host=$(hostname)"
echo "[ss-conj-truth] started=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "[ss-conj-truth] cpus=${SLURM_CPUS_PER_TASK:-missing}"

set +e
/usr/bin/time -v -o "$RUN_DIR/process-time.txt" \
    "$JULIA_BIN" \
    --project="$JULIA_PROJECT" \
    --startup-file=no \
    --history-file=no \
    tracks/polyopt/solutions/sdp-gap-seekers/test/runtests.jl \
    2>&1 | tee "$RUN_DIR/test.log"
test_exit="${PIPESTATUS[0]}"
set -e

printf '%s\n' "$test_exit" > "$RUN_DIR/test-exit-code.txt"
printf '%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$RUN_DIR/finished-at-utc.txt"
(
    cd "$RUN_DIR"
    sha256sum \
        test.log \
        process-time.txt \
        runner-commit.txt \
        git-status.txt \
        test-exit-code.txt \
        finished-at-utc.txt > SHA256SUMS
)

echo "[ss-conj-truth] test_exit=$test_exit"
echo "[ss-conj-truth] finished=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
sync
exit "$test_exit"
