#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
executable="${ALF_EXECUTABLE:-${project_root}/run/binary/bin/ALF.binary.out}"
run_dir="${project_root}/run/binary/smoke"

if [[ ! -x "${executable}" ]]; then
    echo "Missing binary-Hirsch executable: ${executable}" >&2
    exit 1
fi

/usr/bin/python3 "${project_root}/scripts/prepare_inputs.py" --mode smoke
set +u
source /opt/intel/oneapi/setvars.sh >/dev/null 2>&1
set -u
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export I_MPI_PIN=1
export I_MPI_PIN_DOMAIN=core

cd "${run_dir}"
/usr/bin/time -f $'WALL_SECONDS=%e\nMAX_RSS_KB=%M' \
    mpirun -np 6 "${executable}" > run.log 2>&1
tail -n 2 run.log
