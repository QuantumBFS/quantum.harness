#!/usr/bin/env bash
#SBATCH --job-name=ss-full-g0p8-solve
#SBATCH --partition=kshcnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=112G
#SBATCH --time=03:00:00
#SBATCH --array=0-1
#SBATCH --output=tracks/polyopt/solutions/sdp-gap-seekers/results/_slurm/scnet-ss-full-state-g0p8-solve-%A_%a.out

set -euo pipefail

export LC_ALL=C
export LANG=C
export JULIA_NUM_THREADS="${SLURM_CPUS_PER_TASK:-32}"

readonly EXPECTED_ROOT="/public/home/sihhu/quantum-hackson/checkouts/ss-exact-reduction"
readonly JULIA_ROOT="/public/home/sihhu/quantum-hackson/toolchains/julia-1.11.5"
readonly JULIA_BIN="$JULIA_ROOT/bin/julia"
readonly JULIA_PROJECT="/public/home/sihhu/quantum-hackson/envs/ss-full-state"
readonly MOSEK_LICENSE="/public/home/sihhu/quantum-hackson/licenses/mosek.lic"

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

readonly INPUT_DIR="tracks/polyopt/solutions/sdp-gap-seekers/results/ss-full-state-g0p8-${GAMMA_TAG}-mof-scnet-20260729-r1"
readonly SOLVE_DIR="tracks/polyopt/solutions/sdp-gap-seekers/results/ss-full-state-g0p8-${GAMMA_TAG}-solve-scnet-20260729-r1"

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
[[ -f "$MOSEK_LICENSE" ]] || {
    echo "Mosek license missing: $MOSEK_LICENSE" >&2
    exit 2
}
[[ -f "$INPUT_DIR/model.mof.json" ]] || {
    echo "MOF input missing: $INPUT_DIR/model.mof.json" >&2
    exit 2
}
[[ -f "$INPUT_DIR/runmeta.toml" ]] || {
    echo "runmeta input missing: $INPUT_DIR/runmeta.toml" >&2
    exit 2
}
[[ ! -e "$SOLVE_DIR" ]] || {
    echo "solve directory already exists: $SOLVE_DIR" >&2
    exit 2
}

export LD_LIBRARY_PATH="$JULIA_ROOT/lib/julia:${LD_LIBRARY_PATH:-}"
export MOSEKLM_LICENSE_FILE="$MOSEK_LICENSE"

(
    cd "$INPUT_DIR"
    sha256sum model.mof.json runmeta.toml > SHA256SUMS
)
mkdir -p "$SOLVE_DIR"

printf 'commit=%s\n' "$(git rev-parse HEAD)"
printf 'host=%s cpus=%s array_task=%s gamma=%s start=%s\n' \
    "$(hostname)" \
    "${SLURM_CPUS_PER_TASK:-unknown}" \
    "$SLURM_ARRAY_TASK_ID" \
    "$GAMMA" \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

/usr/bin/time -v -o "$SOLVE_DIR/process-time.txt" \
    "$JULIA_BIN" \
    --project="$JULIA_PROJECT" \
    --startup-file=no \
    tracks/polyopt/solutions/sdp-gap-seekers/scripts/solve_shastry_full_state_spatial_mof.jl \
    --model "$INPUT_DIR/model.mof.json" \
    --runmeta "$INPUT_DIR/runmeta.toml" \
    --checksums "$INPUT_DIR/SHA256SUMS" \
    --expected-gamma "$GAMMA" \
    --repository-root "$PWD" \
    --output "$SOLVE_DIR/result.toml" \
    --time-limit-seconds 9000 \
    --threads "${SLURM_CPUS_PER_TASK:-32}" \
    --audit-tolerance 1e-7

(
    cd "$SOLVE_DIR"
    sha256sum process-time.txt result.toml > SHA256SUMS
)
printf 'finish=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
