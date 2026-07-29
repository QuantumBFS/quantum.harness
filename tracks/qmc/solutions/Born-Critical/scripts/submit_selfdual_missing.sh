#!/bin/bash
# Submit self-dual cells in QOS-safe batches on a non-shared cluster.
set -euo pipefail

run_spec_relative="${1:?usage: submit_selfdual_missing.sh RUN_SPEC_RELATIVE}"
node="${2:-ws5}"
batch_size="${BORN_CRITICAL_BATCH_SIZE:-15}"
concurrency="${BORN_CRITICAL_CONCURRENCY:-8}"
solution_root="/home/ystu/quantum.harness/tracks/qmc/solutions/Born-Critical"
run_root="/home/ystu/quantum.harness/${run_spec_relative%/run_spec.json}"
spec_path="/home/ystu/quantum.harness/${run_spec_relative}"
sbatch_path="${solution_root}/slurm/stage4-selfdual-array.sbatch"

while true; do
    indices="$(python3 - "$spec_path" "$run_root" "$batch_size" <<'PY'
import json,pathlib,sys
spec=json.load(open(sys.argv[1]))
run=pathlib.Path(sys.argv[2])
limit=int(sys.argv[3])
missing=[]
for index,cell in enumerate(spec["cells"],1):
    manifest=run/"cells"/cell["cell_id"]/"manifest.json"
    if not manifest.exists():
        missing.append(index)
    else:
        try:
            if json.load(open(manifest)).get("status") != "success":
                missing.append(index)
        except Exception:
            missing.append(index)
print(",".join(str(value) for value in missing[:limit]))
PY
)"
    if [[ -z "$indices" ]]; then
        echo "[submit-selfdual] all cells have success manifests"
        exit 0
    fi

    planned_cpus=$((2 * concurrency))
    python3 "${solution_root}/scripts/audit_slurm_resources.py" \
        --ssh ws4 --user ystu --planned-node "$node" \
        --planned-cpus "$planned_cpus"

    submission="$(ssh ws4 sbatch \
        --partition=gpu --nodelist="$node" --nodes=1 --ntasks=1 \
        --cpus-per-task=1 --mem=4G --time=03:00:00 \
        --array="${indices}%${concurrency}" \
        --export="ALL,HARNESS_RUN_SPEC=${run_spec_relative}" \
        < "$sbatch_path")"
    echo "$submission"
    job_id="${submission##* }"

    while true; do
        remaining="$(python3 - "$spec_path" "$run_root" "$indices" <<'PY'
import json,pathlib,sys
spec=json.load(open(sys.argv[1]))
run=pathlib.Path(sys.argv[2])
indices=[int(value) for value in sys.argv[3].split(",")]
remaining=[]
for index in indices:
    cell=spec["cells"][index-1]
    manifest=run/"cells"/cell["cell_id"]/"manifest.json"
    try:
        success=manifest.exists() and json.load(open(manifest)).get("status")=="success"
    except Exception:
        success=False
    if not success:
        remaining.append(index)
print(",".join(map(str,remaining)))
PY
)"
        if [[ -z "$remaining" ]]; then
            ssh ws4 scancel "$job_id" >/dev/null 2>&1 || true
            echo "[submit-selfdual] batch ${indices} complete"
            break
        fi
        active="$(ssh ws4 "squeue -h -j '${job_id}' | wc -l")"
        if [[ "$active" -eq 0 ]]; then
            echo "[submit-selfdual] job ${job_id} ended with missing cells ${remaining}" >&2
            exit 2
        fi
        sleep 5
    done
done
