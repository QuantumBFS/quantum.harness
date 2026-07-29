#!/usr/bin/env bash
#SBATCH --job-name=ss-gamma-scan
#SBATCH --partition=xhacnormalb
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=24G
#SBATCH --time=03:00:00
#SBATCH --output=tracks/polyopt/solutions/sdp-gap-seekers/results/slurm-%j.out

set -euo pipefail

: "${SS_SCAN_GAMMAS:?set SS_SCAN_GAMMAS to space-separated nonnegative rationals}"
: "${SS_RUN_ID:?set SS_RUN_ID to a unique scan directory name}"

JULIA_BIN="${JULIA_BIN:-/work/home/sihhu/.julia/juliaup/julia-1.11.5+0.x64.linux.gnu/bin/julia}"
JULIA_PROJECT="${JULIA_PROJECT:-/work/home/sihhu/quantum-hackson/challenge-88/repo-cb725ac3/julia-env}"
MOSEK_BIN_DIR="${MOSEK_BIN_DIR:-/work/home/sihhu/quantum-hackson/toolchains/mosek-11.2/mosek/11.2/tools/platform/linux64x86/bin}"
MOSEK_LICENSE="${MOSEK_LICENSE:-/work/home/sihhu/mosek/mosek.lic}"
SS_TIME_LIMIT_SECONDS="${SS_TIME_LIMIT_SECONDS:-1200}"
SS_AUDIT_TOLERANCE="${SS_AUDIT_TOLERANCE:-1e-7}"

REPOSITORY_ROOT="$(git rev-parse --show-toplevel)"
EXPECTED_ROOT="${SS_EXPECTED_REPOSITORY_ROOT:-$REPOSITORY_ROOT}"
[[ "$REPOSITORY_ROOT" == "$EXPECTED_ROOT" ]] || {
    echo "[ss-gamma-scan] refusing checkout: $REPOSITORY_ROOT" >&2
    exit 2
}
cd "$REPOSITORY_ROOT"

[[ -x "$JULIA_BIN" ]]
[[ -d "$JULIA_PROJECT" ]]
[[ -d "$MOSEK_BIN_DIR" ]]
[[ -f "$MOSEK_LICENSE" ]]
[[ -z "$(git status --porcelain --untracked-files=all)" ]] || {
    echo "[ss-gamma-scan] refusing dirty checkout" >&2
    exit 2
}

read -r -a gammas <<< "$SS_SCAN_GAMMAS"
[[ "${#gammas[@]}" -gt 0 ]]
for gamma in "${gammas[@]}"; do
    [[ "$gamma" =~ ^[0-9]+([/]{1,2}[0-9]+)?$ ]] || {
        echo "[ss-gamma-scan] invalid gamma: $gamma" >&2
        exit 2
    }
done

RUN_DIR="tracks/polyopt/solutions/sdp-gap-seekers/results/${SS_RUN_ID}"
[[ ! -e "$RUN_DIR" ]] || {
    echo "[ss-gamma-scan] refusing existing run directory: $RUN_DIR" >&2
    exit 2
}
mkdir -p "$RUN_DIR"

export PATH="${MOSEK_BIN_DIR}:${PATH}"
export LD_LIBRARY_PATH="${MOSEK_BIN_DIR}:${LD_LIBRARY_PATH:-}"
export MOSEKLM_LICENSE_FILE="$MOSEK_LICENSE"
export JULIA_NUM_THREADS="${SLURM_CPUS_PER_TASK:-16}"
export SS_SCAN_DYNAMIC_INPUT=1

git rev-parse HEAD > "$RUN_DIR/runner-commit.txt"
git rev-parse 'HEAD^{tree}' > "$RUN_DIR/runner-tree.txt"
git status --porcelain --untracked-files=all > "$RUN_DIR/git-status.txt"
printf '%s\n' "$SS_SCAN_GAMMAS" > "$RUN_DIR/requested-gammas.txt"
printf 'gamma\tbuild_exit\tsolve_exit\tclassification\n' > "$RUN_DIR/summary.tsv"

echo "[ss-gamma-scan] run_id=$SS_RUN_ID"
echo "[ss-gamma-scan] job_id=${SLURM_JOB_ID:-missing}"
echo "[ss-gamma-scan] gammas=$SS_SCAN_GAMMAS"
echo "[ss-gamma-scan] started=$(date -u +%Y-%m-%dT%H:%M:%SZ)"

