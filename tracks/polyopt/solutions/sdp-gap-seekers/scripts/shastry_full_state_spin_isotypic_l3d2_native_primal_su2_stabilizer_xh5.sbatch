#!/usr/bin/env bash
# Direct L=3 production route: exact rank-four SO(3) moment projection plus
# the exact nontrivial-character stabilizer cone split.
#SBATCH --job-name=ss-l3-su2-stab
#SBATCH --partition=xhacnormalb
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=128
#SBATCH --mem=480G
#SBATCH --time=20:00:00
#SBATCH --output=tracks/polyopt/solutions/sdp-gap-seekers/results/_slurm/xh5-ss-l3-native-primal-su2-stabilizer-%j.out

set -euo pipefail

export LC_ALL=C
export LANG=C
export JULIA_NUM_THREADS="${SLURM_CPUS_PER_TASK:-128}"
export SS_MOSEK_THREADS="${SLURM_CPUS_PER_TASK:-128}"
export SS_MOSEK_TIME_LIMIT_SECONDS=54000
export SS_MOSEK_LOG_LEVEL=2
export SS_AUDIT_TOLERANCE=1e-9
export SHASTRY_STREAM_ROW_BATCH="${SLURM_CPUS_PER_TASK:-128}"
export SHASTRY_SU2_RANK4_REDUCTION=1
export SHASTRY_STABILIZER_COEFFICIENT_TRUTH=1
export SHASTRY_STABILIZER_CONE_SPLIT=1

readonly EXPECTED_ROOT="${SS_EXPECTED_ROOT:-/work/home/sihhu/quantum-hackson/challenge-88/checkouts/ss-l3-su2-stabilizer}"
readonly EXPECTED_COMMIT="${SS_EXPECTED_COMMIT:?SS_EXPECTED_COMMIT is required}"
readonly JULIA_ROOT="/work/home/sihhu/.julia/juliaup/julia-1.11.5+0.x64.linux.gnu"
readonly JULIA_BIN="$JULIA_ROOT/bin/julia"
readonly JULIA_PROJECT="/work/home/sihhu/quantum-hackson/challenge-88/repo-cb725ac3/julia-env"
readonly MOSEK_BIN_DIR="/work/home/sihhu/quantum-hackson/toolchains/mosek-11.2/mosek/11.2/tools/platform/linux64x86/bin"
readonly MOSEK_LICENSE="/work/home/sihhu/mosek/mosek.lic"
readonly OUTPUT_DIR="tracks/polyopt/solutions/sdp-gap-seekers/results/ss-full-state-spin-isotypic-l3d2-g0p8-gamma2-native-primal-su2-stabilizer-xh5-${SLURM_JOB_ID}"

cd "${SLURM_SUBMIT_DIR:?SLURM_SUBMIT_DIR is required}"
[[ "$PWD" == "$EXPECTED_ROOT" ]] || {
    echo "unexpected checkout: $PWD" >&2
    exit 2
}
[[ "$(git rev-parse HEAD)" == "$EXPECTED_COMMIT" ]] || {
    echo "unexpected commit: $(git rev-parse HEAD)" >&2
    exit 2
}
[[ -z "$(git status --porcelain)" ]] || {
    echo "refusing dirty checkout" >&2
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
    --patch-level 3 \
    --mode native \
    --output "$OUTPUT_DIR"

printf 'finish=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
