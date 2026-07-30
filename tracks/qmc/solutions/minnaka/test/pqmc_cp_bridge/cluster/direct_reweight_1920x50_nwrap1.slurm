#!/bin/bash
#SBATCH --job-name=QH_DRW_NW1
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=192
#SBATCH --array=0-9%10
#SBATCH --time=01:00:00
#SBATCH --output=direct_reweight_1920x50_nwrap1/logs/replica-%A_%a.out
#SBATCH --error=direct_reweight_1920x50_nwrap1/logs/replica-%A_%a.err

set -euo pipefail
set +u
source /opt/software/intel_2023/oneapi/setvars.sh >/dev/null 2>&1
set -u

export MKL_DEBUG_CPU_TYPE=5
export MKL_ENABLE_INSTRUCTIONS=AVX2
export LD_PRELOAD=/home/mzlu/bin/libmkl_trick.so
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export I_MPI_PIN=0

repo_root="${SLURM_SUBMIT_DIR}"
production_root="${repo_root}/direct_reweight_1920x50_nwrap1"
python=/opt/software/anaconda3/bin/python
alf="${repo_root}/test/alf_hirsch_binary/run/cluster_serial_green/bin/ALF.serial.out"
replay="${repo_root}/test/cpmc_path_audit/build/cpmc_audit"
selected="${repo_root}/results/cluster_calibration_bin128_nwrap5/selected_projection.json"

test -x "${alf}"
test -x "${replay}"
test -f "${selected}"

echo "DIRECT_REWEIGHT_NWRAP1_START id=${SLURM_ARRAY_TASK_ID} node=${SLURM_JOB_NODELIST} $(date --iso-8601=seconds)"
"${python}" -u test/pqmc_cp_bridge/scripts/run_direct_reweight_replica.py \
    --production-root "${production_root}" \
    --replica-id "${SLURM_ARRAY_TASK_ID}" \
    --alf-executable "${alf}" \
    --replay-executable "${replay}" \
    --selected-projection "${selected}" \
    --workers "${SLURM_CPUS_PER_TASK}" \
    --replicas 10 \
    --chains 192 \
    --paths-per-chain 50 \
    --burn-sweeps 2000 \
    --stride 239 \
    --master-seed 3700090 \
    --nwrap 1
echo "DIRECT_REWEIGHT_NWRAP1_COMPLETE id=${SLURM_ARRAY_TASK_ID} $(date --iso-8601=seconds)"
