#!/usr/bin/env bash
#SBATCH --job-name=floim-fig3q
#SBATCH --account=giggleliu
#SBATCH --output=results/20260729-floquet-fig3-quick/slurm-%j.out
#SBATCH --error=results/20260729-floquet-fig3-quick/slurm-%j.err
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=04:00:00
#SBATCH --partition=xhacnormalb

set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
project_dir="${repo_root}/tracks/mps/solutions/reproduction/floquet_spin_boson"
result_dir="${repo_root}/results/20260729-floquet-fig3-quick"
reference_dir="${result_dir}/references/fig_3"

mkdir -p "${result_dir}"
cd "${project_dir}"

export OPENBLAS_NUM_THREADS=1
export JULIA_NUM_THREADS="${SLURM_CPUS_PER_TASK:-16}"

printf 'Fig. 3 stable quick start: commit=%s threads=%s host=%s\n' \
    "$(git rev-parse --short HEAD)" "${JULIA_NUM_THREADS}" "$(hostname)"
printf 'Setup: Omega=1 S=sigma_z alpha=0.05 omega_c=2.5 epsilon_d=1 T=0 dt_target=pi/6 chi_cap=16 lag=16384\n'

julia --threads="${JULIA_NUM_THREADS}" --project=envs/current \
    scripts/reproduce_fig3.jl \
    --parallel phases \
    --resume \
    --reference-dir "${reference_dir}" \
    configs/fig3_cluster_quick.toml \
    "${result_dir}/fig3"

printf 'Fig. 3 stable quick finished\n'
