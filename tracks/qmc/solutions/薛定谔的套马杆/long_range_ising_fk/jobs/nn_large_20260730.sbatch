#!/bin/bash
#SBATCH --job-name=ising_nn_big
#SBATCH --partition=xhacnormalb
#SBATCH --array=1-28%28
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=6G
#SBATCH --time=24:00:00
#SBATCH --output=tracks/qmc/solutions/薛定谔的套马杆/long_range_ising_fk/results/nn_large_20260730/logs/%A_%a.out
#SBATCH --error=tracks/qmc/solutions/薛定谔的套马杆/long_range_ising_fk/results/nn_large_20260730/logs/%A_%a.err
set -euo pipefail
cd "$HOME/quantum.harness"
mkdir -p "tracks/qmc/solutions/薛定谔的套马杆/long_range_ising_fk/results/nn_large_20260730/logs"
export HARNESS_RUN_SPEC="$PWD/tracks/qmc/solutions/薛定谔的套马杆/long_range_ising_fk/results/nn_large_20260730/run_spec.json"
export JULIA_BIN="$HOME/.local/bin/julia"
python "tracks/qmc/solutions/薛定谔的套马杆/long_range_ising_fk/scripts/nn_large_cell.py"
