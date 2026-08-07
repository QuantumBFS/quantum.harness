#!/usr/bin/env bash
#SBATCH --job-name=occam71-espresso
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --output=/home/user_milksang/private/homefile/quantum_harness/issue71_occam/results/occam71/routes/symbolic-hybrid-seed42/logs/espresso-%j.out
#SBATCH --error=/home/user_milksang/private/homefile/quantum_harness/issue71_occam/results/occam71/routes/symbolic-hybrid-seed42/logs/espresso-%j.err

set -euo pipefail

repo=/home/user_milksang/private/homefile/quantum_harness/issue71_occam
code="$repo/tracks/qcs/solutions/Genshin_Impact-71/routes/symbolic_hybrid"
work="$repo/results/occam71/routes/symbolic-hybrid-seed42"
source="$repo/results/occam71/tools/abc-e76768b9d34f/job-42912/source"
archive="$repo/results/occam71/tools/abc-source-e76768b9d34f.tar"
tool_root="$repo/results/occam71/tools/espresso-e76768b9d34f"
build="$tool_root/job-$SLURM_JOB_ID"
expected_commit=e76768b9d34f9dc67cb6608efecd55db271ff849
expected_archive_sha=6a2cb045808579a9c7fe1758b94de968dcf4cbb114c7b726091e776d40b9cdf9
expected_main_sha=2361118aac6635e52f21f71b08b6df8e5a1444f9d6e42021c1c5b1c2be736b0b
expected_abc_sha=a971b5a85892e3bf2d09b6d62eaf6f608d7638936e39d6e4b3095e9c72c9c771

mkdir -p "$work/logs" "$build/bin"
test -x "$source/abc"
test -f "$source/libabc.a"
actual_archive_sha=$(sha256sum "$archive" | awk '{print $1}')
actual_main_sha=$(sha256sum "$source/src/misc/espresso/main.c" | awk '{print $1}')
actual_abc_sha=$(sha256sum "$source/abc" | awk '{print $1}')
if [[ "$actual_archive_sha" != "$expected_archive_sha" ]] ||
   [[ "$actual_main_sha" != "$expected_main_sha" ]] ||
   [[ "$actual_abc_sha" != "$expected_abc_sha" ]]; then
    echo "pinned source/tool hash mismatch" >&2
    exit 2
fi

# The embedded standalone CLI is official Berkeley Espresso source. In ABC's
# tree its historical include points at ABC's application header rather than
# the adjacent Espresso CLI header; restore that one include in a recorded copy.
sed 's#"base/main/main.h"#"main.h"#' \
    "$source/src/misc/espresso/main.c" > "$build/espresso-cli-main.c"
diff -u "$source/src/misc/espresso/main.c" \
    "$build/espresso-cli-main.c" > "$build/espresso-cli-include.patch" || true

cd "$source"
gcc -std=gnu89 -Wno-implicit-int -Wno-return-type \
    -Isrc -Isrc/misc/util -Isrc/misc/espresso \
    -include src/misc/util/abc_global.h $(./arch_flags) \
    -c "$build/espresso-cli-main.c" -o "$build/espresso-main.o"
mkdir -p "$build/espresso-objects"
for c_source in src/misc/espresso/*.c; do
    if [[ "$c_source" == "src/misc/espresso/main.c" ]]; then
        continue
    fi
    object="$build/espresso-objects/$(basename "${c_source%.c}").o"
    gcc -std=gnu89 -Wno-implicit-int -Wno-return-type \
        -Isrc -Isrc/misc/util -Isrc/misc/espresso \
        -include src/misc/util/abc_global.h $(./arch_flags) \
        -c "$c_source" -o "$object"
done
g++ "$build/espresso-main.o" "$build"/espresso-objects/*.o libabc.a \
    -lm -ldl -lpthread -o "$build/bin/espresso"
cp -p abc "$build/bin/abc"

printf '.i 1\n.o 1\n.type fr\n.p 1\n0 1\n.e\n' > "$build/smoke.pla"
"$build/bin/espresso" -o f "$build/smoke.pla" \
    > "$build/smoke-minimized.pla" 2> "$build/smoke.log"
grep -q '^0 1$' "$build/smoke-minimized.pla"

sha256sum "$build/bin/abc" "$build/bin/espresso" \
    "$build/espresso-cli-main.c" "$build/espresso-cli-include.patch" \
    > "$build/tool-sha256.txt"
{
    printf 'source_commit=%s\n' "$expected_commit"
    printf 'source_archive_sha256=%s\n' "$actual_archive_sha"
    printf 'source_main_sha256=%s\n' "$actual_main_sha"
    printf 'abc_sha256=%s\n' "$actual_abc_sha"
    printf 'source_tree=%s\n' "$source"
    printf 'slurm_job_id=%s\n' "$SLURM_JOB_ID"
    printf 'slurm_node=%s\n' "$SLURMD_NODENAME"
    printf 'root_seed=%s\n' 42
} > "$build/build-metadata.txt"
printf 'success\n' > "$build/SMOKE_COMPLETE"

python -u "$code/run_espresso_only.py" \
    --work "$work" --abc "$build/bin/abc" \
    --espresso "$build/bin/espresso"
printf 'success\n' > "$build/BUILD_AND_RUN_COMPLETE"
