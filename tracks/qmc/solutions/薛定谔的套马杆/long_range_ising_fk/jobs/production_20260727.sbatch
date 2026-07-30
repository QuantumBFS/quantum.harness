#!/bin/bash
#SBATCH --job-name=lrising_fk
#SBATCH --partition=xhacnormalb
#SBATCH --array=1-96%32
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=12:00:00
#SBATCH --output=tracks/qmc/solutions/薛定谔的套马杆/long_range_ising_fk/results/track_a_20260727/logs/%A_%a.out
#SBATCH --error=tracks/qmc/solutions/薛定谔的套马杆/long_range_ising_fk/results/track_a_20260727/logs/%A_%a.err
set -euo pipefail
cd "$HOME/quantum.harness"
SOLUTION_ROOT="$PWD/tracks/qmc/solutions/薛定谔的套马杆/long_range_ising_fk"
mkdir -p "$SOLUTION_ROOT/results/track_a_20260727/logs"
export RUN_ROOT="$SOLUTION_ROOT/results/track_a_20260727"
"$HOME/.local/bin/julia" --startup-file=no "$SOLUTION_ROOT/scripts/production_point.jl"
