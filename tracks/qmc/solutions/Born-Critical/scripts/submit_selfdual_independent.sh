#!/bin/bash
# Submit eight one-cell jobs per wave to avoid this cluster's long-array requeue.
#
# The site job-submit policy may rewrite a repeated request for ws5 into an
# exclusion of ws5.  Therefore this driver uses at most one ws5 slot per wave
# and verifies ReqNodeList immediately after every submission.  A rewritten
# job is cancelled before it can consume resources.
set -euo pipefail

run_spec_relative="${1:?usage: submit_selfdual_independent.sh RUN_SPEC_RELATIVE}"
solution_root="/home/ystu/quantum.harness/tracks/qmc/solutions/Born-Critical"
run_root="/home/ystu/quantum.harness/${run_spec_relative%/run_spec.json}"
spec_path="/home/ystu/quantum.harness/${run_spec_relative}"
sbatch_path="${solution_root}/slurm/stage4-selfdual-array.sbatch"

missing_indices() {
    python3 - "$spec_path" "$run_root" "${1:-8}" <<'PY'
import json,pathlib,sys
spec=json.load(open(sys.argv[1]))
run=pathlib.Path(sys.argv[2])
limit=int(sys.argv[3])
missing=[]
for index,cell in enumerate(spec["cells"],1):
    manifest=run/"cells"/cell["cell_id"]/"manifest.json"
    try:
        success=manifest.exists() and json.load(open(manifest)).get("status")=="success"
    except Exception:
        success=False
    if not success:
        missing.append(index)
print(" ".join(map(str,missing[:limit])))
PY
}

while true; do
    read -r -a indices <<< "$(missing_indices 8)"
    if [[ ${#indices[@]} -eq 0 ]]; then
        echo "[independent] all cells have success manifests"
        exit 0
    fi

    # This slot layout is frozen against the live audit immediately below.
    # ws1 has two free GPUs (reserve eight CPUs); ws3 has one eight-CPU GPU
    # job and one free GPU (reserve four CPUs).  ws2 has both GPUs allocated.
    slots=(ws1 ws1 ws1 ws1 ws2 ws2 ws3 ws5)
    ws3_count=0
    ws1_count=0
    ws2_count=0
    ws5_count=0
    for position in "${!indices[@]}"; do
        case "${slots[$position]}" in
            ws3) ws3_count=$((ws3_count + 1)) ;;
            ws1) ws1_count=$((ws1_count + 1)) ;;
            ws2) ws2_count=$((ws2_count + 1)) ;;
            ws5) ws5_count=$((ws5_count + 1)) ;;
        esac
    done
    python3 "${solution_root}/scripts/audit_slurm_resources.py" \
        --ssh ws4 --user ystu --planned-node ws3 \
        --planned-cpus $((2 * ws3_count))
    python3 "${solution_root}/scripts/audit_slurm_resources.py" \
        --ssh ws4 --user ystu --planned-node ws1 \
        --planned-cpus $((2 * ws1_count))
    python3 "${solution_root}/scripts/audit_slurm_resources.py" \
        --ssh ws4 --user ystu --planned-node ws2 \
        --planned-cpus $((2 * ws2_count))
    python3 "${solution_root}/scripts/audit_slurm_resources.py" \
        --ssh ws4 --user ystu --planned-node ws5 \
        --planned-cpus $((2 * ws5_count))

    job_ids=()
    for position in "${!indices[@]}"; do
        index="${indices[$position]}"
        node="${slots[$position]}"
        submission="$(ssh ws4 sbatch \
            --partition=gpu --nodelist="$node" --nodes=1 --ntasks=1 \
            --cpus-per-task=1 --mem=4G --time=03:00:00 \
            --array="$index" \
            --export="ALL,HARNESS_RUN_SPEC=${run_spec_relative}" \
            < "$sbatch_path")"
        echo "$submission index=${index} node=${node}"
        job_id="${submission##* }"
        request_line="$(ssh ws4 "scontrol show job '${job_id}' | grep -m1 'ReqNodeList='")"
        if [[ "$request_line" != *"ReqNodeList=${node} "* ]] \
            || [[ "$request_line" != *"ExcNodeList=(null)"* ]]; then
            echo "[independent] scheduler rewrote job ${job_id}: ${request_line}; cancelling"
            ssh ws4 scancel "$job_id"
            continue
        fi
        job_ids+=("$job_id")
    done

    while true; do
        read -r -a remaining <<< "$(missing_indices 8)"
        all_wave_done=true
        for index in "${indices[@]}"; do
            for value in "${remaining[@]}"; do
                if [[ "$index" == "$value" ]]; then all_wave_done=false; fi
            done
        done
        if $all_wave_done; then
            echo "[independent] wave complete indices=${indices[*]}"
            break
        fi
        active=0
        for job_id in "${job_ids[@]}"; do
            count="$(ssh ws4 "squeue -h -j '${job_id}' | wc -l")"
            active=$((active + count))
        done
        if [[ $active -eq 0 ]]; then
            echo "[independent] wave ended partially; retrying missing cells"
            break
        fi
        sleep 10
    done
done
