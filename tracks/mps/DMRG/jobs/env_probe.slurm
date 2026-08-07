#!/bin/bash
#SBATCH --job-name=challenge28-env-probe
#SBATCH --partition=qdagnormal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:02:00
#SBATCH --gres=gpu:A800:1
#SBATCH --output=env-probe-%j.out
#SBATCH --error=env-probe-%j.err

set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"

echo "hostname=$(hostname)"
echo "kernel=$(uname -srmo)"
echo "path=$PATH"
command -v python3 || true
command -v python || true
command -v apptainer || true
command -v singularity || true
command -v conda || true
command -v modulecmd || true
nvidia-smi --query-gpu=name,driver_version --format=csv,noheader || true
/usr/bin/modulecmd bash avail 2>&1 | head -n 120 || true
for root in /public /share /opt /usr/local; do
  if test -d "$root"; then
    find "$root" -maxdepth 4 -type f \
      \( -name 'python3' -o -name 'python3.*' -o -name 'apptainer' -o -name 'singularity' \) \
      -perm -u+x 2>/dev/null | head -n 80
  fi
done
