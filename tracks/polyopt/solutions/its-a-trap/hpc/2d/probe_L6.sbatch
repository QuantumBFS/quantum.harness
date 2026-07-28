#!/bin/bash
#SBATCH --job-name=c2d-L6
#SBATCH --partition=xhacnormalb
#SBATCH --cpus-per-task=32
#SBATCH --time=08:00:00
#SBATCH --output=slurm-2d-%j.out
# 2D resource probe, L=6 (36 sites). Knob vector (named in full, per the
# banned-phrase rule): d=4, extra=4, rdm=10, pso=0, lso=0, three_type=[1,1].
# pso/lso CHOSEN BY US = 0: every square-lattice example in the package
# passes pso=0, lso=0; the paper's exact 2D table config is indeterminable.
set -u
cd "$HOME/qh-method"
export PATH="$HOME/julia/bin:$PATH"
# old system libstdc++ lacks GLIBCXX_3.4.21 needed by Mosek libtbb —
# julia ships a newer one (fix verified on login02, MOSEK 11.2.2 runs)
export LD_LIBRARY_PATH="$HOME/julia/lib/julia:$HOME/mosek/bin:${LD_LIBRARY_PATH:-}"
export MAX_WALL_S=27000 MAX_RSS_GB=110 MAX_PROC_SWAP_GB=2 MOSEK_THREADS=16
OUT="tracks/polyopt/results/${RUN_NAME:?}/cell_c2d_L6"
mkdir -p "$OUT"
julia -t 2 -L tracks/polyopt/solutions/its-a-trap/hpc/2d/resort_patch.jl --project=julia-env \
  tracks/polyopt/solutions/its-a-trap/overnight_harness.jl "$OUT" t2d \
  "c2d_L6:6:model=heis2d,extra=4,rdm=10,pso=0,lso=false"
