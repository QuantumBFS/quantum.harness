#!/bin/sh
set -eu

archive_url='https://github.com/QuantumBFS/quantum.harness/releases/download/occam-circuit-data-v1/occam-circuit.zip'
expected_sha='c15f84839a365dd9daab686ccfd58a50ce286d5f1071d7f093e9fdd091ecaa1b'
repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
temporary_dir=$(mktemp -d "${TMPDIR:-/tmp}/occam-circuit.XXXXXX")
trap 'rm -rf "$temporary_dir"' EXIT HUP INT TERM

curl -L --fail --silent --show-error "$archive_url" \
  -o "$temporary_dir/occam-circuit.zip"

actual_sha=$(shasum -a 256 "$temporary_dir/occam-circuit.zip" | awk '{print $1}')
if [ "$actual_sha" != "$expected_sha" ]; then
  echo "checksum mismatch: expected $expected_sha, got $actual_sha" >&2
  exit 1
fi

unzip -q "$temporary_dir/occam-circuit.zip" -d "$temporary_dir/unpacked"
mkdir -p "$repo_root/vendor"
rm -rf "$repo_root/vendor/occam-circuit"
mv "$temporary_dir/unpacked/occam-circuit" "$repo_root/vendor/occam-circuit"

echo "verified SHA-256: $actual_sha"
echo "installed official data at $repo_root/vendor/occam-circuit"
