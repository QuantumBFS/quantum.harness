#!/usr/bin/env bash
#SBATCH --job-name=occam71-abc-build
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --output=/home/user_milksang/private/homefile/quantum_harness/issue71_occam/results/occam71/routes/symbolic-hybrid-seed42/logs/abc-build-%j.out
#SBATCH --error=/home/user_milksang/private/homefile/quantum_harness/issue71_occam/results/occam71/routes/symbolic-hybrid-seed42/logs/abc-build-%j.err

set -euo pipefail

repo=/home/user_milksang/private/homefile/quantum_harness/issue71_occam
archive="$repo/results/occam71/tools/abc-source-e76768b9d34f.tar"
tool_root="$repo/results/occam71/tools/abc-e76768b9d34f"
build="$tool_root/job-$SLURM_JOB_ID"
expected_archive_sha=6a2cb045808579a9c7fe1758b94de968dcf4cbb114c7b726091e776d40b9cdf9

mkdir -p "$repo/results/occam71/routes/symbolic-hybrid-seed42/logs"
mkdir -p "$build/source" "$build/bin"

actual_archive_sha=$(sha256sum "$archive" | awk '{print $1}')
if [[ "$actual_archive_sha" != "$expected_archive_sha" ]]; then
    echo "archive SHA mismatch: $actual_archive_sha" >&2
    exit 2
fi

tar -xf "$archive" -C "$build/source"
cd "$build/source"
make -j "$SLURM_CPUS_PER_TASK" ABC_MAKE_NO_DEPS=1 ABC_USE_NO_READLINE=1
make -j "$SLURM_CPUS_PER_TASK" ABC_MAKE_NO_DEPS=1 ABC_USE_NO_READLINE=1 libabc.a

cp -p abc "$build/bin/abc"

# ABC embeds the original Berkeley Espresso sources but intentionally excludes
# its CLI main.c from libabc.a. Compile that official entry point and link it
# against the just-built pinned library, so `.type fr` reaches espresso(F,D,R).
gcc -std=gnu89 -Wno-implicit-int -Wno-return-type \
    -Isrc -Isrc/misc/util -include src/misc/util/abc_global.h $(./arch_flags) \
    -c src/misc/espresso/main.c -o "$build/espresso-main.o"
g++ "$build/espresso-main.o" libabc.a \
    -lm -ldl -lpthread -o "$build/bin/espresso"

"$build/bin/abc" -c "version" > "$build/abc-version.txt"
printf '.i 1\n.o 1\n.type fr\n.p 1\n0 1\n.e\n' > "$build/smoke.pla"
"$build/bin/espresso" -o f "$build/smoke.pla" > "$build/smoke-minimized.pla"
grep -q '^0 1$' "$build/smoke-minimized.pla"

sha256sum "$build/bin/abc" "$build/bin/espresso" > "$build/tool-sha256.txt"
{
    printf 'source_commit=%s\n' e76768b9d34f9dc67cb6608efecd55db271ff849
    printf 'source_archive_sha256=%s\n' "$actual_archive_sha"
    printf 'slurm_job_id=%s\n' "$SLURM_JOB_ID"
    printf 'slurm_node=%s\n' "$SLURMD_NODENAME"
    printf 'root_seed=%s\n' 42
} > "$build/build-metadata.txt"
printf 'success\n' > "$build/BUILD_COMPLETE"
