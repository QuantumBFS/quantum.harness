#!/usr/bin/env bash
#SBATCH --job-name=tw-phase0
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --output=/home/chentao/tesseract_20x_full_bosonchen/logs/tw-phase0-%j.out
#SBATCH --error=/home/chentao/tesseract_20x_full_bosonchen/logs/tw-phase0-%j.err

set -euo pipefail

root=/home/chentao/tesseract_20x_full_bosonchen
source_root="$root/baseline-audit-work"
run_root="$root/runs/tempered_worm_phase0"
binary="$source_root/bazel-bin/tempered_worm/phase0"

mkdir -p "$run_root"

case_name=${CASE_NAME:?CASE_NAME is required}
shots=${SHOTS:-10}
mc_seed=${MC_SEED:-20260730}

case "$case_name" in
  surface_d5_p2)
    circuit='testdata/surfacecodes/r=5,d=5,p=0.002,noise=si1000,c=surface_code_X,q=49,gates=cz.stim'
    sample_seed=2026073005
    beam=15
    pqlimit=200000
    num_det_orders=16
    ;;
  surface_d11)
    circuit='testdata/surfacecodes/r=11,d=11,p=0.001,noise=si1000,c=surface_code_X,q=241,gates=cz.stim'
    sample_seed=740425619
    beam=15
    pqlimit=200000
    num_det_orders=16
    ;;
  bbc_nlr10_d6)
    circuit='testdata/bivariatebicyclecodes_nlr10wb/r=6,d=6,p=0.001,noise=nlr10wb,c=bivariate_bicycle_X,k=12,q=144,iscolored=True,A_poly=x^3+y+y^2,B_poly=y^3+x+x^2.stim'
    sample_seed=732466215
    beam=15
    pqlimit=200000
    num_det_orders=16
    ;;
  bbc_nlr10_d18)
    circuit='testdata/bivariatebicyclecodes_nlr10wb/r=18,d=18,p=0.001,noise=nlr10wb,c=bivariate_bicycle_X,k=12,q=576,iscolored=True,A_poly=x^3+y^2+y^7,B_poly=y^3+x+x^2.stim'
    sample_seed=733304047
    beam=15
    pqlimit=200000
    num_det_orders=16
    ;;
  transcx_d13)
    circuit='testdata/surface_code_trans_cx_circuits/r=13,d=13,p=0.001,noise=si1000,c=surface_code_trans_cx_X,q=674,gates=cz.stim'
    sample_seed=742206012
    beam=20
    pqlimit=1000000
    num_det_orders=21
    ;;
  *)
    echo "Unknown CASE_NAME: $case_name" >&2
    exit 2
    ;;
esac

"$binary" \
  --circuit "$source_root/$circuit" \
  --out "$run_root/$case_name.json" \
  --shots "$shots" \
  --sample-seed "$sample_seed" \
  --mc-seed "$mc_seed" \
  --beam "$beam" \
  --pqlimit "$pqlimit" \
  --num-det-orders "$num_det_orders" \
  --seed-detector-order 2 \
  --seed-beam 2 \
  --cycle-attempts "${CYCLE_ATTEMPTS:-4000}" \
  --logical-seed-attempts "${LOGICAL_SEED_ATTEMPTS:-2000}" \
  --cycle-max-steps "${CYCLE_MAX_STEPS:-64}" \
  --cycle-max-moves "${CYCLE_MAX_MOVES:-20000}" \
  --algebraic-basis-sources "${ALGEBRAIC_BASIS_SOURCES:-0}" \
  --algebraic-max-moves "${ALGEBRAIC_MAX_MOVES:-4096}" \
  --algebraic-max-local-moves "${ALGEBRAIC_MAX_LOCAL_MOVES:-4096}" \
  --burn-in "${BURN_IN:-500}" \
  --measurements "${MEASUREMENTS:-2000}" \
  --moves-per-sweep "${MOVES_PER_SWEEP:-2}" \
  --bar-max-sectors "${BAR_MAX_SECTORS:-64}" \
  --bar-max-enumerated-sectors "${BAR_MAX_ENUMERATED_SECTORS:-65536}" \
  --bar-min-local-accepts "${BAR_MIN_LOCAL_ACCEPTS:-50}" \
  --bar-trigger-energy "${BAR_TRIGGER_ENERGY:-20}"
