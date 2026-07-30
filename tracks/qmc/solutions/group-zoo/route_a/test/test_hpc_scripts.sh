#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
stage="$repo_root/hpc/stage_scnet.sh"
accounting_capture="$repo_root/hpc/capture_route_a_accounting.sh"
slurm_dir="$repo_root/hpc/slurm"
scripts=(
    "$stage"
    "$accounting_capture"
    "$slurm_dir/route_a_smoke.sbatch"
    "$slurm_dir/route_a_array.sbatch"
    "$slurm_dir/route_a_benchmark.sbatch"
)

fail() {
    printf 'FAIL: %s\n' "$*" >&2
    exit 1
}

for script in "${scripts[@]}"; do
    [[ -f "$script" ]] || fail "missing $script"
    bash -n "$script"
done

if rg -n -- '--gres|--gpus|mpirun|srun[[:space:]]+--mpi' "$repo_root/hpc"; then
    fail "GPU or MPI resource request found"
fi

for script in "$slurm_dir"/*.sbatch; do
    for directive in \
        '#SBATCH --account=giggleliu' \
        '#SBATCH --partition=qdagnormal' \
        '#SBATCH --nodes=1' \
        '#SBATCH --ntasks=1' \
        '#SBATCH --cpus-per-task=1'; do
        rg -F -x -- "$directive" "$script" >/dev/null ||
            fail "missing directive '$directive' in $script"
    done
done

rg -F -x -- '#SBATCH --time=00:20:00' "$slurm_dir/route_a_smoke.sbatch" >/dev/null
rg -F -x -- '#SBATCH --mem=4G' "$slurm_dir/route_a_smoke.sbatch" >/dev/null
rg -F -x -- '#SBATCH --time=04:00:00' "$slurm_dir/route_a_benchmark.sbatch" >/dev/null
rg -F -x -- '#SBATCH --mem=16G' "$slurm_dir/route_a_benchmark.sbatch" >/dev/null
! rg -n -- '^#SBATCH --(time|mem)=' "$slurm_dir/route_a_array.sbatch" >/dev/null ||
    fail "general array must receive time and memory at submission"

rg -F -- 'git diff --quiet' "$stage" >/dev/null
rg -F -- 'git diff --cached --quiet' "$stage" >/dev/null
rg -F -- 'git archive' "$stage" >/dev/null
rg -F -- 'rev-parse --verify' "$stage" >/dev/null
rg -F -x -- 'export LC_ALL=C LANG=C' "$stage" >/dev/null
rg -F -- '(( $# <= 2 ))' "$stage" >/dev/null
rg -F -- '--sort=name --mtime=@946684800' "$stage" >/dev/null
rg -F -- 'gzip -n' "$stage" >/dev/null
rg -F -- 'flock -x' "$stage" >/dev/null
rg -F -- '--startup-file=no --version' "$stage" >/dev/null
rg -F -- 'scripts/aggregate_route_a.jl' "$stage" >/dev/null
rg -F -- 'scripts/make_route_a_manifest.jl' "$stage" >/dev/null
rg -F -- '25000000000' "$stage" >/dev/null
for payload in project.tar julia.tar.gz depot.tar.gz release.json; do
    rg -F -- "sha256sum \"\$incoming/$payload\"" "$stage" >/dev/null
done
rg -F -- '/home/zcq/.julia/juliaup/julia-1.12.6+0.x64.linux.gnu' "$stage" >/dev/null
rg -F -- '/work/home/zhangchenqi/challenge148' "$stage" >/dev/null
for depot_part in registries packages artifacts; do
    rg -F -- "$depot_part" "$stage" >/dev/null
done
rg -F -- 'LC_ALL=C' "$stage" "$slurm_dir"/*.sbatch >/dev/null
rg -F -- 'JULIA_PKG_PRECOMPILE_AUTO=0' "$stage" >/dev/null ||
    fail "staging must not precompile into the network-filesystem depot"
! rg -F -- 'Pkg.precompile()' "$stage" >/dev/null ||
    fail "staging must not precompile on the login node"
! rg -n -- 'rsync|cp[[:space:]]+-[a-zA-Z]*r' "$stage" >/dev/null ||
    fail "staging must not copy the working tree"
! rg -n -- 'tar .*-[a-zA-Z]*c[a-zA-Z]*z[a-zA-Z]*f' "$stage" >/dev/null ||
    fail "gzip archives must use deterministic gzip -n"
if bash "$stage" scnet HEAD unexpected >/dev/null 2>&1; then
    fail "staging accepted more than two arguments"
fi

tmp=$(mktemp -d)
trap 'rm -rf -- "$tmp"' EXIT
release="$tmp/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
result_root="$tmp/results"
task_dir="$tmp/tasks"
mkdir -p "$release/julia/bin" "$release/project/scripts" "$release/project/hpc/slurm" \
    "$release/depot" "$task_dir"
cp "$slurm_dir/route_a_array.sbatch" "$release/project/hpc/slurm/route_a_array.sbatch"
touch "$release/project/Project.toml" "$release/project/Manifest.toml"
touch "$release/project/scripts/run_cluster.jl"
printf '{}\n' >"$task_dir/first.json"
printf '{}\n' >"$task_dir/second.json"
printf 'first.json\nsecond.json\n' >"$task_dir/task_paths.txt"

cat >"$release/julia/bin/julia" <<'FAKE_JULIA'
#!/usr/bin/env bash
set -euo pipefail
{
    printf 'cwd=%s\n' "$PWD"
    printf 'depot=%s\n' "${JULIA_DEPOT_PATH-}"
    printf 'locale=%s\n' "${LC_ALL-}"
    printf 'release_commit=%s\n' "${CHALLENGE148_RELEASE_COMMIT-}"
    printf 'arg=%s\n' "$@"
} >"${HPC_CAPTURE:?}"
FAKE_JULIA
chmod +x "$release/julia/bin/julia"

capture="$tmp/capture"
node_tmp="$tmp/node-tmp"
mkdir -p "$node_tmp"
env TASK_PATHS="$task_dir/task_paths.txt" RELEASE="$release" RESULT_ROOT="$result_root" \
    SLURM_ARRAY_TASK_ID=1 SLURM_JOB_ID=77 SLURM_TMPDIR="$node_tmp" \
    HPC_CAPTURE="$capture" bash "$slurm_dir/route_a_array.sbatch"
rg -F -x -- "cwd=$result_root" "$capture" >/dev/null
rg -F -x -- "depot=$node_tmp/challenge148-depot-77:$release/depot" "$capture" >/dev/null
rg -F -x -- 'locale=C' "$capture" >/dev/null
rg -F -x -- 'release_commit=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' "$capture" >/dev/null
rg -F -x -- "arg=$task_dir/second.json" "$capture" >/dev/null

expect_array_failure() {
    if env TASK_PATHS="$task_dir/task_paths.txt" RELEASE="$release" RESULT_ROOT="$result_root" \
        SLURM_ARRAY_TASK_ID="$1" HPC_CAPTURE="$capture" bash "$slurm_dir/route_a_array.sbatch" \
        >/dev/null 2>&1; then
        fail "array unexpectedly accepted index $1"
    fi
}

expect_array_failure 2
if env RELEASE="$release" RESULT_ROOT="$result_root" SLURM_ARRAY_TASK_ID=0 \
    HPC_CAPTURE="$capture" bash "$slurm_dir/route_a_array.sbatch" >/dev/null 2>&1; then
    fail "array accepted missing TASK_PATHS"
fi

printf '/tmp/absolute.json\n' >"$task_dir/task_paths.txt"
expect_array_failure 0
printf '../escape.json\n' >"$task_dir/task_paths.txt"
expect_array_failure 0
printf 'linked.json\n' >"$task_dir/task_paths.txt"
ln -s "$task_dir/first.json" "$task_dir/linked.json"
expect_array_failure 0

printf 'first.json\n' >"$task_dir/task_paths.txt"
env TASK_PATHS="$task_dir/task_paths.txt" RELEASE="$release" RESULT_ROOT="$result_root" \
    SLURM_ARRAY_TASK_ID=0 STOP_AFTER_BINS=3 HPC_CAPTURE="$capture" \
    bash "$slurm_dir/route_a_smoke.sbatch"
rg -F -x -- 'arg=--stop-after-bins' "$capture" >/dev/null
rg -F -x -- 'arg=3' "$capture" >/dev/null

printf 'Task 11 HPC script checks passed\n'
bash "$repo_root/test/test_capture_route_a_accounting.sh"
