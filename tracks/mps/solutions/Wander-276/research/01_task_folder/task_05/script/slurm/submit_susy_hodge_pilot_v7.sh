#!/bin/bash
set -euo pipefail

mkdir -p logs
ARRAY_JOB=$(sbatch --parsable --array=0-7%8 run_susy_hodge_pilot_v7_array.sbatch)

echo "response_and_null_array_job=${ARRAY_JOB}"
echo "N10/N12 outcomes are sequential-pilot data; eight workers cover 160 registered logical jobs"
echo "aggregate only after the complete array passes"
