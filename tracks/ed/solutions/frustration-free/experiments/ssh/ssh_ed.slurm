#!/bin/bash
#SBATCH --job-name=ssh-ed-l8
#SBATCH --partition=xhacnormalb
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:05:00
#SBATCH --output=results/ssh-ed-%j.out
#SBATCH --error=results/ssh-ed-%j.err

set -euo pipefail
module load anaconda3/2023.09
source /work/home/mazhuijing/ed-project/.venv/bin/activate
cd /work/home/mazhuijing/ed-project/tracks/ed/hubbard-pump
python3 run_ssh_ed.py
