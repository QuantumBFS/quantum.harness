#!/bin/bash
set -euo pipefail

SOLUTION_DIR=${ISSUE92_SOLUTION_DIR:-"$HOME/quantum.harness/tracks/polyopt/solutions/issue92-bose-hubbard-hyperbolic"}
JULIA_BIN=${JULIA_BIN:-"$HOME/.juliaup/bin/julia"}

export JULIA_DEPOT_PATH=${JULIA_DEPOT_PATH:-"$SOLUTION_DIR/.raw/julia-depot:$HOME/.julia"}
export JULIA_NUM_THREADS=${JULIA_NUM_THREADS:-${SLURM_CPUS_PER_TASK:-1}}
export JULIA_PKG_SERVER=${JULIA_PKG_SERVER:-"https://mirrors.nju.edu.cn/julia"}
export JULIA_PKG_OFFLINE=${JULIA_PKG_OFFLINE:-true}
export OPENBLAS_NUM_THREADS=${OPENBLAS_NUM_THREADS:-${SLURM_CPUS_PER_TASK:-1}}

cd "$SOLUTION_DIR"

echo "issue92 interactive test: host=$(hostname) cpus=${SLURM_CPUS_PER_TASK:-unset} julia_threads=$JULIA_NUM_THREADS"
echo "issue92 interactive test: instantiate + precompile hierarchy/Clarabel path"
"$JULIA_BIN" --startup-file=no --project=julia -e \
    'using Pkg; Pkg.instantiate(;update_registry=false,allow_autoprecomp=false); using QuantumGapHierarchy'

echo "issue92 interactive test: Julia regression suite"
"$JULIA_BIN" --startup-file=no --project=julia julia/test/runtests.jl

if [[ ${ISSUE92_RUN_ATOMIC_CERTIFICATE:-0} == 1 ]]; then
    echo "issue92 interactive test: exact-projected atomic exclusion"
    "$JULIA_BIN" --startup-file=no --project=julia \
        julia/scripts/check_atomic_certificate.jl \
        results/atomic/julia-hierarchy-certificate.json
fi

echo "issue92 interactive test: PASS"