echo "[ss-gamma-scan] string-boundary regression started"
"$JULIA_BIN" \
    --project="$JULIA_PROJECT" \
    --startup-file=no \
    --history-file=no \
    tracks/polyopt/solutions/sdp-gap-seekers/test/runner_string_boundary_tests.jl \
    2>&1 | tee "$RUN_DIR/string-boundary-tests.log"

builder=(
    "$JULIA_BIN"
    --project="$JULIA_PROJECT"
    --startup-file=no
    --history-file=no
    tracks/polyopt/solutions/sdp-gap-seekers/scripts/build_shastry_sutherland_full_spin_isotypic_reduced_mof.jl
)
solver=(
    "$JULIA_BIN"
    --project="$JULIA_PROJECT"
    --startup-file=no
    --history-file=no
    tracks/polyopt/solutions/sdp-gap-seekers/scripts/solve_shastry_sutherland_full_spin_isotypic_reduced_mof.jl
)

overall_exit=0
for gamma in "${gammas[@]}"; do
    tag="${gamma//\//over}"
    point_dir="$RUN_DIR/points/gamma-${tag}"
    input_dir="$point_dir/input"
    solve_dir="$point_dir/solve"
    mkdir -p "$solve_dir"

    echo "[ss-gamma-scan] gamma=$gamma build started"
    set +e
    /usr/bin/time -v -o "$point_dir/build-process-time.txt" \
        "${builder[@]}" \
        --gamma "$gamma" \
        --output "$input_dir" \
        2>&1 | tee "$point_dir/build.log"
    build_exit="${PIPESTATUS[0]}"
    set -e
    printf '%s\n' "$build_exit" > "$point_dir/build-exit-code.txt"
    if [[ "$build_exit" -ne 0 ]]; then
        printf '%s\t%s\t%s\t%s\n' \
            "$gamma" "$build_exit" "not_run" "builder_failure" \
            >> "$RUN_DIR/summary.tsv"
        overall_exit="$build_exit"
        break
    fi

    echo "[ss-gamma-scan] gamma=$gamma solve started"
    set +e
    "${solver[@]}" \
        --model "$input_dir/model.mof.json" \
        --runmeta "$input_dir/runmeta.toml" \
        --checksums "$input_dir/SHA256SUMS" \
        --expected-gamma "$gamma" \
        --repository-root "$REPOSITORY_ROOT" \
        --output "$solve_dir/result.toml" \
        --time-limit-seconds "$SS_TIME_LIMIT_SECONDS" \
        --threads "${SLURM_CPUS_PER_TASK:-16}" \
        --audit-tolerance "$SS_AUDIT_TOLERANCE" \
        2>&1 | tee "$point_dir/solve.log"
    solve_exit="${PIPESTATUS[0]}"
    set -e
    printf '%s\n' "$solve_exit" > "$point_dir/solve-exit-code.txt"
    classification="$(
        sed -n 's/^classification = "\(.*\)"/\1/p' \
            "$solve_dir/result.toml" | head -n 1
    )"
    classification="${classification:-missing}"
    printf '%s\t%s\t%s\t%s\n' \
        "$gamma" "$build_exit" "$solve_exit" "$classification" \
        >> "$RUN_DIR/summary.tsv"
    if [[ "$solve_exit" -ne 0 ]]; then
        overall_exit="$solve_exit"
        break
    fi
    if [[ "$classification" == \
        "infeasibility_candidate_requires_independent_ray_replay" ]]; then
        echo "[ss-gamma-scan] first infeasibility candidate at gamma=$gamma"
        break
    fi
done

printf '%s\n' "$overall_exit" > "$RUN_DIR/scan-exit-code.txt"
printf '%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    > "$RUN_DIR/finished-at-utc.txt"
(
    cd "$RUN_DIR"
    find . -type f ! -name SHA256SUMS -print0 |
        sort -z |
        xargs -0 sha256sum > SHA256SUMS
)

echo "[ss-gamma-scan] summary"
cat "$RUN_DIR/summary.tsv"
echo "[ss-gamma-scan] finished=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
sync
exit "$overall_exit"
