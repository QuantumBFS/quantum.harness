#!/usr/bin/env bash
set -euo pipefail

export LC_ALL=C

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
lock_path="$repo_root/tools/abc/LOCK.json"

read_lock_field() {
    python3 -c \
        'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))[sys.argv[2]])' \
        "$lock_path" "$1"
}

run_with_timeout() {
    local timeout_seconds=$1
    shift
    python3 -c '
import subprocess
import sys
try:
    result = subprocess.run(sys.argv[2:], timeout=float(sys.argv[1]), check=False)
except subprocess.TimeoutExpired:
    print(f"command timed out after {sys.argv[1]} seconds: {sys.argv[2:]}", file=sys.stderr)
    raise SystemExit(124)
raise SystemExit(result.returncode)
' "$timeout_seconds" "$@"
}

commit=$(read_lock_field commit)
archive_url=$(read_lock_field archive_url)
expected_sha=$(read_lock_field archive_sha256)
expected_bytes=$(read_lock_field archive_bytes)
destination="$repo_root/target/tools/abc/$commit"
binary="$destination/abc"
metadata="$destination/build-metadata.json"
lock_sha=$(shasum -a 256 "$lock_path" | awk '{print $1}')

if [[ -x "$binary" && -f "$metadata" ]]; then
    binary_sha=$(shasum -a 256 "$binary" | awk '{print $1}')
    if python3 -c '
import json
import sys
metadata = json.load(open(sys.argv[1], encoding="utf-8"))
raise SystemExit(0 if (
    metadata.get("schema_version") == 1
    and metadata.get("commit") == sys.argv[2]
    and metadata.get("lock_sha256") == sys.argv[3]
    and metadata.get("binary_sha256") == sys.argv[4]
) else 1)
' "$metadata" "$commit" "$lock_sha" "$binary_sha"; then
        (
            cd "$destination"
            run_with_timeout 10 "$binary" -c "version; quit"
        )
        echo "Berkeley ABC cache verified at $binary"
        exit 0
    fi
fi

temporary_dir=$(mktemp -d "${TMPDIR:-/tmp}/occam-abc.XXXXXX")
trap 'rm -rf "$temporary_dir"' EXIT HUP INT TERM
archive="$temporary_dir/abc.tar.gz"
build_log="$temporary_dir/build.log"

curl --location --fail --silent --show-error \
    --connect-timeout 30 --max-time 300 \
    "$archive_url" --output "$archive"

actual_bytes=$(wc -c <"$archive" | tr -d '[:space:]')
if [[ "$actual_bytes" != "$expected_bytes" ]]; then
    echo "ABC archive size mismatch: expected $expected_bytes, got $actual_bytes" >&2
    exit 1
fi
actual_sha=$(shasum -a 256 "$archive" | awk '{print $1}')
if [[ "$actual_sha" != "$expected_sha" ]]; then
    echo "ABC archive checksum mismatch: expected $expected_sha, got $actual_sha" >&2
    exit 1
fi

run_with_timeout 120 tar -xzf "$archive" -C "$temporary_dir"
source_root="$temporary_dir/abc-$commit"
if [[ ! -d "$source_root" ]]; then
    echo "verified ABC archive did not contain abc-$commit" >&2
    exit 1
fi

if ! run_with_timeout 1800 make -C "$source_root" -j2 ABC_USE_NO_READLINE=1 \
    >"$build_log" 2>&1; then
    tail -n 80 "$build_log" >&2
    exit 1
fi
build_log_bytes=$(wc -c <"$build_log" | tr -d '[:space:]')
if (( build_log_bytes > 16777216 )); then
    echo "ABC build log exceeded 16 MiB: $build_log_bytes bytes" >&2
    exit 1
fi
(
    cd "$source_root"
    run_with_timeout 10 "$source_root/abc" -c "version; quit"
)

mkdir -p "$destination"
temporary_binary="$destination/.abc.$$.tmp"
temporary_metadata="$destination/.build-metadata.$$.tmp"
cp "$source_root/abc" "$temporary_binary"
chmod +x "$temporary_binary"
binary_sha=$(shasum -a 256 "$temporary_binary" | awk '{print $1}')
printf '%s\n' \
    '{' \
    '  "schema_version": 1,' \
    "  \"commit\": \"$commit\"," \
    "  \"archive_sha256\": \"$actual_sha\"," \
    "  \"lock_sha256\": \"$lock_sha\"," \
    "  \"binary_sha256\": \"$binary_sha\"" \
    '}' >"$temporary_metadata"
mv "$temporary_binary" "$binary"
mv "$temporary_metadata" "$metadata"

echo "verified ABC archive SHA-256: $actual_sha"
echo "installed Berkeley ABC at $binary"
