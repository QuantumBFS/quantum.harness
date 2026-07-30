#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
executable="${ALF_EXECUTABLE:-${project_root}/run/binary/bin/ALF.binary.out}"
production_root="${project_root}/run/binary/production"
physical_cpus=(0 2 4 6 8 10)

if [[ ! -x "${executable}" ]]; then
    echo "Missing binary-Hirsch executable: ${executable}" >&2
    exit 1
fi

/usr/bin/python3 "${project_root}/scripts/prepare_inputs.py" --mode production
set +u
source /opt/intel/oneapi/setvars.sh >/dev/null 2>&1
set -u
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export I_MPI_PIN=0

start_epoch="$(date +%s)"
pids=()
for chain in 0 1 2 3 4 5; do
    (
        cd "${production_root}/chain_${chain}"
        /usr/bin/time -f $'WALL_SECONDS=%e\nMAX_RSS_KB=%M' \
            taskset -c "${physical_cpus[chain]}" \
            mpirun -np 1 "${executable}" > run.log 2>&1
    ) &
    pids+=("$!")
done

while true; do
    running=0
    for pid in "${pids[@]}"; do
        if kill -0 "${pid}" 2>/dev/null; then
            running=$((running + 1))
        fi
    done
    complete_bins=0
    for chain in 0 1 2 3 4 5; do
        file="${production_root}/chain_${chain}/Ener_scal"
        if [[ -f "${file}" ]]; then
            lines="$(wc -l < "${file}")"
            complete_bins=$((complete_bins + lines))
        fi
    done
    elapsed="$(($(date +%s) - start_epoch))"
    echo "progress: ${complete_bins}/42 bins, ${running}/6 chains running, ${elapsed}s"
    if [[ "${running}" -eq 0 ]]; then
        break
    fi
    sleep 20
done

status=0
for pid in "${pids[@]}"; do
    if ! wait "${pid}"; then
        status=1
    fi
done
end_epoch="$(date +%s)"
wall_seconds="$((end_epoch - start_epoch))"
echo "WALL_SECONDS=${wall_seconds}" > "${production_root}/production.master.log"
echo "EXIT_STATUS=${status}" >> "${production_root}/production.master.log"
exit "${status}"
