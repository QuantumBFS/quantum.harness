#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
    echo "usage: run_rde_beta16_prepare.sh RUN_ROOT MATCH_ROOT" >&2
    exit 2
fi

run_root=$1
match_root=$2
run_environment="${run_root}/runenv"
julia_bin="/scratch-shared/wguo/workdir_tmp/102_pp_ttn_impl/runtime/julia-1.12.6/bin/julia"

(
    cd "${run_root}"
    sha256sum -c logs/run-config.sha256
    sha256sum -c logs/source-revisions.sha256
    sha256sum -c logs/source-lock-components.sha256
    sha256sum -c logs/source-lock.sha256
)
source "${run_root}/logs/run-config.env"

[[ -s "${match_root}/outputs/matched_cap.txt" ]] || {
    echo "fail-closed: matched_cap.txt does not exist in ${match_root}" >&2
    exit 1
}

if [[ -f "${run_root}/logs/depot-path.env" ]]; then
    source "${run_root}/logs/depot-path.env"
else
    export JULIA_DEPOT_PATH="${run_root}/depot"
fi
export JULIA_NUM_THREADS="${SLURM_CPUS_PER_TASK:-32}"
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export JULIA_PKG_OFFLINE=true
export GRAFT_RDE_MATCH_ROOT="${match_root}"

echo "RUN_CONFIG phase=full_preparation bootstrap=DirectKrylovBootstrap bootstrap_tau=${GRAFT_RDE_BOOTSTRAP_TAU} bootstrap_krylov_dim=${GRAFT_RDE_BOOTSTRAP_KRYLOV_DIM} bootstrap_gram_atol=${GRAFT_RDE_BOOTSTRAP_GRAM_ATOL} bootstrap_gram_rtol=${GRAFT_RDE_BOOTSTRAP_GRAM_RTOL} bootstrap_max_exact_bond=${GRAFT_RDE_BOOTSTRAP_MAX_EXACT_BOND} bootstrap_max_exact_payload=${GRAFT_RDE_BOOTSTRAP_MAX_EXACT_PAYLOAD} main_loop=${GRAFT_RDE_PREP_METHOD} prep_cap=${GRAFT_RDE_PREP_CAP} beta=${GRAFT_RDE_BETA} poles=${GRAFT_RDE_NPOLES} match_root=${match_root} residual_tolerance=${GRAFT_RDE_SOLVE_TOL} max_rounds=${GRAFT_RDE_MAX_ROUNDS} weight_atol=${GRAFT_RDE_WEIGHT_ATOL} weight_rtol=${GRAFT_RDE_WEIGHT_RTOL} enrichment_atol=${GRAFT_RDE_ENRICHMENT_ATOL} enrichment_rtol=${GRAFT_RDE_ENRICHMENT_RTOL}"
exec /usr/bin/time -v \
    "${julia_bin}" \
    --startup-file=no \
    --project="${run_environment}" \
    "${run_root}/harness/rde_beta16_prepare.jl" \
    "${run_root}" \
    "${match_root}"
