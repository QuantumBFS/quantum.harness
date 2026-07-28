#!/bin/bash
# Run ON THE SCNET LOGIN NODE (internet available there; compute nodes are
# offline — everything network-touching must finish here). Idempotent.
set -eu
cd "$HOME/quantum.harness"

# 1. Julia via juliaup (pin 1.12.6 to match the local provenance rows)
if [ ! -x "$HOME/.juliaup/bin/julia" ]; then
  curl -fsSL https://install.julialang.org | sh -s -- --yes --default-channel 1.12.6
fi
export PATH="$HOME/.juliaup/bin:$PATH"
julia -e 'println(VERSION)'

# 2. Mosek licence must already be at ~/mosek/mosek.lic (shipped by ship.sh)
[ -f "$HOME/mosek/mosek.lic" ] || { echo "FATAL: ~/mosek/mosek.lic missing"; exit 1; }

# 3. Instantiate + precompile the project env (downloads registries,
#    artifacts incl. the Mosek binary — login node only)
julia --project=julia-env -e 'using Pkg; Pkg.instantiate(); Pkg.precompile()'

# 4. Smoke: load stack and solve the N=10 rdm=8 cell end-to-end (~1 min)
mkdir -p /tmp/bootstrap_smoke
cp tracks/polyopt/solutions/its-a-trap/hpc/refs/bethe_ref.json /tmp/bootstrap_smoke/ || true
MAX_WALL_S=600 MAX_RSS_GB=8 MOSEK_THREADS=2 julia -t 2 --project=julia-env \
  tracks/polyopt/solutions/its-a-trap/overnight_harness.jl \
  /tmp/bootstrap_smoke smoke "s10:10:rdm=8,pso=0,lso=false"
tail -2 /tmp/bootstrap_smoke/results.csv | cut -c1-160
echo "BOOTSTRAP OK"
