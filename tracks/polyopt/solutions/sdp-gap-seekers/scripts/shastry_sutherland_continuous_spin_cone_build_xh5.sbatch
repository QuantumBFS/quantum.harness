#!/usr/bin/env bash
#SBATCH --job-name=ss-cont-cone-build
#SBATCH --partition=xhacnormalb
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=12G
#SBATCH --time=00:30:00
#SBATCH --output=tracks/polyopt/solutions/sdp-gap-seekers/results/slurm-%j.out

set -euo pipefail

: "${SS_RUN_ID:?set SS_RUN_ID to a unique build-record directory name}"
: "${SS_GAMMA0_OUTPUT:?set SS_GAMMA0_OUTPUT to a repository-relative directory}"
: "${SS_GAMMAHALF_OUTPUT:?set SS_GAMMAHALF_OUTPUT to a repository-relative directory}"

JULIA_BIN="${JULIA_BIN:-/work/home/sihhu/.julia/juliaup/julia-1.11.5+0.x64.linux.gnu/bin/julia}"
JULIA_PROJECT="${JULIA_PROJECT:-/work/home/sihhu/quantum-hackson/challenge-88/repo-cb725ac3/julia-env}"

REPOSITORY_ROOT="$(git rev-parse --show-toplevel)"
EXPECTED_ROOT="/work/home/sihhu/quantum-hackson/challenge-88/bohr-agent/ss-exact-reduction"
[[ "$REPOSITORY_ROOT" == "$EXPECTED_ROOT" ]] || {
    echo "[ss-continuous-spin-cone-build] refusing checkout: $REPOSITORY_ROOT" >&2
    exit 2
}
cd "$REPOSITORY_ROOT"

[[ -x "$JULIA_BIN" ]]
[[ -d "$JULIA_PROJECT" ]]
[[ ! -e "$SS_GAMMA0_OUTPUT" ]]
[[ ! -e "$SS_GAMMAHALF_OUTPUT" ]]

RUN_DIR="tracks/polyopt/solutions/sdp-gap-seekers/results/${SS_RUN_ID}"
[[ ! -e "$RUN_DIR" ]] || {
    echo "[ss-continuous-spin-cone-build] refusing existing run directory: $RUN_DIR" >&2
    exit 2
}
mkdir -p "$RUN_DIR"

export JULIA_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"

git rev-parse HEAD > "$RUN_DIR/builder-commit.txt"
git status --porcelain --untracked-files=all > "$RUN_DIR/git-status.txt"

echo "[ss-continuous-spin-cone-build] run_id=$SS_RUN_ID"
echo "[ss-continuous-spin-cone-build] job_id=${SLURM_JOB_ID:-missing}"
echo "[ss-continuous-spin-cone-build] host=$(hostname)"
echo "[ss-continuous-spin-cone-build] started=$(date -u +%Y-%m-%dT%H:%M:%SZ)"

builder=(
    "$JULIA_BIN"
    --project="$JULIA_PROJECT"
    --startup-file=no
    --history-file=no
    tracks/polyopt/solutions/sdp-gap-seekers/scripts/build_shastry_sutherland_continuous_spin_cone_reduced_mof.jl
)

set +e
/usr/bin/time -v -o "$RUN_DIR/gamma0-process-time.txt" \
    "${builder[@]}" \
    --gamma 0 \
    --output "$SS_GAMMA0_OUTPUT" \
    2>&1 | tee "$RUN_DIR/gamma0-build.log"
gamma0_exit="${PIPESTATUS[0]}"
set -e
printf '%s\n' "$gamma0_exit" > "$RUN_DIR/gamma0-exit-code.txt"

gammahalf_exit=99
if [[ "$gamma0_exit" -eq 0 ]]; then
    set +e
    /usr/bin/time -v -o "$RUN_DIR/gammahalf-process-time.txt" \
        "${builder[@]}" \
        --gamma 1/2 \
        --output "$SS_GAMMAHALF_OUTPUT" \
        2>&1 | tee "$RUN_DIR/gammahalf-build.log"
    gammahalf_exit="${PIPESTATUS[0]}"
    set -e
fi
printf '%s\n' "$gammahalf_exit" > "$RUN_DIR/gammahalf-exit-code.txt"
printf '%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$RUN_DIR/finished-at-utc.txt"

(
    cd "$RUN_DIR"
    checksum_files=(
        builder-commit.txt
        git-status.txt
        gamma0-build.log
        gamma0-process-time.txt
        gamma0-exit-code.txt
        gammahalf-exit-code.txt
        finished-at-utc.txt
    )
    [[ -f gammahalf-build.log ]] &&
        checksum_files+=(gammahalf-build.log)
    [[ -f gammahalf-process-time.txt ]] &&
        checksum_files+=(gammahalf-process-time.txt)
    sha256sum "${checksum_files[@]}" > SHA256SUMS
)

echo "[ss-continuous-spin-cone-build] gamma0_exit=$gamma0_exit"
echo "[ss-continuous-spin-cone-build] gammahalf_exit=$gammahalf_exit"
echo "[ss-continuous-spin-cone-build] finished=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
sync
[[ "$gamma0_exit" -eq 0 && "$gammahalf_exit" -eq 0 ]]
