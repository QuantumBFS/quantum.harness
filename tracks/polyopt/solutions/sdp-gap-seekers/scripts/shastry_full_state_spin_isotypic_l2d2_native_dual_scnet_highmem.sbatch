#!/usr/bin/env bash
# SCNet 22.05 does not honor the GRES-binding flag below from an SBATCH
# directive. Submit reproducibly from the repository root with:
#   sbatch --gres-flags=disable-binding tracks/polyopt/solutions/sdp-gap-seekers/scripts/shastry_full_state_spin_isotypic_l2d2_native_dual_scnet_highmem.sbatch
#SBATCH --job-name=ss-l2-native-dual-hm
#SBATCH --partition=ksagnormal01
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=256000M
#SBATCH --gres=gpu:1
#SBATCH --gres-flags=disable-binding
#SBATCH --time=12:00:00
#SBATCH --output=tracks/polyopt/solutions/sdp-gap-seekers/results/_slurm/scnet-ss-l2-native-dual-hm-%j.out

set -euo pipefail

export LC_ALL=C
export LANG=C
export JULIA_NUM_THREADS="${SLURM_CPUS_PER_TASK:-32}"
export SS_MOSEK_THREADS="${SLURM_CPUS_PER_TASK:-32}"
export SS_MOSEK_TIME_LIMIT_SECONDS=28800
export SS_MOSEK_LOG_LEVEL=2
export SS_AUDIT_TOLERANCE=1e-7
export SHASTRY_STREAM_ROW_BATCH="${SLURM_CPUS_PER_TASK:-32}"
export SHASTRY_CERTIFICATE_FINGERPRINT=1
export SS_EXPECTED_COEFFICIENT_MAP_SHA256="935aab36220ec3f0b2bfaa92ea7527463c9dc1a2d579014798e4fe5534b6b1b4"

readonly EXPECTED_ROOT="${SS_EXPECTED_ROOT:-$HOME/quantum-hackson/checkouts/ss-remote-dual-audit}"
readonly JULIA_ROOT="$HOME/quantum-hackson/toolchains/julia-1.11.5"
readonly JULIA_BIN="$JULIA_ROOT/bin/julia"
readonly JULIA_PROJECT="$HOME/quantum-hackson/envs/ss-full-state"
readonly MOSEK_LICENSE="$HOME/quantum-hackson/licenses/mosek.lic"
readonly OUTPUT_DIR="tracks/polyopt/solutions/sdp-gap-seekers/results/ss-full-state-spin-isotypic-l2d2-g0p8-gamma2-native-dual-scnet-hm-${SLURM_JOB_ID}"

cd "${SLURM_SUBMIT_DIR:?SLURM_SUBMIT_DIR is required}"
[[ "$PWD" == "$EXPECTED_ROOT" ]] || {
    echo "unexpected checkout: $PWD" >&2
    exit 2
}
[[ ! -e "$OUTPUT_DIR" ]] || {
    echo "output directory already exists: $OUTPUT_DIR" >&2
    exit 2
}

export LD_LIBRARY_PATH="$JULIA_ROOT/lib/julia:${LD_LIBRARY_PATH:-}"
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
    --mode certificate \
    --output "$OUTPUT_DIR"

printf 'finish=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
