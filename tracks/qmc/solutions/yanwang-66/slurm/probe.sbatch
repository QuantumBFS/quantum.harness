#!/usr/bin/env bash
#SBATCH --job-name=q66-probe
#SBATCH --partition=dzagnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --gres=gpu:1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
#SBATCH --output=probe-%j.out
#SBATCH --error=probe-%j.err

set -euo pipefail

echo "timestamp_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "hostname=$(hostname)"
echo "slurm_job_id=${SLURM_JOB_ID:-unset}"
echo "slurm_partition=${SLURM_JOB_PARTITION:-unset}"
echo "submit_dir=${SLURM_SUBMIT_DIR:-unset}"
echo "workdir=$(pwd)"
echo "user=$(id -un)"
echo "kernel=$(uname -srmo)"
echo "cpu_count=$(getconf _NPROCESSORS_ONLN)"
echo "python3=$(command -v python3 || true)"
python3 --version 2>&1 || true
echo "git=$(command -v git || true)"
git --version 2>&1 || true
echo "container_tools"
for tool in apptainer singularity docker podman; do
    if command -v "${tool}" >/dev/null 2>&1; then
        "${tool}" --version 2>&1 | head -n 1
    else
        echo "${tool}=missing"
    fi
done
echo "module_list"
if command -v module >/dev/null 2>&1; then
    module -t list 2>&1 || true
else
    echo "module=missing"
fi
echo "gpu_visibility"
echo "CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-unset}"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>&1 || true
echo "filesystem"
df -h .
