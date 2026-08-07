#!/bin/bash
#SBATCH -J QH_ALF_PILOT
#SBATCH --partition=batch
#SBATCH -N 1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=64
#SBATCH --array=0-1
#SBATCH --time=00:10:00
#SBATCH --output=results/cluster_archive/pilot-%A_%a.out
#SBATCH --error=results/cluster_archive/pilot-%A_%a.err

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
ensembles=(II TI)
ensemble="${ensembles[${SLURM_ARRAY_TASK_ID}]}"

mkdir -p results/cluster_archive
echo "ARCHIVE_PILOT_START ensemble=${ensemble} $(date --iso-8601=seconds)"
echo "NODE=${SLURM_JOB_NODELIST} CPUS=${SLURM_CPUS_PER_TASK}"

python3 -u test/pqmc_cp_bridge/scripts/run_archive_pilot.py \
    --selected-projection "${selected}" \
    --executable "${binary}" \
    --run-root "${repo_root}/runs/archive_pilot" \
    --archive-root "${repo_root}/archives" \
    --ensemble "${ensemble}" \
    --direct

echo "ARCHIVE_PILOT_COMPLETE ensemble=${ensemble} $(date --iso-8601=seconds)"
