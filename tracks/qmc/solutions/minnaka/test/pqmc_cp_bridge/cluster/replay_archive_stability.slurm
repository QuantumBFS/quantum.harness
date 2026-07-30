#!/bin/bash
#SBATCH -J QH_REPLAY_STAB
#SBATCH --partition=batch
#SBATCH -N 1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=64
#SBATCH --time=00:10:00
#SBATCH --output=results/cluster_archive/replay-stability-%j.out
#SBATCH --error=results/cluster_archive/replay-stability-%j.err

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
archive_index="${repo_root}/archives/pilot/archive_index.json"
sample_manifest="${repo_root}/replay/manifests/pilot_all.csv"
replay_root="${repo_root}/replay/pilot"

echo "REPLAY_STABILITY_START $(date --iso-8601=seconds)"
test -f "${replay_root}/replay_summary_s5.csv"
"${python}" -u test/pqmc_cp_bridge/scripts/run_parallel_replay.py \
    --archive-index "${archive_index}" \
    --sample-manifest "${sample_manifest}" \
    --selected-projection \
        "${repo_root}/results/cluster_calibration_bin128_nwrap5/selected_projection.json" \
    --executable "${repo_root}/test/cpmc_path_audit/build/cpmc_audit" \
    --output-dir "${replay_root}" \
    --stabilize-every 1 \
    --workers "${SLURM_CPUS_PER_TASK}"
status=0
"${python}" -u test/pqmc_cp_bridge/scripts/verify_archive_replay.py \
    --archive-index "${archive_index}" \
    --sample-manifest "${sample_manifest}" \
    --summary \
        "${replay_root}/replay_summary_s5.csv" \
        "${replay_root}/replay_summary_s1.csv" \
    --output "${repo_root}/results/pilot_replay_stability.json" \
    --failure-manifest \
        "${repo_root}/replay/manifests/pilot_replay_stability_failures.csv" \
    || status=$?
echo "REPLAY_STABILITY_COMPLETE status=${status} $(date --iso-8601=seconds)"
exit "${status}"
