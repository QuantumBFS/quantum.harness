#!/bin/bash
set -euo pipefail

mkdir -p logs
ARRAY_JOB=$(sbatch --parsable --array=0-15%8 run_susy_hodge_N14_v7_array.sbatch)
NULL_JOB=$(sbatch --parsable --dependency="afterok:${ARRAY_JOB}" --array=0-47%16 run_susy_hodge_N14_null_v7_array.sbatch)
SEAL_JOB=$(sbatch --parsable --dependency="afterok:${NULL_JOB}" seal_susy_hodge_N14_v7.sbatch)

echo "N14_response_array_job=${ARRAY_JOB}"
echo "N14_null_array_job=${NULL_JOB}"
echo "N14_prediction_seal_job=${SEAL_JOB}"
echo "workflow stops after the prediction hash is printed"
echo "opening outcome sidecars requires a separate, explicit command"
