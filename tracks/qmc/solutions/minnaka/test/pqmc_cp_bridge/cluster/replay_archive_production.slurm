#!/bin/bash
#SBATCH -J QH_REPLAY_PROD
#SBATCH --partition=batch
#SBATCH -N 1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=64
#SBATCH --array=0-2
#SBATCH --time=00:10:00
#SBATCH --output=results/cluster_archive/replay-production-%A_%a.out
#SBATCH --error=results/cluster_archive/replay-production-%A_%a.err

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
intervals=(1 5 10)
interval="${intervals[${SLURM_ARRAY_TASK_ID}]}"

echo "PRODUCTION_REPLAY_START stabilize=${interval} $(date --iso-8601=seconds)"
"${python}" -u test/pqmc_cp_bridge/scripts/run_parallel_replay.py \
    --archive-index "${repo_root}/archives/archive_index.json" \
    --sample-manifest "${repo_root}/replay/manifests/production_all.csv" \
    --selected-projection \
        "${repo_root}/results/cluster_calibration_bin128_nwrap5/selected_projection.json" \
    --executable "${repo_root}/test/cpmc_path_audit/build/cpmc_audit" \
    --output-dir "${repo_root}/replay/production" \
    --stabilize-every "${interval}" \
    --workers "${SLURM_CPUS_PER_TASK}"
echo "PRODUCTION_REPLAY_COMPLETE stabilize=${interval} $(date --iso-8601=seconds)"
