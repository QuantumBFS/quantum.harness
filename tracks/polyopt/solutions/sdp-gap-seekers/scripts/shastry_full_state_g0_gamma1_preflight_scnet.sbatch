#!/usr/bin/env bash
#SBATCH --job-name=ss-full-g0-g1
#SBATCH --partition=kshcnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=20
#SBATCH --mem=64G
#SBATCH --time=02:00:00
#SBATCH --output=tracks/polyopt/solutions/sdp-gap-seekers/results/_slurm/scnet-ss-full-state-g0-gamma1-%j.out

set -euo pipefail

export LC_ALL=C
export LANG=C
export JULIA_NUM_THREADS="${SLURM_CPUS_PER_TASK:-20}"

readonly EXPECTED_ROOT="$HOME/quantum-hackson/checkouts/ss-exact-reduction"
readonly JULIA_BIN="$HOME/quantum-hackson/toolchains/julia-1.11.5/bin/julia"
readonly JULIA_PROJECT="$HOME/quantum-hackson/envs/ss-full-state"
readonly RUN_DIR="tracks/polyopt/solutions/sdp-gap-seekers/results/ss-full-state-g0-gamma1-scnet-20260729-r1"
readonly LOG_DIR="tracks/polyopt/solutions/sdp-gap-seekers/results/_slurm"

cd "${SLURM_SUBMIT_DIR:?SLURM_SUBMIT_DIR is required}"
[[ "$PWD" == "$EXPECTED_ROOT" ]] || {
    echo "unexpected checkout: $PWD" >&2
    exit 2
}
[[ -x "$JULIA_BIN" ]] || {
    echo "Julia executable missing: $JULIA_BIN" >&2
    exit 2
}
[[ -d "$JULIA_PROJECT" ]] || {
    echo "Julia project missing: $JULIA_PROJECT" >&2
    exit 2
}

printf 'commit=%s\n' "$(git rev-parse HEAD)"
printf 'host=%s cpus=%s start=%s\n' \
    "$(hostname)" \
    "${SLURM_CPUS_PER_TASK:-unknown}" \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
flush_marker="$LOG_DIR/scnet-ss-full-state-g0-gamma1-${SLURM_JOB_ID:-unknown}.started"
printf 'job_id=%s\n' "${SLURM_JOB_ID:-unknown}" > "$flush_marker"

/usr/bin/time -v "$JULIA_BIN" \
    --project="$JULIA_PROJECT" \
    --startup-file=no \
    tracks/polyopt/solutions/sdp-gap-seekers/scripts/build_shastry_full_state_spatial_mof.jl \
    --coupling 0 \
    --gamma 1 \
    --mode preflight \
    --output "$RUN_DIR"

printf 'finish=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
