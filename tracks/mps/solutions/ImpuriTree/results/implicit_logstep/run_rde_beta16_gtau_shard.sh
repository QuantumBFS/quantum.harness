#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
    echo "usage: run_rde_beta16_gtau_shard.sh RUN_ROOT PREP_ROOT" >&2
    exit 2
fi

run_root=$1
prep_root=$2
run_environment="${run_root}/runenv"
julia_bin="/scratch-shared/wguo/workdir_tmp/102_pp_ttn_impl/runtime/julia-1.12.6/bin/julia"
worker_index=${SLURM_PROCID:?SLURM_PROCID is required}
worker_count=${SLURM_NTASKS:?SLURM_NTASKS is required}

(
    cd "${run_root}"
    sha256sum -c logs/run-config.sha256
    sha256sum -c logs/source-revisions.sha256
    sha256sum -c logs/source-lock-components.sha256
    sha256sum -c logs/source-lock.sha256
)
source "${run_root}/logs/run-config.env"

[[ "${worker_count}" -eq 8 ]] || {
    echo "Gtau fanout requires exactly 8 Slurm tasks; got ${worker_count}" >&2
    exit 1
}
[[ -s "${prep_root}/outputs/preparation-final.jld2" ]] || {
    echo "missing completed preparation checkpoint in ${prep_root}" >&2
    exit 1
}
: "${GRAFT_RDE_MATCH_ROOT:?GRAFT_RDE_MATCH_ROOT is required}"

if [[ -f "${run_root}/logs/depot-path.env" ]]; then
    source "${run_root}/logs/depot-path.env"
else
    export JULIA_DEPOT_PATH="${run_root}/depot"
fi
export JULIA_NUM_THREADS="${SLURM_CPUS_PER_TASK:-16}"
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export JULIA_PKG_OFFLINE=true

echo "RUN_CONFIG phase=gtau_fanout worker=${worker_index} workers=${worker_count} points=17 beta=${GRAFT_RDE_BETA} sign=Gtau_equals_minus_correlator preparation_bootstrap=DirectKrylovBootstrap preparation_bootstrap_tau=${GRAFT_RDE_BOOTSTRAP_TAU} branch_manifold_source=preparation_checkpoint_virtual_spaces branch_bootstrap=none branch_evolution=${GRAFT_RDE_PREP_METHOD} prep_cap=${GRAFT_RDE_PREP_CAP} residual_tolerance=${GRAFT_RDE_SOLVE_TOL} max_rounds=${GRAFT_RDE_MAX_ROUNDS} weight_atol=${GRAFT_RDE_WEIGHT_ATOL} weight_rtol=${GRAFT_RDE_WEIGHT_RTOL} enrichment_atol=${GRAFT_RDE_ENRICHMENT_ATOL} enrichment_rtol=${GRAFT_RDE_ENRICHMENT_RTOL}"
exec /usr/bin/time -v \
    "${julia_bin}" \
    --startup-file=no \
    --project="${run_environment}" \
    "${run_root}/harness/rde_beta16_gtau_shard.jl" \
    "${run_root}" \
    "${prep_root}" \
    "${worker_index}" \
    "${worker_count}"
