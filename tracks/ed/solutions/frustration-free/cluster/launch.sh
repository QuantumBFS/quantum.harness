#!/bin/bash
set -uo pipefail

: "${SCAN_SOURCE_DIR:?SCAN_SOURCE_DIR is required}"
: "${SCAN_SOURCE_COMMIT:?SCAN_SOURCE_COMMIT is required}"
: "${SCAN_PYTHON:?SCAN_PYTHON is required}"

SCAN_RUN_DIR=${SCAN_RUN_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}
SCAN_MAX_CONCURRENT=${SCAN_MAX_CONCURRENT:-128}
# The cluster account caps submitted array elements at 200. Leave headroom for
# controller and smoke jobs while preserving the independent-task throughput.
SCAN_CHUNK_SIZE=${SCAN_CHUNK_SIZE:-190}
SCAN_L=${SCAN_L:-8}
SCAN_INITIAL_WALLTIME=${SCAN_INITIAL_WALLTIME:-02:00:00}
SCAN_RETRY_WALLTIME=${SCAN_RETRY_WALLTIME:-06:00:00}
SCAN_FINAL_WALLTIME=${SCAN_FINAL_WALLTIME:-24:00:00}

WORKER="$SCAN_SOURCE_DIR/scripts/cluster_worker.py"
SBATCH_SCRIPT="$SCAN_SOURCE_DIR/cluster/worker.slurm"
MANIFEST_DIR="$SCAN_RUN_DIR/manifests"
TASK_MAP_DIR="$SCAN_RUN_DIR/task_maps"
LOG_DIR="$SCAN_RUN_DIR/logs"
CHERN_DIR="$SCAN_RUN_DIR/chern10"
STATIC_DIR="$SCAN_RUN_DIR/static"
REFINED_DIR="$SCAN_RUN_DIR/chern20"
REALTIME_DIR="$SCAN_RUN_DIR/realtime"
AGGREGATE_DIR="$SCAN_RUN_DIR/aggregate"
STATUS_FILE="$SCAN_RUN_DIR/controller_status.json"
SUBMISSION_LOG="$SCAN_RUN_DIR/submissions.log"
REFINEMENT_MANIFEST="$MANIFEST_DIR/refinement.jsonl"

mkdir -p "$SCAN_RUN_DIR" "$MANIFEST_DIR" "$TASK_MAP_DIR" "$LOG_DIR" \
    "$CHERN_DIR" "$STATIC_DIR" "$REFINED_DIR" "$REALTIME_DIR" || exit 2

if [[ ! -f $SCAN_SOURCE_DIR/SOURCE_COMMIT ]] || \
   [[ $(<"$SCAN_SOURCE_DIR/SOURCE_COMMIT") != "$SCAN_SOURCE_COMMIT" ]]; then
    echo "Source commit manifest does not match SCAN_SOURCE_COMMIT" >&2
    exit 2
fi
if [[ ! -f $WORKER || ! -f $SBATCH_SCRIPT ]]; then
    echo "Cluster source is incomplete" >&2
    exit 2
fi

controller_complete=0
current_stage=initializing

write_status() {
    local state=$1
    local stage=$2
    local message=$3
    local temporary="$STATUS_FILE.tmp.$$"
    printf '{"state":"%s","stage":"%s","message":"%s","updated_at":"%s"}\n' \
        "$state" "$stage" "$message" "$(date -Is)" > "$temporary"
    mv "$temporary" "$STATUS_FILE"
}

on_exit() {
    local rc=$?
    if ((controller_complete == 0)); then
        write_status "EXITED" "$current_stage" "controller_exit_$rc"
    fi
}
trap on_exit EXIT

attention_wait() {
    local message=$1
    write_status "ATTENTION_REQUIRED" "$current_stage" "$message"
    echo "ATTENTION_REQUIRED stage=$current_stage reason=$message" >&2
    while true; do
        sleep 900
    done
}

create_manifest() {
    local kind=$1
    local output=$2
    if [[ -f $output ]]; then
        return
    fi
    local temporary="$output.tmp.$$"
    if ! "$SCAN_PYTHON" "$WORKER" manifest --kind "$kind" > "$temporary"; then
        attention_wait "manifest_${kind}_failed"
    fi
    mv "$temporary" "$output"
}

missing_map() {
    local stage=$1
    local output=$2
    case "$stage" in
        static)
            "$SCAN_PYTHON" "$WORKER" missing \
                --kind static --result-dir "$STATIC_DIR" --L "$SCAN_L" > "$output"
            ;;
        refine)
            "$SCAN_PYTHON" "$WORKER" missing \
                --kind refine --result-dir "$REFINED_DIR" --L "$SCAN_L" \
                --manifest "$REFINEMENT_MANIFEST" --static-dir "$STATIC_DIR" \
                --target-grid "${SCAN_REFINED_GRID:-20}" > "$output"
            ;;
        realtime)
            "$SCAN_PYTHON" "$WORKER" missing \
                --kind realtime --result-dir "$REALTIME_DIR" --L "$SCAN_L" > "$output"
            ;;
    esac
}

walltime_for_attempt() {
    local attempt=$1
    if ((attempt == 1)); then
        echo "$SCAN_INITIAL_WALLTIME"
    elif ((attempt == 2)); then
        echo "$SCAN_RETRY_WALLTIME"
    else
        echo "$SCAN_FINAL_WALLTIME"
    fi
}

