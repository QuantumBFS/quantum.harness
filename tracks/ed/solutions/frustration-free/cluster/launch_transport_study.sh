#!/bin/bash
set -uo pipefail

: "${TRANSPORT_RUN_DIR:?TRANSPORT_RUN_DIR is required}"
: "${TRANSPORT_SOURCE_DIR:?TRANSPORT_SOURCE_DIR is required}"
: "${TRANSPORT_SOURCE_COMMIT:?TRANSPORT_SOURCE_COMMIT is required}"
: "${TRANSPORT_PYTHON:?TRANSPORT_PYTHON is required}"

worker="$TRANSPORT_SOURCE_DIR/scripts/transport_study.py"
slurm="$TRANSPORT_SOURCE_DIR/cluster/transport_study.slurm"
manifests="$TRANSPORT_RUN_DIR/manifests"
maps="$TRANSPORT_RUN_DIR/task_maps"
logs="$TRANSPORT_RUN_DIR/logs"
static="$TRANSPORT_RUN_DIR/static"
refined="$TRANSPORT_RUN_DIR/chern20"
realtime="$TRANSPORT_RUN_DIR/realtime"
aggregate="$TRANSPORT_RUN_DIR/aggregate"
mkdir -p "$manifests" "$maps" "$logs" "$TRANSPORT_RUN_DIR/chern10" \
    "$static" "$refined" "$realtime"

if [[ ! -f $TRANSPORT_SOURCE_DIR/SOURCE_COMMIT ]] || \
   [[ $(<"$TRANSPORT_SOURCE_DIR/SOURCE_COMMIT") != "$TRANSPORT_SOURCE_COMMIT" ]]; then
    echo "source commit mismatch" >&2
    exit 2
fi

static_manifest="$manifests/static.jsonl"
realtime_manifest="$manifests/realtime.jsonl"
refinement_manifest="$manifests/refinement.jsonl"
[[ -f $static_manifest ]] || "$TRANSPORT_PYTHON" "$worker" manifest --kind static > "$static_manifest"
[[ -f $realtime_manifest ]] || "$TRANSPORT_PYTHON" "$worker" manifest --kind realtime > "$realtime_manifest"

walltime() {
    case "$1" in
        1) echo 06:00:00 ;;
        2) echo 12:00:00 ;;
        *) echo 24:00:00 ;;
    esac
}

run_stage() {
    local stage=$1
    local manifest=$2
    local result_dir=$3
    local attempt=0
    while true; do
        attempt=$((attempt + 1))
        local map="$maps/${stage}_attempt_$(printf '%03d' "$attempt").jsonl"
        local missing=(missing --kind "$stage" --result-dir "$result_dir" --L 8)
        if [[ $stage == refine ]]; then
            missing+=(--manifest "$manifest" --static-dir "$static")
        fi
        "$TRANSPORT_PYTHON" "$worker" "${missing[@]}" > "$map" || exit 2
        local count
        count=$(wc -l < "$map")
        ((count > 0)) || return
        local prefix="$maps/${stage}_attempt_$(printf '%03d' "$attempt")_chunk_"
        split -d -a 4 -l 190 --additional-suffix=.jsonl "$map" "$prefix"
        local chunk
        for chunk in "${prefix}"*.jsonl; do
            local n
            n=$(wc -l < "$chunk")
            local stamp
            stamp=$(basename "$chunk" .jsonl)
            local export_values="ALL,TRANSPORT_STAGE=$stage,TRANSPORT_PYTHON=$TRANSPORT_PYTHON,TRANSPORT_SOURCE_DIR=$TRANSPORT_SOURCE_DIR,TRANSPORT_SOURCE_COMMIT=$TRANSPORT_SOURCE_COMMIT,TRANSPORT_TASK_MAP=$chunk,TRANSPORT_RUN_DIR=$TRANSPORT_RUN_DIR"
            if ! output=$(sbatch --wait --parsable \
                --job-name="transport-${stage}-a${attempt}" \
                --array="0-$((n - 1))%128" \
                --time="$(walltime "$attempt")" \
                --output="$logs/${stamp}_%A_%a.out" \
                --error="$logs/${stamp}_%A_%a.err" \
                --export="$export_values" "$slurm" 2>&1); then
                echo "$(date -Is) stage=$stage attempt=$attempt chunk=$stamp result=$output" >&2
            else
                echo "$(date -Is) stage=$stage attempt=$attempt chunk=$stamp job=$output"
            fi
        done
    done
}

run_stage static "$static_manifest" "$static"
if [[ ! -f $refinement_manifest ]]; then
    "$TRANSPORT_PYTHON" "$worker" select --static-dir "$static" --L 8 > "$refinement_manifest"
fi
run_stage refine "$refinement_manifest" "$refined"
run_stage realtime "$realtime_manifest" "$realtime"

if [[ ! -d $aggregate ]]; then
    "$TRANSPORT_PYTHON" "$worker" aggregate \
        --static-dir "$static" --refined-dir "$refined" \
        --realtime-dir "$realtime" --refinement-manifest "$refinement_manifest" \
        --output-dir "$aggregate" --L 8
fi
echo TRANSPORT_STUDY_COMPLETE
