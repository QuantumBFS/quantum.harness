#!/bin/bash
#SBATCH --job-name=issue92-mkl-smoke
#SBATCH --partition=wzacnormal03
#SBATCH --nodes=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=8G
#SBATCH --time=00:15:00
#SBATCH --output=results/slurm/issue92-mkl-smoke-%j.out
#SBATCH --error=results/slurm/issue92-mkl-smoke-%j.err

set -euo pipefail

SOLUTION_DIR=${SLURM_SUBMIT_DIR:?submit from the issue-92 solution directory}
cd "$SOLUTION_DIR"
mkdir -p results/slurm
module purge
module load compiler/intel/2021.3.0
export PATH="$HOME/.juliaup/bin:$PATH"
export JULIA_NUM_THREADS=${SLURM_CPUS_PER_TASK}
export MKL_NUM_THREADS=${SLURM_CPUS_PER_TASK}
export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK}
export JULIA_DEPOT_PATH="$SOLUTION_DIR/.raw/julia-depot:$HOME/.julia"
export JULIA_PKG_OFFLINE=true
export ISSUE92_CLARABEL_PROFILE=presentation-fast
export ISSUE92_CLARABEL_MAX_ITER=30
export ISSUE92_CLARABEL_TIME_LIMIT=60
export ISSUE92_CLARABEL_DIRECT_SOLVER=mkl
export ISSUE92_CLARABEL_MAX_THREADS=${SLURM_CPUS_PER_TASK}
export ISSUE92_SOLVE_PROGRESS=1

julia --project=julia -e '
    using QuantumGapHierarchy
    graph = read_graph_json("results/graphs/83-L1.json")
    spec = LevelSpec("83",1,1,1,:matrix,:complete,PRIMARY_SYMMETRY)
    template = build_level(spec,graph)
    record = solve_feasibility(template,ModelParams(0,1,1//2,0);solver=:clarabel)
    println("MKL_SMOKE classification=$(record.classification) raw=$(record.raw_status) solver=$(record.solver) runtime=$(record.runtime_seconds)")
    flush(stdout)
    record.classification == :FEASIBLE || error("MKL smoke did not pass independent feasibility checks")
'
