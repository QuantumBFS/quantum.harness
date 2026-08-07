#!/bin/bash
#SBATCH -J QH_ALF_CAL
#SBATCH --partition=batch
#SBATCH -N 1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=128
#SBATCH --time=00:10:00
#SBATCH --output=results/cluster_calibration_bin128_nwrap5/slurm-%j.out
#SBATCH --error=results/cluster_calibration_bin128_nwrap5/slurm-%j.err

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
run_root="${repo_root}/runs/alf_projection_bin128_nwrap5"
result_root="${repo_root}/results/cluster_calibration_bin128_nwrap5"

if [[ ! -x "${binary}" ]]; then
    echo "Missing serial ALF binary: ${binary}" >&2
    exit 2
fi

mkdir -p "${run_root}" "${result_root}"
echo "CALIBRATION_START $(date --iso-8601=seconds)"
echo "NODE=${SLURM_JOB_NODELIST} CPUS=${SLURM_CPUS_PER_TASK}"

python3 -u test/pqmc_cp_bridge/scripts/calibrate_projection.py \
    --run-root "${run_root}" \
    --results-root "${result_root}" \
    --executable "${binary}" \
    --trial-assets test/pqmc_cp_bridge/assets/trials \
    --master-seed 900090 \
    --chains "${SLURM_CPUS_PER_TASK}" \
    --initial-nbin 21 \
    --max-nbin 21 \
    --max-new-batches 1 \
    --nwrap 5 \
    --sweeps-per-bin 150 \
    --direct

echo "CALIBRATION_COMPLETE $(date --iso-8601=seconds)"
