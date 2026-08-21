#!/bin/bash
set -euo pipefail

project_root="${1:-/home/jhzhu/quantum.harness-haar}"
cd "$project_root"

mkdir -p .python-packages
python3 -m zipfile -e \
  numpy-2.5.1-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl \
  .python-packages
mv -f haar_mipt_slurm_cell.py scripts/haar_mipt_slurm_cell.py
