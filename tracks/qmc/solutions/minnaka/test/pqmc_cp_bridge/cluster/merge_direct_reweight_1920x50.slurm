#!/bin/bash
#SBATCH --job-name=QH_DRW_MERGE
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:10:00
#SBATCH --output=direct_reweight_1920x50/logs/merge-%j.out
#SBATCH --error=direct_reweight_1920x50/logs/merge-%j.err

set -euo pipefail

repo_root="${SLURM_SUBMIT_DIR}"
production_root="${repo_root}/direct_reweight_1920x50"
python=/opt/software/anaconda3/bin/python

echo "DIRECT_REWEIGHT_MERGE_START $(date --iso-8601=seconds)"
"${python}" -u \
    test/pqmc_cp_bridge/scripts/merge_direct_reweight_replicas.py \
    --production-root "${production_root}" \
    --replicas 10 \
    --chains-per-replica 192 \
    --paths-per-chain 50 \
    --target-error 0.01
echo "DIRECT_REWEIGHT_MERGE_COMPLETE $(date --iso-8601=seconds)"
