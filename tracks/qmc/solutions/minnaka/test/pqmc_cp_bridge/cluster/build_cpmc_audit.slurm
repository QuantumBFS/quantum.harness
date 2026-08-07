#!/bin/bash
#SBATCH -J QH_CPMC_BUILD
#SBATCH --partition=batch
#SBATCH -N 1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=64
#SBATCH --time=00:05:00
#SBATCH --output=results/cluster_cpmc_build/slurm-%j.out
#SBATCH --error=results/cluster_cpmc_build/slurm-%j.err

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
result_root="${repo_root}/results/cluster_cpmc_build"
mkdir -p "${result_root}"

echo "CPMC_AUDIT_BUILD_START $(date --iso-8601=seconds)"
make --output-sync=target -j "${SLURM_CPUS_PER_TASK}" \
    -C test/cpmc_path_audit all test
sha256sum test/cpmc_path_audit/build/cpmc_audit \
    > "${result_root}/cpmc_audit.sha256"
echo "CPMC_AUDIT_BUILD_COMPLETE $(date --iso-8601=seconds)"
cat "${result_root}/cpmc_audit.sha256"
