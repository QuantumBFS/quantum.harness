#!/usr/bin/env bash
#SBATCH --job-name=ss-full-g0p8-mof
#SBATCH --partition=kshcnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=20
#SBATCH --mem=32G
#SBATCH --time=00:30:00
#SBATCH --array=0-1
#SBATCH --output=tracks/polyopt/solutions/sdp-gap-seekers/results/_slurm/scnet-ss-full-state-g0p8-mof-%A_%a.out

set -euo pipefail

export LC_ALL=C
export LANG=C
export JULIA_NUM_THREADS="${SLURM_CPUS_PER_TASK:-20}"

readonly EXPECTED_ROOT="/public/home/sihhu/quantum-hackson/checkouts/ss-exact-reduction"
readonly JULIA_BIN="/public/home/sihhu/quantum-hackson/toolchains/julia-1.11.5/bin/julia"
readonly JULIA_PROJECT="/public/home/sihhu/quantum-hackson/envs/ss-full-state"
readonly LOG_DIR="tracks/polyopt/solutions/sdp-gap-seekers/results/_slurm"

case "${SLURM_ARRAY_TASK_ID:?SLURM_ARRAY_TASK_ID is required}" in
    0)
        readonly GAMMA="0"
        readonly GAMMA_TAG="gamma0"
        ;;
    1)
        readonly GAMMA="1/2"
        readonly GAMMA_TAG="gamma0p5"
        ;;
    *)
        echo "unexpected array index: $SLURM_ARRAY_TASK_ID" >&2
        exit 2
        ;;
esac

readonly RUN_DIR="tracks/polyopt/solutions/sdp-gap-seekers/results/ss-full-state-g0p8-${GAMMA_TAG}-mof-scnet-20260729-r1"

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
[[ ! -e "$RUN_DIR" ]] || {
    echo "run directory already exists: $RUN_DIR" >&2
    exit 2
}

printf 'commit=%s\n' "$(git rev-parse HEAD)"
printf 'host=%s cpus=%s array_task=%s gamma=%s start=%s\n' \
    "$(hostname)" \
    "${SLURM_CPUS_PER_TASK:-unknown}" \
    "$SLURM_ARRAY_TASK_ID" \
    "$GAMMA" \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
flush_marker="$LOG_DIR/scnet-ss-full-state-g0p8-${GAMMA_TAG}-${SLURM_ARRAY_JOB_ID:-unknown}_${SLURM_ARRAY_TASK_ID}.started"
printf 'job_id=%s_%s\n' \
    "${SLURM_ARRAY_JOB_ID:-unknown}" \
    "$SLURM_ARRAY_TASK_ID" \
    > "$flush_marker"

/usr/bin/time -v "$JULIA_BIN" \
    --project="$JULIA_PROJECT" \
    --startup-file=no \
    tracks/polyopt/solutions/sdp-gap-seekers/scripts/build_shastry_full_state_spatial_mof.jl \
    --coupling 4/5 \
    --gamma "$GAMMA" \
    --mode mof \
    --output "$RUN_DIR"

printf 'finish=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
