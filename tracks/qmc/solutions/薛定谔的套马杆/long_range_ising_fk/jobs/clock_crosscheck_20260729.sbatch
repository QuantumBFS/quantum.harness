#!/bin/bash
#SBATCH --job-name=lrising_clock
#SBATCH --partition=xhacnormalb
#SBATCH --array=1-16%16
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=24:00:00
#SBATCH --output=tracks/qmc/solutions/薛定谔的套马杆/long_range_ising_fk/results/clock_production_20260729/logs/%A_%a.out
#SBATCH --error=tracks/qmc/solutions/薛定谔的套马杆/long_range_ising_fk/results/clock_production_20260729/logs/%A_%a.err
set -euo pipefail
cd "$HOME/quantum.harness"
SOLUTION_ROOT="$PWD/tracks/qmc/solutions/薛定谔的套马杆/long_range_ising_fk"
mkdir -p "$SOLUTION_ROOT/results/clock_production_20260729/logs"
export RUN_ROOT="${RUN_ROOT:-$SOLUTION_ROOT/results/clock_production_20260729}"
"$HOME/.local/bin/julia" --startup-file=no "$SOLUTION_ROOT/scripts/clock_point.jl"
