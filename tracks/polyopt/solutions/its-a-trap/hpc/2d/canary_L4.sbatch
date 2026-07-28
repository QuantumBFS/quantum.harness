#!/bin/bash
#SBATCH --job-name=c2d-L4
#SBATCH --partition=xhacnormalb
#SBATCH --cpus-per-task=8
#SBATCH --time=02:00:00
#SBATCH --output=slurm-2d-%j.out
# 2D chain head: L=4 canary. Purpose: encoding / normalization / solve path.
# Knobs mirror the package's own square example (rdm=8, pso=0, lso=0,
# extra=0 — examples/ground_state.jl:36-37, 50-53); verdict = valid lower
# bound vs the well-known 4x4 torus ED value E0/N = -0.7017802 (Schulz et al.)
set -u
cd "$HOME/qh-method"
export PATH="$HOME/julia/bin:$PATH"
# old system libstdc++ lacks GLIBCXX_3.4.21 needed by Mosek libtbb —
# julia ships a newer one (fix verified on login02, MOSEK 11.2.2 runs)
export LD_LIBRARY_PATH="$HOME/julia/lib/julia:$HOME/mosek/bin:${LD_LIBRARY_PATH:-}"
export MAX_WALL_S=6000 MAX_RSS_GB=26 MAX_PROC_SWAP_GB=2 MOSEK_THREADS=4
OUT="tracks/polyopt/results/${RUN_NAME:?}/cell_c2d_L4"
mkdir -p "$OUT"
julia -t 2 --project=julia-env \
  tracks/polyopt/solutions/its-a-trap/overnight_harness.jl "$OUT" t2d \
  "c2d_L4:4:model=heis2d,extra=0,rdm=8,pso=0,lso=false"
rc=$?
echo "=== canary julia exit=$rc"
# verdict (compute nodes have no python3 — julia checker)
julia tracks/polyopt/solutions/its-a-trap/hpc/2d/check_row.jl "$OUT/results.csv" canary
