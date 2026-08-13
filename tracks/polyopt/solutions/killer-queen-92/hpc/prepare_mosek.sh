#!/bin/bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
SOLUTION_DIR=${ISSUE92_SOLUTION_DIR:-"$(cd -- "$SCRIPT_DIR/.." && pwd)"}
JULIA_BIN=${JULIA_BIN:-"$HOME/.juliaup/bin/julia"}

export JULIA_DEPOT_PATH=${JULIA_DEPOT_PATH:-"$SOLUTION_DIR/.raw/julia-depot:$HOME/.julia"}
export JULIA_PKG_OFFLINE=true
module unload compiler/devtoolset/7.3.1
module load compiler/gcc/12.2.0

MOSEK_PACKAGE_DIR=$(find "$SOLUTION_DIR/.raw/julia-depot/packages/Mosek" \
    -mindepth 1 -maxdepth 1 -type d -print -quit)
[[ -n "$MOSEK_PACKAGE_DIR" ]] || { echo "staged Mosek.jl package not found" >&2; exit 1; }
MOSEK_VERSION=$(tr -d '[:space:]' < "$MOSEK_PACKAGE_DIR/MOSEKVER")
export MOSEKBINDIR="$MOSEK_PACKAGE_DIR/deps/src/mosek/$MOSEK_VERSION/tools/platform/linux64x86/bin"
[[ -x "$MOSEKBINDIR/mosek" ]] || { echo "staged Mosek executable not found in $MOSEKBINDIR" >&2; exit 1; }

cd "$SOLUTION_DIR"
echo "issue92 Mosek relocation: host=$(hostname) bindir=$MOSEKBINDIR"
"$JULIA_BIN" --startup-file=no --project=julia -e \
    'using Pkg; Pkg.build("Mosek"); using MosekTools; println("MosekTools import: PASS")'