run_stage() {
    local stage=$1
    local attempt=0
    local previous_missing=-1
    local stagnant=0
    current_stage=$stage

    while true; do
        attempt=$((attempt + 1))
        local task_map="$TASK_MAP_DIR/${stage}_attempt_$(printf '%03d' "$attempt").jsonl"
        local temporary="$task_map.tmp.$$"
        if ! missing_map "$stage" "$temporary"; then
            attention_wait "${stage}_validation_failed"
        fi
        mv "$temporary" "$task_map"
        local count
        count=$(wc -l < "$task_map")
        if ((count == 0)); then
            write_status "RUNNING" "$stage" "stage_complete"
            return
        fi

        if ((count == previous_missing)); then
            stagnant=$((stagnant + 1))
        else
            stagnant=0
        fi
        if ((stagnant >= 3)); then
            attention_wait "${stage}_made_no_progress_after_3_retries"
        fi
        previous_missing=$count
        write_status "RUNNING" "$stage" "attempt_${attempt}_missing_${count}"

        local chunk_prefix="$TASK_MAP_DIR/${stage}_attempt_$(printf '%03d' "$attempt")_chunk_"
        rm -f "${chunk_prefix}"*.jsonl
        split -d -a 4 -l "$SCAN_CHUNK_SIZE" --additional-suffix=.jsonl \
            "$task_map" "$chunk_prefix" || attention_wait "${stage}_split_failed"
        local walltime
        walltime=$(walltime_for_attempt "$attempt")
        local chunk
        for chunk in "${chunk_prefix}"*.jsonl; do
            local chunk_count
            chunk_count=$(wc -l < "$chunk")
            local chunk_name
            chunk_name=$(basename "$chunk" .jsonl)
            local export_values
            export_values="ALL,SCAN_STAGE=$stage,SCAN_PYTHON=$SCAN_PYTHON,SCAN_SOURCE_DIR=$SCAN_SOURCE_DIR,SCAN_TASK_MAP=$chunk,SCAN_L=$SCAN_L,SCAN_CHERN_DIR=$CHERN_DIR,SCAN_STATIC_DIR=$STATIC_DIR,SCAN_REFINED_DIR=$REFINED_DIR,SCAN_REALTIME_DIR=$REALTIME_DIR,SCAN_LEGACY_DIR=${SCAN_LEGACY_DIR:-},SCAN_DELTA0=${SCAN_DELTA0:-0.9},SCAN_CAPITAL_DELTA0=${SCAN_CAPITAL_DELTA0:-3.0},SCAN_POLARIZATION_POINTS=${SCAN_POLARIZATION_POINTS:-10},SCAN_REFINED_GRID=${SCAN_REFINED_GRID:-20},SCAN_INITIAL_TIME_STEP=${SCAN_INITIAL_TIME_STEP:-0.05},SCAN_CHARGE_TOLERANCE=${SCAN_CHARGE_TOLERANCE:-0.005},SCAN_TIME_REFINEMENTS=${SCAN_TIME_REFINEMENTS:-3}"
            local submission_output
            submission_output=$(sbatch --wait --parsable \
                --job-name="rmh-${stage}-a${attempt}" \
                --array="0-$((chunk_count - 1))%${SCAN_MAX_CONCURRENT}" \
                --time="$walltime" \
                --output="$LOG_DIR/${chunk_name}_%A_%a.out" \
                --error="$LOG_DIR/${chunk_name}_%A_%a.err" \
                --export="$export_values" \
                "$SBATCH_SCRIPT" 2>&1)
            local submission_rc=$?
            printf '%s stage=%s attempt=%d chunk=%s tasks=%d walltime=%s submission_rc=%d output=%q\n' \
                "$(date -Is)" "$stage" "$attempt" "$chunk_name" "$chunk_count" \
                "$walltime" "$submission_rc" "$submission_output" | tee -a "$SUBMISSION_LOG"
        done
    done
}

echo "run_dir=$SCAN_RUN_DIR"
echo "source_dir=$SCAN_SOURCE_DIR"
echo "source_commit=$SCAN_SOURCE_COMMIT"
echo "python=$SCAN_PYTHON"
write_status "RUNNING" "$current_stage" "controller_started"

create_manifest static "$MANIFEST_DIR/static.jsonl"
create_manifest realtime "$MANIFEST_DIR/realtime.jsonl"
run_stage static

current_stage=select_refinement
if [[ ! -f $REFINEMENT_MANIFEST ]]; then
    temporary="$REFINEMENT_MANIFEST.tmp.$$"
    if ! "$SCAN_PYTHON" "$WORKER" select --static-dir "$STATIC_DIR" \
        --L "$SCAN_L" > "$temporary"; then
        attention_wait "refinement_selection_failed"
    fi
    mv "$temporary" "$REFINEMENT_MANIFEST"
fi
run_stage refine
run_stage realtime

current_stage=aggregate
if ! "$SCAN_PYTHON" "$WORKER" aggregate \
    --static-dir "$STATIC_DIR" \
    --realtime-dir "$REALTIME_DIR" \
    --refined-dir "$REFINED_DIR" \
    --output-dir "$AGGREGATE_DIR" \
    --refinement-manifest "$REFINEMENT_MANIFEST" \
    --refined-grid "${SCAN_REFINED_GRID:-20}" \
    --L "$SCAN_L"; then
    attention_wait "aggregate_failed"
fi

write_status "COMPLETE" "$current_stage" "all_manifests_validated"
controller_complete=1
echo "SCAN_COMPLETE"
