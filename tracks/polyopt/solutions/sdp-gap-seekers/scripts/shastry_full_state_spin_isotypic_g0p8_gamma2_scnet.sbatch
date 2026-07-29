#!/usr/bin/env bash
#SBATCH --job-name=ss-spiniso-g2
#SBATCH --partition=kshcnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=20
#SBATCH --mem=64000M
#SBATCH --time=01:20:00
#SBATCH --output=tracks/polyopt/solutions/sdp-gap-seekers/results/_slurm/scnet-ss-full-state-spin-isotypic-g0p8-gamma2-%j.out

set -euo pipefail

export LC_ALL=C
export LANG=C
export JULIA_NUM_THREADS="${SLURM_CPUS_PER_TASK:-20}"
export SS_MOSEK_SOLVE_FORM="${SS_MOSEK_SOLVE_FORM:-free}"
export SS_MOSEK_LOG_LEVEL="${SS_MOSEK_LOG_LEVEL:-1}"

readonly EXPECTED_ROOT="/public/home/sihhu/quantum-hackson/checkouts/ss-exact-reduction"
readonly JULIA_ROOT="/public/home/sihhu/quantum-hackson/toolchains/julia-1.11.5"
readonly JULIA_BIN="$JULIA_ROOT/bin/julia"
readonly JULIA_PROJECT="/public/home/sihhu/quantum-hackson/envs/ss-full-state"
readonly MOSEK_LICENSE="/public/home/sihhu/quantum-hackson/licenses/mosek.lic"
readonly MODEL_DIR="tracks/polyopt/solutions/sdp-gap-seekers/results/ss-full-state-spin-isotypic-g0p8-gamma2-mof-scnet-20260729-r2"
readonly SOLVE_DIR="tracks/polyopt/solutions/sdp-gap-seekers/results/ss-full-state-spin-isotypic-g0p8-gamma2-solve-scnet-20260729-r2"

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
[[ ! -e "$MODEL_DIR" ]] || {
    echo "model directory already exists: $MODEL_DIR" >&2
    exit 2
}
[[ ! -e "$SOLVE_DIR" ]] || {
    echo "solve directory already exists: $SOLVE_DIR" >&2
    exit 2
}

export LD_LIBRARY_PATH="$JULIA_ROOT/lib/julia:${LD_LIBRARY_PATH:-}"
export MOSEKLM_LICENSE_FILE="$MOSEK_LICENSE"

printf 'commit=%s\n' "$(git rev-parse HEAD)"
printf 'host=%s cpus=%s gamma=2 start=%s\n' \
    "$(hostname)" \
    "${SLURM_CPUS_PER_TASK:-unknown}" \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

/usr/bin/time -v -o "${MODEL_DIR}.process-time.txt" \
    "$JULIA_BIN" \
    --project="$JULIA_PROJECT" \
    --startup-file=no \
    tracks/polyopt/solutions/sdp-gap-seekers/scripts/build_shastry_full_state_spin_isotypic_mof.jl \
    --coupling 4/5 \
    --gamma 2 \
    --mode mof \
    --output "$MODEL_DIR"

(
    cd "$MODEL_DIR"
    sha256sum model.mof.json runmeta.toml > SHA256SUMS
)
mkdir "$SOLVE_DIR"

/usr/bin/time -v -o "$SOLVE_DIR/process-time.txt" \
    "$JULIA_BIN" \
    --project="$JULIA_PROJECT" \
    --startup-file=no \
    tracks/polyopt/solutions/sdp-gap-seekers/scripts/solve_shastry_full_state_spatial_mof.jl \
    --model "$MODEL_DIR/model.mof.json" \
    --runmeta "$MODEL_DIR/runmeta.toml" \
    --checksums "$MODEL_DIR/SHA256SUMS" \
    --expected-gamma 2 \
    --repository-root "$PWD" \
    --output "$SOLVE_DIR/result.toml" \
    --time-limit-seconds 3600 \
    --threads "${SLURM_CPUS_PER_TASK:-20}" \
    --audit-tolerance 1e-7

(
    cd "$SOLVE_DIR"
    sha256sum process-time.txt result.toml > SHA256SUMS
)
printf 'finish=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
