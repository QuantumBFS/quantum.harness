#!/bin/bash
#SBATCH --job-name=issue28-n3-replica
#SBATCH --output=slurm-%j.out

set -euo pipefail
: "${SLURM_SUBMIT_DIR:?Slurm must provide SLURM_SUBMIT_DIR}"

export HARNESS_RUN_SPEC="tracks/mps/DMRG/run_specs/issue28_n3_hpc_replica_20260729_01.json"
export HARNESS_CELL_INDEX=1

exec bash "$SLURM_SUBMIT_DIR/tracks/mps/DMRG/jobs/issue28_n3.slurm"
