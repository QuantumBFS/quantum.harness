#!/usr/bin/env bash
#SBATCH --job-name=tfim-hon-L28-pilot
#SBATCH --partition=xhacnormalb
#SBATCH --nodes=1
#SBATCH --ntasks=32
#SBATCH --cpus-per-task=1
#SBATCH --mem=64G
#SBATCH --time=01:00:00
#SBATCH --output=pilot-honeycomb-L28-%j.log

set -euo pipefail

PILOT_ROOT="${SLURM_SUBMIT_DIR:?SLURM_SUBMIT_DIR is required}"
ONLY_TEAM_ROOT="$PILOT_ROOT/tracks/qmc/solutions/Only-team"
CONFIG_PATH="$ONLY_TEAM_ROOT/configs/pilot-honeycomb-L28-h2p13250.toml"
OUTPUT_DIR="$PILOT_ROOT/tracks/qmc/results/Only-team/pilot-honeycomb-L28-h2p13250"
MPIEXECJL="$HOME/.julia/bin/mpiexecjl"
PYTHON3="/public/software/apps/anaconda3/2023.09/bin/python3"

export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export JULIA_NUM_THREADS=1

module purge

for required in \
    "$MPIEXECJL" \
    "$PYTHON3" \
    "$CONFIG_PATH" \
    "$ONLY_TEAM_ROOT/Project.toml" \
    "$ONLY_TEAM_ROOT/scripts/run.jl"
do
    [[ -f "$required" ]] || {
        printf 'missing required file: %s\n' "$required" >&2
        exit 2
    }
done

if [[ -e "$OUTPUT_DIR" ]]; then
    if [[ ! -d "$OUTPUT_DIR" ]] ||
       [[ -n "$(find "$OUTPUT_DIR" -mindepth 1 -print -quit)" ]]
    then
        printf 'refusing to overwrite output: %s\n' "$OUTPUT_DIR" >&2
        exit 2
    fi
fi

printf 'pilot_start job=%s host=%s ranks=32\n' \
    "${SLURM_JOB_ID:-unknown}" "$(hostname)"
printf 'setup lattice=honeycomb L=28 h=2.1325 beta=13.130128956623683 requested_dltau=0.013\n'
printf 'sampling nWarm=1000 NmBin=8 NSwep=500 nLocal=1 nWolff=5\n'
printf 'julia=%s\n' "$(julia --version)"

"$MPIEXECJL" --project="$ONLY_TEAM_ROOT" -n 32 \
    julia --project="$ONLY_TEAM_ROOT" \
    "$ONLY_TEAM_ROOT/scripts/run.jl" \
    "$CONFIG_PATH"

export OUTPUT_DIR
"$PYTHON3" - <<'PY'
import csv
import hashlib
import json
import math
import os
import tomllib
from pathlib import Path

output = Path(os.environ["OUTPUT_DIR"])
with (output / "bins.csv").open(newline="", encoding="utf-8") as stream:
    bins = list(csv.DictReader(stream))
if len(bins) != 8 or [int(row["bin"]) for row in bins] != list(range(1, 9)):
    raise SystemExit("pilot must contain eight consecutive bins")
for row in bins:
    values = [float(row[key]) for key in ("m2_bin", "m4_bin", "Q_bin")]
    if not all(math.isfinite(value) for value in values):
        raise SystemExit("pilot contains a nonfinite bin")

with (output / "metadata.toml").open("rb") as stream:
    metadata = tomllib.load(stream)
seeds = [int(seed) for seed in metadata["runtime"]["rank_seeds"]]
if len(seeds) != 32 or len(set(seeds)) != 32:
    raise SystemExit("pilot must contain 32 distinct rank seeds")

actual = metadata["actual_parameters"]
expected = {
    "lattice": "honeycomb",
    "NumL1": 28,
    "NumL2": 28,
    "NumNS": 1568,
    "J1": -1.0,
    "J2": 0.0,
    "hTrfd": 2.1325,
    "LTrot": 1012,
    "nLocal": 1,
    "nWolff": 5,
}
for key, value in expected.items():
    if actual[key] != value:
        raise SystemExit(f"metadata mismatch for {key}: {actual[key]!r}")
if not math.isclose(actual["BetaT"], 28 / 2.1325, rel_tol=0, abs_tol=1e-14):
    raise SystemExit("metadata BetaT does not equal L/h")
if not math.isclose(actual["Dltau"], actual["BetaT"] / 1012, rel_tol=0, abs_tol=1e-15):
    raise SystemExit("metadata Dltau is inconsistent")

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

manifest = {
    "schema_version": 1,
    "state": "complete",
    "job_id": os.environ.get("SLURM_JOB_ID"),
    "lattice": "honeycomb",
    "L": 28,
    "N": 1568,
    "hTrfd": 2.1325,
    "BetaT": actual["BetaT"],
    "LTrot": actual["LTrot"],
    "Dltau": actual["Dltau"],
    "nprocs": 32,
    "bins": 8,
    "rank_seeds": 32,
    "wall_time_seconds": metadata["runtime"]["wall_time_seconds"],
    "hashes": {
        name: digest(output / name)
        for name in (
            "bins.csv",
            "metadata.toml",
            "results.csv",
        )
    },
}
destination = output / "pilot_manifest.json"
temporary = output / ".pilot_manifest.json.tmp"
with temporary.open("x", encoding="utf-8") as stream:
    json.dump(manifest, stream, indent=2, sort_keys=True)
    stream.write("\n")
    stream.flush()
    os.fsync(stream.fileno())
os.replace(temporary, destination)
print(
    "pilot_verified bins=8 seeds=32 "
    f"wall={manifest['wall_time_seconds']:.6f}s",
    flush=True,
)
PY

printf 'pilot_complete job=%s\n' "${SLURM_JOB_ID:-unknown}"
