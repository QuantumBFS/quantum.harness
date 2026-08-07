#!/bin/bash
# Run ON THE SCNET LOGIN NODE. Compute nodes are offline AND the login node
# cannot reach install.julialang.org / download.mosek.com — julia comes from
# the Tsinghua mirror, the Mosek binary dir is rsynced from the laptop by
# ship.sh into ~/mosek/bin (build.jl honors MOSEKBINDIR). Idempotent.
set -eu
cd "$HOME/quantum.harness"
export JULIA_PKG_SERVER=https://mirrors.tuna.tsinghua.edu.cn/julia
export MOSEKBINDIR="$HOME/mosek/bin"

# 1. Julia 1.12.6 from the mirror (matches local provenance rows)
if [ ! -x "$HOME/julia/bin/julia" ]; then
  curl -fsSL -o /tmp/julia.tar.gz \
    https://mirrors.tuna.tsinghua.edu.cn/julia-releases/bin/linux/x64/1.12/julia-1.12.6-linux-x86_64.tar.gz
  tar -xzf /tmp/julia.tar.gz -C "$HOME"
  ln -sfn "$HOME/julia-1.12.6" "$HOME/julia"
  rm /tmp/julia.tar.gz
fi
export PATH="$HOME/julia/bin:$PATH"
# old system libstdc++ lacks GLIBCXX_3.4.21 needed by Mosek libtbb —
# julia ships a newer one (fix verified on login02, MOSEK 11.2.2 runs)
export LD_LIBRARY_PATH="$HOME/julia/lib/julia:$HOME/mosek/bin:${LD_LIBRARY_PATH:-}"
julia -e 'println(VERSION)'

# 2. Mosek licence + binaries must have been shipped
[ -f "$HOME/mosek/mosek.lic" ] || { echo "FATAL: ~/mosek/mosek.lic missing"; exit 1; }
[ -x "$HOME/mosek/bin/mosek" ]  || { echo "FATAL: ~/mosek/bin missing (ship.sh step 2)"; exit 1; }

# 3. Instantiate + build (MOSEKBINDIR skips the blocked mosek.com download)
julia --project=julia-env -e 'using Pkg; Pkg.instantiate(); Pkg.build("Mosek"); Pkg.precompile()'

# 4. Smoke: N=10 rdm=8 end-to-end (~1 min)
mkdir -p "$HOME/bootstrap_smoke"
cp tracks/polyopt/solutions/its-a-trap/hpc/refs/bethe_ref.json "$HOME/bootstrap_smoke/" || true
MAX_WALL_S=600 MAX_RSS_GB=8 MOSEK_THREADS=2 julia -t 2 --project=julia-env \
  tracks/polyopt/solutions/its-a-trap/overnight_harness.jl \
  "$HOME/bootstrap_smoke" smoke "s10:10:rdm=8,pso=0,lso=false"
tail -1 "$HOME/bootstrap_smoke/results.csv" | cut -c1-160
echo "BOOTSTRAP OK"
