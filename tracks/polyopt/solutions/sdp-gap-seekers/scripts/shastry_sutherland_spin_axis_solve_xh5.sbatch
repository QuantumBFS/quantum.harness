#!/usr/bin/env bash
#SBATCH --job-name=ss-axis-solve
#SBATCH --partition=xhacnormalb
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=24G
#SBATCH --time=01:00:00
#SBATCH --output=tracks/polyopt/solutions/sdp-gap-seekers/results/slurm-%j.out

set -euo pipefail

: "${SS_INPUT_POINT:?set SS_INPUT_POINT to the immutable input directory}"
: "${SS_EXPECTED_GAMMA:?set SS_EXPECTED_GAMMA to 0 or 1/2}"
: "${SS_RUN_ID:?set SS_RUN_ID to a unique result directory name}"

JULIA_BIN="${JULIA_BIN:-$HOME/.julia/juliaup/julia-1.11.5+0.x64.linux.gnu/bin/julia}"
JULIA_PROJECT="${JULIA_PROJECT:-$HOME/quantum-hackson/challenge-88/repo-cb725ac3/julia-env}"
MOSEK_BIN_DIR="${MOSEK_BIN_DIR:-$HOME/quantum-hackson/toolchains/mosek-11.2/mosek/11.2/tools/platform/linux64x86/bin}"
MOSEK_LICENSE="${MOSEK_LICENSE:-$HOME/mosek/mosek.lic}"
SS_TIME_LIMIT_SECONDS="${SS_TIME_LIMIT_SECONDS:-3300}"
SS_AUDIT_TOLERANCE="${SS_AUDIT_TOLERANCE:-1e-7}"

REPOSITORY_ROOT="$(git rev-parse --show-toplevel)"
EXPECTED_ROOT="$HOME/quantum-hackson/challenge-88/bohr-agent/ss-exact-reduction"
[[ "$REPOSITORY_ROOT" == "$EXPECTED_ROOT" ]] || {
    echo "[ss-axis-solve] refusing checkout: $REPOSITORY_ROOT" >&2
    exit 2
}
cd "$REPOSITORY_ROOT"

[[ -x "$JULIA_BIN" ]]
[[ -d "$JULIA_PROJECT" ]]
[[ -d "$MOSEK_BIN_DIR" ]]
[[ -f "$MOSEK_LICENSE" ]]
[[ -f "$SS_INPUT_POINT/model.mof.json" ]]
[[ -f "$SS_INPUT_POINT/runmeta.toml" ]]
[[ -f "$SS_INPUT_POINT/SHA256SUMS" ]]

RUN_DIR="tracks/polyopt/solutions/sdp-gap-seekers/results/${SS_RUN_ID}"
[[ ! -e "$RUN_DIR" ]] || {
    echo "[ss-axis-solve] refusing existing run directory: $RUN_DIR" >&2
    exit 2
}
mkdir -p "$RUN_DIR"

export PATH="${MOSEK_BIN_DIR}:${PATH}"
export LD_LIBRARY_PATH="${MOSEK_BIN_DIR}:${LD_LIBRARY_PATH:-}"
export MOSEKLM_LICENSE_FILE="$MOSEK_LICENSE"
export JULIA_NUM_THREADS="${SLURM_CPUS_PER_TASK:-16}"

git rev-parse HEAD > "$RUN_DIR/runner-commit.txt"
git status --porcelain --untracked-files=all > "$RUN_DIR/git-status.txt"
cp "$SS_INPUT_POINT/runmeta.toml" "$RUN_DIR/input-runmeta.toml"
cp "$SS_INPUT_POINT/SHA256SUMS" "$RUN_DIR/input-SHA256SUMS"

echo "[ss-axis-solve] run_id=$SS_RUN_ID"
echo "[ss-axis-solve] job_id=${SLURM_JOB_ID:-missing}"
echo "[ss-axis-solve] host=$(hostname)"
echo "[ss-axis-solve] started=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "[ss-axis-solve] gamma=$SS_EXPECTED_GAMMA"
echo "[ss-axis-solve] cpus=${SLURM_CPUS_PER_TASK:-missing}"
echo "[ss-axis-solve] input=$SS_INPUT_POINT"

set +e
"$JULIA_BIN" \
    --project="$JULIA_PROJECT" \
    --startup-file=no \
    --history-file=no \
    tracks/polyopt/solutions/sdp-gap-seekers/scripts/solve_shastry_sutherland_spin_axis_reduced_mof.jl \
    --model "$SS_INPUT_POINT/model.mof.json" \
    --runmeta "$SS_INPUT_POINT/runmeta.toml" \
    --checksums "$SS_INPUT_POINT/SHA256SUMS" \
    --expected-gamma "$SS_EXPECTED_GAMMA" \
    --repository-root "$REPOSITORY_ROOT" \
    --output "$RUN_DIR/result.toml" \
    --time-limit-seconds "$SS_TIME_LIMIT_SECONDS" \
    --threads "${SLURM_CPUS_PER_TASK:-16}" \
    --audit-tolerance "$SS_AUDIT_TOLERANCE" \
    2>&1 | tee "$RUN_DIR/runner.log"
solver_exit="${PIPESTATUS[0]}"
set -e

printf '%s\n' "$solver_exit" > "$RUN_DIR/runner-exit-code.txt"
printf '%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$RUN_DIR/finished-at-utc.txt"
(
    cd "$RUN_DIR"
    sha256sum \
        result.toml \
        runner.log \
        input-runmeta.toml \
        input-SHA256SUMS \
        runner-commit.txt \
        git-status.txt \
        runner-exit-code.txt \
        finished-at-utc.txt > SHA256SUMS
)

echo "[ss-axis-solve] runner_exit=$solver_exit"
echo "[ss-axis-solve] finished=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
sync
exit "$solver_exit"
