#!/bin/bash
#SBATCH -J QH_ALF_PROD
#SBATCH --partition=batch
#SBATCH -N 1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=128
#SBATCH --array=0-1
#SBATCH --time=00:10:00
#SBATCH --output=results/cluster_archive/production-%A_%a.out
#SBATCH --error=results/cluster_archive/production-%A_%a.err

set -eo pipefail
set +u
source /opt/software/intel_2023/oneapi/setvars.sh >/dev/null 2>&1
set -u
export MKL_DEBUG_CPU_TYPE=5
export MKL_ENABLE_INSTRUCTIONS=AVX2
export LD_PRELOAD=/home/mzlu/bin/libmkl_trick.so
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export I_MPI_PIN=0

repo_root="${SLURM_SUBMIT_DIR}"
binary="${repo_root}/test/alf_hirsch_binary/run/cluster_serial_green/bin/ALF.serial.out"
selected="${repo_root}/results/cluster_calibration_bin128_nwrap5/selected_projection.json"
stride="${repo_root}/results/archive_stride.json"
target_records="${TARGET_RECORDS_PER_ENSEMBLE:-1024}"
chains="${ARCHIVE_CHAINS:-128}"
ensembles=(II TI)
ensemble="${ensembles[${SLURM_ARRAY_TASK_ID}]}"

mkdir -p results/cluster_archive
echo "ARCHIVE_PRODUCTION_START ensemble=${ensemble} target=${target_records} chains=${chains} $(date --iso-8601=seconds)"
echo "NODE=${SLURM_JOB_NODELIST} CPUS=${SLURM_CPUS_PER_TASK}"

python3 -u test/pqmc_cp_bridge/scripts/run_archive_production.py \
    --selected-projection "${selected}" \
    --stride-contract "${stride}" \
    --target-records-per-ensemble "${target_records}" \
    --chains "${chains}" \
    --executable "${binary}" \
    --run-root "${repo_root}/runs/archive_production" \
    --archive-root "${repo_root}/archives" \
    --ensemble "${ensemble}" \
    --max-sweeps-per-job 4500 \
    --direct

echo "ARCHIVE_PRODUCTION_COMPLETE ensemble=${ensemble} $(date --iso-8601=seconds)"
