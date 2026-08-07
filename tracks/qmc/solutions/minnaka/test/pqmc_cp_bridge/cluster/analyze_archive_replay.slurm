#!/bin/bash
#SBATCH -J QH_REPLAY_ANALYZE
#SBATCH --partition=batch
#SBATCH -N 1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=64
#SBATCH --time=00:10:00
#SBATCH --output=results/cluster_archive/replay-analyze-%j.out
#SBATCH --error=results/cluster_archive/replay-analyze-%j.err

set -eo pipefail
set +u
source /opt/software/intel_2023/oneapi/setvars.sh >/dev/null 2>&1
set -u
export MKL_DEBUG_CPU_TYPE=5
export MKL_ENABLE_INSTRUCTIONS=AVX2
export LD_PRELOAD=/home/mzlu/bin/libmkl_trick.so
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1

repo_root="${SLURM_SUBMIT_DIR}"
python=/opt/software/anaconda3/bin/python
archive_index="${repo_root}/archives/archive_index.json"
manifest="${repo_root}/replay/manifests/production_all.csv"
replay_root="${repo_root}/replay/production"
result_root="${repo_root}/results"

echo "PRODUCTION_REPLAY_ANALYSIS_START $(date --iso-8601=seconds)"
"${python}" -u test/pqmc_cp_bridge/scripts/verify_archive_replay.py \
    --archive-index "${archive_index}" \
    --sample-manifest "${manifest}" \
    --summary \
        "${replay_root}/replay_summary_s1.csv" \
        "${replay_root}/replay_summary_s5.csv" \
        "${replay_root}/replay_summary_s10.csv" \
    --output "${result_root}/replay_validation.json"
"${python}" -u test/pqmc_cp_bridge/scripts/analyze_prefix_risk.py \
    --summary "${replay_root}/replay_summary_s5.csv" \
    --prefix "${replay_root}/replay_prefix_s5.qhpfx" \
    --stability-validation "${result_root}/replay_validation.json" \
    --output "${result_root}/replay_strata.csv" \
    --contract-output "${result_root}/strata_contract.json" \
    --reference-output "${result_root}/prefix_reference.json"
"${python}" -u test/pqmc_cp_bridge/scripts/energy_decomposition.py \
    --strata "${result_root}/replay_strata.csv" \
    --split held-out \
    --output "${result_root}/energy_decomposition.json"
"${python}" -u test/pqmc_cp_bridge/scripts/select_full_traces.py \
    --strata "${result_root}/replay_strata.csv" \
    --archive-index "${archive_index}" \
    --fields-dir "${replay_root}/traces/fields" \
    --manifest-output "${repo_root}/replay/manifests/full_traces.csv" \
    --selection-output \
        "${repo_root}/replay/manifests/full_trace_selection.json"
"${python}" -u test/pqmc_cp_bridge/scripts/run_parallel_traces.py \
    --manifest "${repo_root}/replay/manifests/full_traces.csv" \
    --trial-manifest \
        "${repo_root}/test/pqmc_cp_bridge/assets/trials/trial_manifest.json" \
    --executable \
        "${repo_root}/test/cpmc_path_audit/build/cpmc_audit" \
    --output-dir "${replay_root}/traces" \
    --workers "${SLURM_CPUS_PER_TASK}" \
    --stabilize-every 5
echo "PRODUCTION_REPLAY_ANALYSIS_COMPLETE $(date --iso-8601=seconds)"
