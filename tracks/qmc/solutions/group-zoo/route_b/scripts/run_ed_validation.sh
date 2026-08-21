#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
repo_root=$(cd -- "$script_dir/../.." && pwd -P)
evidence_root=${1:-/home/zcq/work/challenge-148-route-b-evidence/ed-reproduction}
task_root="$evidence_root/tasks"
result_root="$evidence_root/results"
report_path="$evidence_root/report.json"

mkdir -p -- "$result_root"
cd -- "$repo_root"
if [[ -n "$(git status --porcelain -- route_b)" ]]; then
    printf 'Route B worktree must be clean before recording Git provenance\n' >&2
    exit 1
fi
route_b_commit=$(git rev-parse HEAD)
[[ "$route_b_commit" =~ ^[0-9a-f]{40}$ ]] || {
    printf 'invalid Route B Git commit\n' >&2
    exit 1
}
export ROUTE_B_RELEASE_COMMIT="$route_b_commit"
julia --project=route_b route_b/scripts/make_ed_validation_manifest.jl \
    --config route_b/config/ed_validation.toml \
    --output "$task_root"

while IFS= read -r task_name; do
    printf '%s\n' "$task_name"
done < "$task_root/task_paths.txt" | xargs -P4 -I{} bash -c '
    julia --project=route_b route_b/scripts/run_task.jl \
        --task "$1/tasks/$2" --output "$1/results/$2"
' _ "$evidence_root" {}

julia --project=route_b route_b/scripts/validate_ed.jl \
    --config route_b/config/ed_validation.toml \
    --tasks "$task_root" \
    --results "$result_root" \
    --report "$report_path"
printf 'Route B ED report: %s\n' "$report_path"
