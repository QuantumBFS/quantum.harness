#!/usr/bin/env bash
#SBATCH --partition=xhacnormalb
#SBATCH --account=giggleliu
#SBATCH --nodes=1
#SBATCH --ntasks=1

set -euo pipefail
unset LC_ALL
export LANG=C

source /usr/share/Modules/init/bash
module purge
module load anaconda3/2023.09

ROOT=/work/share/giggleliu/cfys01/kharkov_burgers_20260729
PYTHON="$ROOT/env/tenpy-py311/bin/python"
SOURCE="$ROOT/source"

export PYTHONNOUSERSITE=1
cd "$SOURCE"
exec "$PYTHON" hpc/scnet/continue_convergence.py

