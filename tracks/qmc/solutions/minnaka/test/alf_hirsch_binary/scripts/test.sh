#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
executable="${ALF_EXECUTABLE:-${project_root}/run/binary/bin/ALF.binary.out}"

set +u
source /opt/intel/oneapi/setvars.sh >/dev/null 2>&1
set -u
export ALF_EXECUTABLE="${executable}"
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1
cd "${project_root}"
/usr/bin/python3 -m unittest discover -v -s tests -p 'test_*.py'
