#!/usr/bin/env bash
#SBATCH --job-name=occ71-espresso-ucb
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --output=/home/user_milksang/private/homefile/quantum_harness/issue71_occam/results/occam71/routes/symbolic-hybrid-seed42/logs/espresso-ucb-%j.out
#SBATCH --error=/home/user_milksang/private/homefile/quantum_harness/issue71_occam/results/occam71/routes/symbolic-hybrid-seed42/logs/espresso-ucb-%j.err

set -euo pipefail
export PYTHONHASHSEED=42
export LC_ALL=C

repo=/home/user_milksang/private/homefile/quantum_harness/issue71_occam
code="$repo/tracks/qcs/solutions/Genshin_Impact-71/routes/symbolic_hybrid"
work="$repo/results/occam71/routes/symbolic-hybrid-seed42"
archive="$repo/results/occam71/tools/espresso-berkeley-1994.tar.gz"
abc="$repo/results/occam71/tools/abc-e76768b9d34f/job-42912/source/abc"
tool_root="$repo/results/occam71/tools/espresso-berkeley-1994"
build="$tool_root/job-$SLURM_JOB_ID"
expected_archive_sha=757256c24d33f343068a67f51a57f8dfbe8af01d122a8434ef99572544cb4802

mkdir -p "$work/logs" "$build/source" "$build/bin"
actual_archive_sha=$(sha256sum "$archive" | awk '{print $1}')
if [[ "$actual_archive_sha" != "$expected_archive_sha" ]]; then
    echo "official Berkeley source archive SHA mismatch" >&2
    exit 2
fi
tar -xzf "$archive" -C "$build/source"
compat_patch="$code/espresso-berkeley-errtrap-stdarg.patch"
compat_patch_sha=$(sha256sum "$compat_patch" | awk '{print $1}')
(
    cd "$build/source"
    chmod u+w errtrap/errtrap.c errtrap/errtrap.h
    patch --batch -p1 < "$compat_patch"
)

# Build the 1994 U.C. Berkeley distribution with its own original support
# libraries.  gnu89 and -fcommon restore the C dialect/global-symbol semantics
# assumed by this pre-ANSI-era release.  The only source patch mechanically
# translates the obsolete errtrap support library from varargs.h to stdarg.h;
# no Espresso algorithm source is changed.
cd "$build/source"
mkdir -p lib include doc bin man/man1 man/man5
compiler="gcc -std=gnu89 -fcommon"
(
    cd utility
    make ../include/utility.h CAD=.. CC="$compiler" COMPFLAG=-O2
)
# The archived `port` package reimplements ANSI libc routines such as strlen
# and strstr.  Those shims conflict with Rocky Linux's modern libc prototypes,
# so install its public headers but deliberately link an empty compatibility
# archive; all required routines are supplied by the system libc.
cp -p port/port.h port/ansi.h port/copyright.h include/
cp -p uprintf/uprintf.h errtrap/errtrap.h st/st.h mm/mm.h include/
ar rcs lib/libport.a
# The archived mm package replaces malloc/free/realloc and conflicts with
# modern libc prototypes.  Its public header is empty and Espresso needs no
# package-specific symbols, so retain the expected archive name while using
# the system allocator.
ar rcs lib/libmm.a
for package in uprintf errtrap st; do
    (
        cd "$package"
        make "lib${package}.a" CAD=.. CC="$compiler" COMPFLAG=-O2
    )
    cp -p "$package/lib${package}.a" lib/
done
(
    cd utility
    make libutility.a \
        OBJ='cpu_time.o prtime.o strsav.o' \
        CAD=.. CC="$compiler" COMPFLAG=-O2
)
cp -p utility/libutility.a lib/
(
    cd espresso
    make espresso CAD=.. CC="$compiler" COMPFLAG=-O2
)
cp -p espresso/espresso "$build/bin/espresso"
cp -p "$abc" "$build/bin/abc"

printf '.i 1\n.o 1\n.type fr\n.p 1\n0 1\n.e\n' > "$build/smoke.pla"
"$build/bin/espresso" -o f "$build/smoke.pla" \
    > "$build/smoke-minimized.pla" 2> "$build/smoke.log"
grep -q '^0 1$' "$build/smoke-minimized.pla"

sha256sum "$build/bin/espresso" "$build/bin/abc" \
    "$build/smoke.pla" "$build/smoke-minimized.pla" \
    > "$build/tool-and-smoke-sha256.txt"
{
    printf 'source_url=%s\n' \
        'https://ptolemy.berkeley.edu/projects/embedded/pubs/downloads/espresso/espresso.tar.gz'
    printf 'source_archive_sha256=%s\n' "$actual_archive_sha"
    printf 'source_last_updated=%s\n' '1994-11-01'
    printf 'compiler_mode=%s\n' 'gcc -std=gnu89 -fcommon -O2'
    printf 'algorithm_source_patches=%s\n' 'none'
    printf 'support_compatibility_patch=%s\n' \
        'espresso-berkeley-errtrap-stdarg.patch'
    printf 'support_compatibility_patch_sha256=%s\n' "$compat_patch_sha"
    printf 'compatibility_action=%s\n' \
        'system libc replaces archived port string/memory shims and mm allocator; errtrap varargs.h mechanically translated to stdarg.h; utility archive contains only Espresso-referenced cpu_time/prtime/strsav objects'
    printf 'slurm_job_id=%s\n' "$SLURM_JOB_ID"
    printf 'slurm_node=%s\n' "$SLURMD_NODENAME"
    printf 'root_seed=%s\n' 42
} > "$build/build-metadata.txt"
printf 'success\n' > "$build/SMOKE_COMPLETE"

python -u "$code/run_espresso_only.py" \
    --work "$work" \
    --abc "$build/bin/abc" \
    --espresso "$build/bin/espresso"
printf 'success\n' > "$build/BUILD_AND_RUN_COMPLETE"
