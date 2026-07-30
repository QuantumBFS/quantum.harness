#!/usr/bin/env bash
#SBATCH --job-name=ss-l2d2-real-solve
#SBATCH --partition=xhacnormalb
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=64
#SBATCH --mem=240G
#SBATCH --time=12:00:00
#SBATCH --output=tracks/polyopt/solutions/sdp-gap-seekers/results/_slurm/xh5-ss-l2d2-real-solve-%j.out

set -euo pipefail

export LC_ALL=C
export LANG=C
export JULIA_NUM_THREADS="${SLURM_CPUS_PER_TASK:-64}"
export SS_MOSEK_THREADS="${SLURM_CPUS_PER_TASK:-64}"
export SS_MOSEK_TIME_LIMIT_SECONDS=28800
export SS_MOSEK_LOG_LEVEL=2

readonly EXPECTED_ROOT="${SS_EXPECTED_ROOT:-$HOME/quantum-hackson/challenge-88/bohr-agent/ss-exact-reduction}"
readonly JULIA_ROOT="$HOME/.julia/juliaup/julia-1.11.5+0.x64.linux.gnu"
readonly JULIA_BIN="$JULIA_ROOT/bin/julia"
readonly JULIA_PROJECT="$HOME/quantum-hackson/challenge-88/repo-cb725ac3/julia-env"
readonly MOSEK_BIN_DIR="$HOME/quantum-hackson/toolchains/mosek-11.2/mosek/11.2/tools/platform/linux64x86/bin"
readonly MOSEK_LICENSE="$HOME/mosek/mosek.lic"
readonly OUTPUT_DIR="tracks/polyopt/solutions/sdp-gap-seekers/results/ss-full-state-spin-isotypic-l2d2-g0p8-gamma2-solve-xh5-${SLURM_JOB_ID}"

cd "${SLURM_SUBMIT_DIR:?SLURM_SUBMIT_DIR is required}"
[[ "$PWD" == "$EXPECTED_ROOT" ]] || {
    echo "unexpected checkout: $PWD" >&2
    exit 2
}
[[ ! -e "$OUTPUT_DIR" ]] || {
    echo "output directory already exists: $OUTPUT_DIR" >&2
    exit 2
}

export PATH="$MOSEK_BIN_DIR:${PATH}"
export LD_LIBRARY_PATH="$MOSEK_BIN_DIR:$JULIA_ROOT/lib/julia:${LD_LIBRARY_PATH:-}"
export MOSEKLM_LICENSE_FILE="$MOSEK_LICENSE"

printf 'commit=%s\n' "$(git rev-parse HEAD)"
printf 'host=%s cpus=%s start=%s\n' \
    "$(hostname)" \
    "${SLURM_CPUS_PER_TASK:-unknown}" \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

/usr/bin/time -v -o "${OUTPUT_DIR}.process-time.txt" \
    "$JULIA_BIN" \
    --project="$JULIA_PROJECT" \
    --startup-file=no \
    tracks/polyopt/solutions/sdp-gap-seekers/scripts/build_shastry_full_state_spin_isotypic_mof.jl \
    --coupling 4/5 \
    --gamma 2 \
    --patch-level 2 \
    --mode solve \
    --output "$OUTPUT_DIR"

printf 'finish=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
