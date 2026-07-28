#!/bin/bash
#SBATCH --job-name=c2d-L8
#SBATCH --partition=xhhgnormal
#SBATCH --cpus-per-task=32
#SBATCH --mem=220G
#SBATCH --time=12:00:00
#SBATCH --output=slurm-2d-%j.out
# 2D resource probe, L=8 (64 sites). Same named knob vector as L=6.
# Runs only afterok(fit-check) AND after a manual morning release.
set -u
cd "$HOME/qh-method"
export PATH="$HOME/julia/bin:$PATH"
# old system libstdc++ lacks GLIBCXX_3.4.21 needed by Mosek libtbb —
# julia ships a newer one (fix verified on login02, MOSEK 11.2.2 runs)
export LD_LIBRARY_PATH="$HOME/julia/lib/julia:$HOME/mosek/bin:${LD_LIBRARY_PATH:-}"
export MAX_WALL_S=41000 MAX_RSS_GB=200 MAX_PROC_SWAP_GB=2 MOSEK_THREADS=16
OUT="tracks/polyopt/results/${RUN_NAME:?}/cell_c2d_L8"
mkdir -p "$OUT"
julia -t 2 --project=julia-env \
  tracks/polyopt/solutions/its-a-trap/overnight_harness.jl "$OUT" t2d \
  "c2d_L8:8:model=heis2d,extra=4,rdm=10,pso=0,lso=false"
