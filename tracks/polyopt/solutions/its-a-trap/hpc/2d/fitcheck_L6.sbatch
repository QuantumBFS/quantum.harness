#!/bin/bash
#SBATCH --job-name=c2d-fit
#SBATCH --partition=xhacnormalb
#SBATCH --cpus-per-task=1
#SBATCH --time=00:10:00
#SBATCH --output=slurm-2d-%j.out
# Fit-check: reads the L6 row; exit code IS the verdict for releasing L8.
set -u
cd "$HOME/qh-method"
export PATH="$HOME/julia/bin:$PATH"
julia tracks/polyopt/solutions/its-a-trap/hpc/2d/check_row.jl \
  "tracks/polyopt/results/${RUN_NAME:?}/cell_c2d_L6/results.csv" fitcheck
