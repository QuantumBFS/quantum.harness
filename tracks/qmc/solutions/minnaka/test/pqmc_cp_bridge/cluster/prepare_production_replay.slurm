#!/bin/bash
#SBATCH -J QH_REPLAY_SELECT
#SBATCH --partition=batch
#SBATCH -N 1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:05:00
#SBATCH --output=results/cluster_archive/replay-select-%j.out
#SBATCH --error=results/cluster_archive/replay-select-%j.err

set -eo pipefail
repo_root="${SLURM_SUBMIT_DIR}"

echo "PRODUCTION_REPLAY_SELECT_START $(date --iso-8601=seconds)"
python3 -u test/pqmc_cp_bridge/scripts/select_replay_samples.py \
    --archive-index "${repo_root}/archives/archive_index.json" \
    --output "${repo_root}/replay/manifests/production_all.csv" \
    --all
echo "PRODUCTION_REPLAY_SELECT_COMPLETE $(date --iso-8601=seconds)"
