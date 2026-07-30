#!/usr/bin/env bash
#SBATCH --job-name=ss-spin-irrep
#SBATCH --partition=kshcnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=20
#SBATCH --mem=16000M
#SBATCH --time=00:20:00
#SBATCH --output=tracks/polyopt/solutions/sdp-gap-seekers/results/_slurm/scnet-ss-full-state-spin-isotypic-probe-%j.out

set -euo pipefail

export LC_ALL=C
export LANG=C
export JULIA_NUM_THREADS="${SLURM_CPUS_PER_TASK:-20}"

readonly EXPECTED_ROOT="/public/home/sihhu/quantum-hackson/checkouts/ss-exact-reduction"
readonly JULIA_BIN="/public/home/sihhu/quantum-hackson/toolchains/julia-1.11.5/bin/julia"
readonly OUTPUT="tracks/polyopt/solutions/sdp-gap-seekers/results/ss-full-state-spin-isotypic-probe-scnet-20260729-r2.toml"

cd "${SLURM_SUBMIT_DIR:?SLURM_SUBMIT_DIR is required}"
[[ "$PWD" == "$EXPECTED_ROOT" ]] || {
    echo "unexpected checkout: $PWD" >&2
    exit 2
}
[[ ! -e "$OUTPUT" ]] || {
    echo "output already exists: $OUTPUT" >&2
    exit 2
}

printf 'commit=%s host=%s start=%s\n' \
    "$(git rev-parse HEAD)" \
    "$(hostname)" \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

/usr/bin/time -v "$JULIA_BIN" --startup-file=no \
    tracks/polyopt/solutions/sdp-gap-seekers/scripts/probe_shastry_full_state_spin_isotypic.jl \
    > "$OUTPUT"

printf 'finish=%s output=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    "$OUTPUT"
