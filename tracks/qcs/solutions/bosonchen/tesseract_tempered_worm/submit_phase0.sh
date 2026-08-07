#!/usr/bin/env bash
set -euo pipefail

source_root=/home/chentao/tesseract_20x_full_bosonchen/baseline-audit-work
script="$source_root/tempered_worm/phase0.slurm"
partition=${PARTITION:-bigmem}
shots=${SHOTS:-10}

submit() {
  local case_name=$1
  sbatch \
    --partition="$partition" \
    --export="ALL,CASE_NAME=$case_name,SHOTS=$shots,MC_SEED=20260730" \
    "$script"
}

submit surface_d11
submit bbc_nlr10_d18
submit transcx_d13
