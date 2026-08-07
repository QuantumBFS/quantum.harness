#!/usr/bin/env bash
#SBATCH --job-name=q66-env-check
#SBATCH --partition=dzagnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --gres=gpu:1
#SBATCH --mem=4G
#SBATCH --time=00:10:00
#SBATCH --output=env-check-%j.out
#SBATCH --error=env-check-%j.err

set -euo pipefail

echo "timestamp_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "hostname=$(hostname)"
echo "module_avail_begin"
if command -v module >/dev/null 2>&1; then
    module -t avail 2>&1 || true
else
    echo "module=missing"
fi
echo "module_avail_end"

for tool in python python3 conda mamba micromamba docker; do
    printf '%s=' "${tool}"
    command -v "${tool}" || true
done

echo "docker_info_begin"
set +e
docker info 2>&1
docker_status=$?
set -e
echo "docker_status=${docker_status}"
echo "docker_info_end"

echo "anaconda_check_begin"
module load anaconda3/2023.09
echo "python3=$(command -v python3)"
python3 --version
python3 -m pip --version
echo "anaconda_check_end"
