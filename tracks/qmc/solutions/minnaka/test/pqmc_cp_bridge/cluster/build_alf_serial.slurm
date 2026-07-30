#!/bin/bash
#SBATCH -J QH_ALF_BUILD
#SBATCH --partition=batch
#SBATCH -N 1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=64
#SBATCH --time=00:10:00
#SBATCH --output=results/cluster_build_green/slurm-%j.out
#SBATCH --error=results/cluster_build_green/slurm-%j.err

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
alf_root="${repo_root}/test/alf_hirsch_binary/ALF"
binary_root="${repo_root}/test/alf_hirsch_binary/run/cluster_serial_green/bin"
result_root="${repo_root}/results/cluster_build_green"

mkdir -p "${binary_root}" "${result_root}"
echo "BUILD_START $(date --iso-8601=seconds)"
echo "NODE=${SLURM_JOB_NODELIST} CPUS=${SLURM_CPUS_PER_TASK}"

cd "${alf_root}"
set +u
source ./configure.sh Intel noMPI STAB3 NO-INTERACTIVE
set -u
make program
cp -p Prog/ALF.out "${binary_root}/ALF.serial.out"
sha256sum "${binary_root}/ALF.serial.out" \
    > "${result_root}/ALF.serial.sha256"

echo "BUILD_COMPLETE $(date --iso-8601=seconds)"
cat "${result_root}/ALF.serial.sha256"
