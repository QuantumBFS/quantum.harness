#!/bin/bash
#SBATCH --job-name=ising_nn_smoke
#SBATCH --partition=xhacnormalb
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:10:00
#SBATCH --output=tracks/qmc/solutions/薛定谔的套马杆/long_range_ising_fk/results/nn_large_20260730/logs/smoke_%j.out
#SBATCH --error=tracks/qmc/solutions/薛定谔的套马杆/long_range_ising_fk/results/nn_large_20260730/logs/smoke_%j.err
set -euo pipefail
cd "$HOME/quantum.harness"
"$HOME/.local/bin/julia" --startup-file=no "tracks/qmc/solutions/薛定谔的套马杆/long_range_ising_fk/test/runtests.jl"
export NN_CELL_ID="smoke"
export NN_L="16"
export NN_SEED="20260730"
export NN_BETA="0.44068679350977147"
export NN_THERM="500"
export NN_MEAS="5000"
export NN_BLOCKS="20"
export RUN_ROOT="$PWD/tracks/qmc/solutions/薛定谔的套马杆/long_range_ising_fk/results/nn_large_20260730/smoke_check"
"$HOME/.local/bin/julia" --startup-file=no "tracks/qmc/solutions/薛定谔的套马杆/long_range_ising_fk/scripts/nn_large_point.jl"
