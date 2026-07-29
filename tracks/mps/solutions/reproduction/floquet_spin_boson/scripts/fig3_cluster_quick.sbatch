#!/usr/bin/env bash
#SBATCH --job-name=floim-fig3q
#SBATCH --account=giggleliu
#SBATCH --output=results/20260729-floquet-fig3-quick/slurm-%j.out
#SBATCH --error=results/20260729-floquet-fig3-quick/slurm-%j.err
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=8G
#SBATCH --time=00:30:00
#SBATCH --partition=xhacnormalb

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../../../../../.." && pwd)"
project_dir="${repo_root}/tracks/mps/solutions/reproduction/floquet_spin_boson"
result_dir="${repo_root}/results/20260729-floquet-fig3-quick"
reference_dir="${result_dir}/references/fig_3"

mkdir -p "${result_dir}"
cd "${project_dir}"

export OPENBLAS_NUM_THREADS=1
export JULIA_NUM_THREADS="${SLURM_CPUS_PER_TASK:-8}"

source_fingerprint="$(
    find src -maxdepth 1 -type f -name '*.jl' -print0 |
        sort -z |
        xargs -0 sha256sum |
        sha256sum |
        cut -d' ' -f1
)"
printf 'Fig. 3 stable quick start: source=%s threads=%s host=%s\n' \
    "${source_fingerprint}" "${JULIA_NUM_THREADS}" "$(hostname)"
printf 'Setup: Omega=1 S=sigma_z alpha=0.05 omega_c=2.5 epsilon_d=1 T=0 transversal_omega_d=1 dt_target=pi/6 tol=1e-7 n_c=1024 chi_cap=128 lag=1024\n'

julia --threads="${JULIA_NUM_THREADS}" --project=envs/current \
    scripts/reproduce_fig3.jl \
    --parallel phases \
    --resume \
    --reference-dir "${reference_dir}" \
    configs/fig3_cluster_quick.toml \
    "${result_dir}/fig3"

printf 'Fig. 3 stable quick finished\n'
