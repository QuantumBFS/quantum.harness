#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C LANG=C

repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
capture="$repo_root/hpc/capture_route_a_accounting.sh"

fail() {
    printf 'FAIL: %s\n' "$*" >&2
    exit 1
}

tmp=$(mktemp -d)
trap 'rm -rf -- "$tmp"' EXIT
campaign="$tmp/benchmark.json"
results="$tmp/results"
logs="$tmp/logs"
bundle="$tmp/route_a_bundle.sbatch"
fake_sacct="$tmp/fake-sacct"
accounting="$tmp/accounting.psv"
mkdir -p "$results" "$logs"
printf '{"campaign_id":"benchmark-5c3e1a4868c36f8e"}\n' >"$campaign"
printf '#!/usr/bin/env bash\n' >"$bundle"
chmod +x "$bundle"

for index in $(seq 0 15); do
    job=9001
    (( index >= 8 )) && job=9002
    printf '{"provenance":{"slurm_job_id":"%s"}}\n' "$job"         >"$results/result-$(printf '%02d' "$index").json"
done
printf 'route_a_bundle: completed task indices 0-7\n' >"$logs/probe-8000_0.out"
printf 'route_a_bundle: completed task indices 8-15\n' >"$logs/probe-8000_1.out"

cat >"$fake_sacct" <<'FAKE'
#!/usr/bin/env bash
set -euo pipefail
cat "${FAKE_SACCT_OUTPUT:?}"
FAKE
chmod +x "$fake_sacct"

write_good_accounting() {
    cat >"$accounting" <<'PSV'
JobIDRaw|JobID|JobName|State|ElapsedRaw|TimelimitRaw|ReqMem|AllocCPUS|MaxRSS|ExitCode|SubmitLine
9001|8000_0|route_a_bundle.sbatch|COMPLETED|210|1800|64G|8||0:0|sbatch --array=0
9001.batch|8000_0.batch|batch|COMPLETED|210|||8|4063576K|0:0|
9002|8000_1|route_a_bundle.sbatch|COMPLETED|221|1800|64G|8||0:0|sbatch --array=1
9002.batch|8000_1.batch|batch|COMPLETED|221|||8|4100000K|0:0|
PSV
}

write_good_accounting
output="$tmp/evidence"
JULIA_BIN="$(command -v julia)" SACCT_BIN="$fake_sacct" FAKE_SACCT_OUTPUT="$accounting"     bash "$capture" "$campaign" "$results" "$logs" "$bundle" "$output"

expected_header='JobIDRaw|JobID|JobName|State|ElapsedRaw|TimelimitRaw|ReqMem|AllocCPUS|MaxRSS|ExitCode|SubmitLine'
[[ $(sed -n '1p' "$output/sacct.psv") == "$expected_header" ]] ||
    fail "canonical accounting header differs"
[[ $(wc -l <"$output/sacct.psv") -eq 5 ]] || fail "accounting row count differs"
[[ $(wc -l <"$output/wrapper_inventory.psv") -eq 3 ]] || fail "wrapper inventory row count differs"
[[ -f "$output/wrappers/probe-8000_0.out" ]] || fail "first wrapper was not copied"
[[ -f "$output/wrappers/probe-8000_1.out" ]] || fail "second wrapper was not copied"
rg -F -x -- 'route_a_bundle: completed task indices 0-7'     "$output/wrappers/probe-8000_0.out" >/dev/null
rg -F -- '8000_0|9001|0|probe-8000_0.out|' "$output/wrapper_inventory.psv" >/dev/null
rg -F -- '|0|7' "$output/wrapper_inventory.psv" >/dev/null
rg -F -- '|8|15' "$output/wrapper_inventory.psv" >/dev/null
julia --startup-file=no --project="$repo_root" -e '
    using JSON, SHA
    capture = JSON.parsefile(ARGS[1])
    capture["schema_version"] == 1 || error("schema")
    capture["kind"] == "route_a_accounting_capture" || error("kind")
    capture["allocation_count"] == 2 || error("count")
    for (field, file) in (
        ("sacct_sha256", "sacct.psv"),
        ("wrapper_inventory_sha256", "wrapper_inventory.psv"),
    )
        capture[field] == bytes2hex(sha256(read(joinpath(dirname(ARGS[1]), file)))) ||
            error(field)
    end
' "$output/capture.json"

if JULIA_BIN="$(command -v julia)" SACCT_BIN="$fake_sacct" FAKE_SACCT_OUTPUT="$accounting"     bash "$capture" "$campaign" "$results" "$logs" "$bundle" "$output" >/dev/null 2>&1; then
    fail "capture overwrote an existing evidence directory"
fi

printf 'route_a_bundle: completed task indices 0-7\n' >"$logs/duplicate-8000_0.out"
if JULIA_BIN="$(command -v julia)" SACCT_BIN="$fake_sacct" FAKE_SACCT_OUTPUT="$accounting"     bash "$capture" "$campaign" "$results" "$logs" "$bundle" "$tmp/duplicate-evidence"     >/dev/null 2>&1; then
    fail "capture accepted duplicate wrapper logs"
fi
[[ ! -e "$tmp/duplicate-evidence" ]] || fail "failed duplicate capture left output"
rm "$logs/duplicate-8000_0.out"

awk 'NR != 3' "$accounting" >"$tmp/missing-batch.psv"
if JULIA_BIN="$(command -v julia)" SACCT_BIN="$fake_sacct" FAKE_SACCT_OUTPUT="$tmp/missing-batch.psv"     bash "$capture" "$campaign" "$results" "$logs" "$bundle" "$tmp/missing-evidence"     >/dev/null 2>&1; then
    fail "capture accepted a missing batch row"
fi
[[ ! -e "$tmp/missing-evidence" ]] || fail "failed batch capture left output"

sed 's/9002|8000_1|route_a_bundle.sbatch|COMPLETED/9002|8000_1|route_a_bundle.sbatch|FAILED/'     "$accounting" >"$tmp/failed-job.psv"
if JULIA_BIN="$(command -v julia)" SACCT_BIN="$fake_sacct" FAKE_SACCT_OUTPUT="$tmp/failed-job.psv"     bash "$capture" "$campaign" "$results" "$logs" "$bundle" "$tmp/failed-evidence"     >/dev/null 2>&1; then
    fail "capture accepted a failed allocation"
fi
[[ ! -e "$tmp/failed-evidence" ]] || fail "failed state capture left output"

printf 'route_a_bundle: completed task indices 8-x\n' >"$logs/probe-8000_1.out"
if JULIA_BIN="$(command -v julia)" SACCT_BIN="$fake_sacct" FAKE_SACCT_OUTPUT="$accounting"     bash "$capture" "$campaign" "$results" "$logs" "$bundle" "$tmp/range-evidence"     >/dev/null 2>&1; then
    fail "capture accepted a malformed wrapper range"
fi
[[ ! -e "$tmp/range-evidence" ]] || fail "failed range capture left output"

printf 'Route A accounting capture checks passed\n'
