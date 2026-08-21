#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C LANG=C
umask 077

die() {
    printf 'capture_route_a_accounting: %s\n' "$*" >&2
    exit 1
}

(( $# == 5 )) ||
    die "usage: capture_route_a_accounting.sh CAMPAIGN_JSON RESULTS_DIR LOG_DIR BUNDLE_SCRIPT OUTPUT_DIR"
campaign=$1
results=$2
logs=$3
bundle=$4
output=$5
julia_bin=${JULIA_BIN:-julia}
sacct_bin=${SACCT_BIN:-sacct}
script_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
julia_project=${JULIA_PROJECT_PATH:-$script_root}

for item in "$campaign" "$bundle"; do
    [[ -f "$item" && ! -L "$item" ]] || die "input must be a regular non-symlink file: $item"
done
for item in "$results" "$logs"; do
    [[ -d "$item" && ! -L "$item" ]] || die "input must be a directory and not a symlink: $item"
done
command -v "$julia_bin" >/dev/null 2>&1 || die "Julia executable is unavailable"
command -v "$sacct_bin" >/dev/null 2>&1 || die "sacct executable is unavailable"
[[ -f "$julia_project/Project.toml" && ! -L "$julia_project/Project.toml" ]] ||
    die "Julia project is unavailable"
[[ "$output" == /* ]] || die "OUTPUT_DIR must be absolute"
[[ ! -e "$output" && ! -L "$output" ]] || die "OUTPUT_DIR already exists"
output_parent=$(dirname -- "$output")
[[ -d "$output_parent" && ! -L "$output_parent" ]] ||
    die "OUTPUT_DIR parent must be an existing non-symlink directory"

campaign_sha=$(sha256sum "$campaign" | awk '{print $1}')
bundle_sha=$(sha256sum "$bundle" | awk '{print $1}')
stage=$(mktemp -d "$output_parent/.route-a-accounting-stage.XXXXXX")
cleanup() {
    [[ -n "${stage:-}" && -d "$stage" ]] && rm -rf -- "$stage"
    return 0
}
trap cleanup EXIT
mkdir "$stage/wrappers"

write_result_inventory() {
    local destination=$1
    "$julia_bin" --startup-file=no --project="$julia_project" -e '
        using JSON
        using SHA
        directory, destination = ARGS
        names = sort(filter(name -> endswith(name, ".json"), readdir(directory)))
        isempty(names) && error("results directory contains no JSON files")
        open(destination, "w") do io
            println(io, "result_file|result_sha256|slurm_job_id")
            for name in names
                basename(name) == name && !occursin("|", name) ||
                    error("unsafe result basename")
                path = joinpath(directory, name)
                isfile(path) && !islink(path) || error("result is not a regular file: " * name)
                bytes = read(path)
                parsed = JSON.parse(String(bytes))
                parsed isa AbstractDict || error("result is not an object: " * name)
                provenance = get(parsed, "provenance", nothing)
                provenance isa AbstractDict || error("result provenance is absent: " * name)
                job = get(provenance, "slurm_job_id", nothing)
                job isa AbstractString && occursin(r"^[0-9]+$", job) ||
                    error("result has invalid Slurm job id: " * name)
                println(io, name, "|", bytes2hex(sha256(bytes)), "|", job)
            end
        end
    ' "$results" "$destination"
}

write_result_inventory "$stage/result_provenance.psv"
tail -n +2 "$stage/result_provenance.psv" | cut -d'|' -f3 | sort -u >"$stage/job_ids.txt"
[[ -s "$stage/job_ids.txt" ]] || die "no Slurm job IDs were discovered"
jobs_csv=$(paste -sd, "$stage/job_ids.txt")
[[ "$jobs_csv" =~ ^[0-9]+(,[0-9]+)*$ ]] || die "discovered Slurm job list is malformed"

accounting_header='JobIDRaw|JobID|JobName|State|ElapsedRaw|TimelimitRaw|ReqMem|AllocCPUS|MaxRSS|ExitCode|SubmitLine'
"$sacct_bin" -j "$jobs_csv"     --format=JobIDRaw,JobID,JobName%64,State,ElapsedRaw,TimelimitRaw,ReqMem,AllocCPUS,MaxRSS,ExitCode,SubmitLine%500     -P >"$stage/sacct.raw.psv"
[[ $(sed -n '1p' "$stage/sacct.raw.psv") == "$accounting_header" ]] ||
    die "sacct returned an unexpected header"

printf '%s\n' "$accounting_header" >"$stage/sacct.psv"
printf '%s\n'     'allocation_key|raw_job_id|array_task_id|wrapper_file|wrapper_sha256|start_index|end_index'     >"$stage/wrapper_inventory.unsorted.psv"
allocation_count=0
shopt -s nullglob
while IFS= read -r raw_job_id; do
    [[ "$raw_job_id" =~ ^[0-9]+$ ]] || die "invalid raw job id"
    job_rows=$(awk -F'|' -v id="$raw_job_id" 'NR > 1 && $1 == id { print }' "$stage/sacct.raw.psv")
    batch_rows=$(awk -F'|' -v id="$raw_job_id.batch" 'NR > 1 && $1 == id { print }' "$stage/sacct.raw.psv")
    [[ $(printf '%s\n' "$job_rows" | awk 'NF { count++ } END { print count + 0 }') -eq 1 ]] ||
        die "expected exactly one allocation row for $raw_job_id"
    [[ $(printf '%s\n' "$batch_rows" | awk 'NF { count++ } END { print count + 0 }') -eq 1 ]] ||
        die "expected exactly one batch row for $raw_job_id"

    IFS='|' read -r row_raw display job_name state elapsed limit reqmem cpus maxrss exit_code submit_line extra         <<<"$job_rows"
    [[ -z "${extra:-}" ]] || die "allocation row contains an unexpected field separator"
    [[ "$row_raw" == "$raw_job_id" && "$display" =~ ^([0-9]+)_([0-9]+)$ ]] ||
        die "allocation display ID is malformed for $raw_job_id"
    array_job_id=${BASH_REMATCH[1]}
    array_task_id=${BASH_REMATCH[2]}
    [[ "$state" == "COMPLETED" && "$exit_code" == "0:0" ]] ||
        die "allocation $display is not COMPLETED 0:0"
    [[ "$elapsed" =~ ^[1-9][0-9]*$ && "$limit" =~ ^[1-9][0-9]*$ ]] ||
        die "allocation $display has invalid timing"
    [[ -n "$reqmem" && "$cpus" =~ ^[1-9][0-9]*$ ]] ||
        die "allocation $display has invalid requested resources"

    IFS='|' read -r batch_raw batch_display batch_name batch_state batch_elapsed batch_limit         batch_reqmem batch_cpus batch_maxrss batch_exit batch_submit batch_extra <<<"$batch_rows"
    [[ -z "${batch_extra:-}" ]] || die "batch row contains an unexpected field separator"
    [[ "$batch_raw" == "$raw_job_id.batch" && "$batch_display" == "$display.batch" &&
        "$batch_name" == "batch" && "$batch_state" == "COMPLETED" &&
        "$batch_exit" == "0:0" && -n "$batch_maxrss" ]] ||
        die "batch row is invalid for $display"

    matches=("$logs"/*-"$array_job_id"_"$array_task_id".out)
    (("${#matches[@]}" == 1)) ||
        die "expected exactly one wrapper stdout for $display"
    wrapper=${matches[0]}
    [[ -f "$wrapper" && ! -L "$wrapper" ]] ||
        die "wrapper stdout must be a regular non-symlink file"
    mapfile -t completion_lines < <(
        grep -E '^route_a_bundle: completed task indices [0-9]+-[0-9]+$' "$wrapper" || true
    )
    (("${#completion_lines[@]}" == 1)) ||
        die "wrapper stdout has no unique completion line for $display"
    completion=${completion_lines[0]}
    last_nonempty=$(awk 'NF { line=$0 } END { print line }' "$wrapper")
    [[ "$last_nonempty" == "$completion" ]] ||
        die "wrapper completion line is not final for $display"
    [[ "$completion" =~ ^route_a_bundle:\ completed\ task\ indices\ ([0-9]+)-([0-9]+)$ ]] ||
        die "wrapper completion range is malformed for $display"
    start_index=${BASH_REMATCH[1]}
    end_index=${BASH_REMATCH[2]}
    ((10#$start_index <= 10#$end_index)) ||
        die "wrapper completion range is reversed for $display"

    wrapper_name=$(basename -- "$wrapper")
    [[ "$wrapper_name" != *'|'* && ! -e "$stage/wrappers/$wrapper_name" ]] ||
        die "wrapper basename is unsafe or duplicated"
    cp -- "$wrapper" "$stage/wrappers/$wrapper_name"
    wrapper_sha=$(sha256sum "$stage/wrappers/$wrapper_name" | awk '{print $1}')
    printf '%s|%s|%s|%s|%s|%s|%s\n'         "$display" "$raw_job_id" "$array_task_id" "$wrapper_name" "$wrapper_sha"         "$start_index" "$end_index" >>"$stage/wrapper_inventory.unsorted.psv"
    printf '%s\n%s\n' "$job_rows" "$batch_rows" >>"$stage/sacct.unsorted.psv"
    allocation_count=$((allocation_count + 1))
done <"$stage/job_ids.txt"
(( allocation_count > 0 )) || die "no completed allocations were captured"

sort -t'|' -k2,2n -k1,1 "$stage/sacct.unsorted.psv" >>"$stage/sacct.psv"
{
    sed -n '1p' "$stage/wrapper_inventory.unsorted.psv"
    tail -n +2 "$stage/wrapper_inventory.unsorted.psv" | sort -t'|' -k1,1
} >"$stage/wrapper_inventory.psv"
rm -- "$stage/sacct.raw.psv" "$stage/sacct.unsorted.psv"     "$stage/wrapper_inventory.unsorted.psv" "$stage/job_ids.txt"

write_result_inventory "$stage/result_provenance.final.psv"
cmp -s "$stage/result_provenance.psv" "$stage/result_provenance.final.psv" ||
    die "result files changed during accounting capture"
rm -- "$stage/result_provenance.final.psv"
[[ $(sha256sum "$campaign" | awk '{print $1}') == "$campaign_sha" ]] ||
    die "campaign changed during accounting capture"
[[ $(sha256sum "$bundle" | awk '{print $1}') == "$bundle_sha" ]] ||
    die "bundle script changed during accounting capture"

sacct_sha=$(sha256sum "$stage/sacct.psv" | awk '{print $1}')
wrapper_inventory_sha=$(sha256sum "$stage/wrapper_inventory.psv" | awk '{print $1}')
result_inventory_sha=$(sha256sum "$stage/result_provenance.psv" | awk '{print $1}')
result_count=$(($(wc -l <"$stage/result_provenance.psv") - 1))
"$julia_bin" --startup-file=no --project="$julia_project" -e '
    using JSON
    output, campaign_sha, bundle_sha, sacct_sha, wrapper_sha, result_sha,
        allocation_count, result_count = ARGS
    record = (
        schema_version=1,
        kind="route_a_accounting_capture",
        campaign_sha256=campaign_sha,
        bundle_script_sha256=bundle_sha,
        sacct_sha256=sacct_sha,
        wrapper_inventory_sha256=wrapper_sha,
        result_provenance_sha256=result_sha,
        allocation_count=parse(Int, allocation_count),
        result_count=parse(Int, result_count),
    )
    open(output, "w") do io
        JSON.print(io, record)
        write(io, "\n")
    end
' "$stage/capture.json" "$campaign_sha" "$bundle_sha" "$sacct_sha"     "$wrapper_inventory_sha" "$result_inventory_sha" "$allocation_count" "$result_count"

mv -- "$stage" "$output"
stage=
printf 'captured %d allocations for %d results in %s\n'     "$allocation_count" "$result_count" "$output"
