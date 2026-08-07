#!/bin/bash
#SBATCH -J QH_PILOT_REPLAY
#SBATCH --partition=batch
#SBATCH -N 1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=64
#SBATCH --time=00:10:00
#SBATCH --output=results/cluster_archive/replay-pilot-%j.out
#SBATCH --error=results/cluster_archive/replay-pilot-%j.err

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
scores="${repo_root}/results/archive_pilot_scores.csv"
stride="${repo_root}/results/archive_stride.json"

echo "PILOT_REPLAY_START $(date --iso-8601=seconds)"
"${python}" -u test/pqmc_cp_bridge/scripts/select_replay_samples.py \
    --archive-index "${archive_index}" \
    --output "${sample_manifest}" \
    --all
"${python}" -u test/pqmc_cp_bridge/scripts/run_parallel_replay.py \
    --archive-index "${archive_index}" \
    --sample-manifest "${sample_manifest}" \
    --selected-projection \
        "${repo_root}/results/cluster_calibration_bin128_nwrap5/selected_projection.json" \
    --executable "${repo_root}/test/cpmc_path_audit/build/cpmc_audit" \
    --output-dir "${replay_root}" \
    --stabilize-every 5 \
    --workers "${SLURM_CPUS_PER_TASK}"
"${python}" -u test/pqmc_cp_bridge/scripts/verify_archive_replay.py \
    --archive-index "${archive_index}" \
    --sample-manifest "${sample_manifest}" \
    --summary "${replay_root}/replay_summary_s5.csv" \
    --output "${repo_root}/results/pilot_replay_validation.json" \
    --failure-manifest \
        "${repo_root}/replay/manifests/pilot_replay_failures.csv"
"${python}" -u test/pqmc_cp_bridge/scripts/make_pilot_scores.py \
    --archive-index "${archive_index}" \
    --replay-summary "${replay_root}/replay_summary_s5.csv" \
    --prefix "${replay_root}/replay_prefix_s5.qhpfx" \
    --output "${scores}"
"${python}" -u test/pqmc_cp_bridge/scripts/estimate_archive_stride.py \
    --scores "${scores}" \
    --output "${stride}"
echo "PILOT_REPLAY_COMPLETE $(date --iso-8601=seconds)"
cat "${stride}"
