#!/bin/bash
#SBATCH -J QH_NWRAP5
#SBATCH --partition=batch
#SBATCH -N 1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=128
#SBATCH --time=00:03:00
#SBATCH --output=results/cluster_nwrap_probe_green/slurm-%j.out
#SBATCH --error=results/cluster_nwrap_probe_green/slurm-%j.err

set -eo pipefail
set +u
source /opt/software/intel_2023/oneapi/setvars.sh >/dev/null 2>&1
set -u
export MKL_DEBUG_CPU_TYPE=5
export MKL_ENABLE_INSTRUCTIONS=AVX2
export LD_PRELOAD=/home/mzlu/bin/libmkl_trick.so
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export I_MPI_PIN=0

repo_root="${SLURM_SUBMIT_DIR}"
binary="${repo_root}/test/alf_hirsch_binary/run/cluster_serial_green/bin/ALF.serial.out"
run_root="${repo_root}/runs/nwrap5_probe_green"
result_root="${repo_root}/results/cluster_nwrap_probe_green"

mkdir -p "${run_root}" "${result_root}"
echo "NWRAP_PROBE_START $(date --iso-8601=seconds)"
python3 -u test/pqmc_cp_bridge/scripts/run_alf_batch.py \
    --ensemble TI \
    --theta 10 \
    --batch 0 \
    --nbin 2 \
    --nsweep 200 \
    --run-root "${run_root}" \
    --master-seed 5900090 \
    --executable "${binary}" \
    --trial-assets test/pqmc_cp_bridge/assets/trials \
    --chains 128 \
    --nwrap 5 \
    --direct

python3 -u - <<'PY'
from pathlib import Path
import re

root = Path("runs/nwrap5_probe_green/TI/theta_010/batch_000")
values = []
locations = []
for info in sorted(root.glob("chain_*/info")):
    match = re.search(
        r"Precision Green\s+Mean,\s*Max\s*:\s*\S+\s+(\S+)",
        info.read_text(),
    )
    if match is None:
        raise SystemExit(f"missing Green precision: {info}")
    values.append(float(match.group(1).replace("D", "E")))
    location = re.search(
        r"Precision Green Max Location "
        r"\(bin,sweep,direction,slice,i,j,flavor\)\s*:\s*"
        r"(\d+\s+\d+\s+-?\d+\s+\d+\s+\d+\s+\d+\s+\d+)",
        info.read_text(),
    )
    if location is None:
        raise SystemExit(f"missing Green maximum location: {info}")
    locations.append(location.group(1))
print(
    f"NWRAP_PROBE_RESULT chains={len(values)} "
    f"max_green_precision={max(values):.17g}",
    flush=True,
)
if max(values) > 1.0e-8:
    raise SystemExit("Nwrap=5 fails the Green precision gate")
print(f"NWRAP_PROBE_MAX_LOCATION {locations[values.index(max(values))]}")
PY
echo "NWRAP_PROBE_COMPLETE $(date --iso-8601=seconds)"
