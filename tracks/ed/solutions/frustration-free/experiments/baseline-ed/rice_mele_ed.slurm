#!/bin/bash
#SBATCH --job-name=rice-mele-ed-l6
#SBATCH --partition=xhacnormalb
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:05:00
#SBATCH --chdir=/work/home/mazhuijing/ed-project/tracks/ed/hubbard-pump
#SBATCH --output=/work/home/mazhuijing/ed-project/tracks/ed/hubbard-pump/results/rice-mele-ed-%j.out
#SBATCH --error=/work/home/mazhuijing/ed-project/tracks/ed/hubbard-pump/results/rice-mele-ed-%j.err

set -euo pipefail
module load anaconda3/2023.09
source /work/home/mazhuijing/ed-project/.venv/bin/activate
python3 run_rice_mele_ed.py
