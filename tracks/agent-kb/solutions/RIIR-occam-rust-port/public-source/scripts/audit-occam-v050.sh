#!/usr/bin/env bash
set -euo pipefail

export LC_ALL=C

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_root"

expected_version=0.5.0
expected_tag="v$expected_version"
immutable_v030=dc4ffedc1a9807144f9bafa560582dad17e1763f
archive_name="occam-rust-port-$expected_tag-evidence.tar.gz"
archive_prefix="occam-rust-port-$expected_tag/"
stable_output="$repo_root/target/$expected_tag-release-evidence"

fail() {
    echo "v0.5.0 audit failed: $*" >&2
    exit 1
}

require_equal() {
    local label=$1
    local actual=$2
    local expected=$3
    if [[ "$actual" != "$expected" ]]; then
        fail "$label: expected '$expected', got '$actual'"
    fi
}

lock_package_version() {
    local lockfile=$1
    awk '
        $0 == "name = \"occam71_rust\"" { in_package = 1; next }
        in_package && /^version = / {
            split($0, fields, "\"")
            print fields[2]
            exit
        }
    ' "$lockfile"
}

echo "[1/5] main, privacy, immutable baseline, and version gates"
require_equal "current branch" "$(git branch --show-current)" main
if [[ -n "$(git status --porcelain)" ]]; then
    git status --short >&2
    fail "worktree must be clean"
fi
require_equal \
    "v0.3.0 peeled commit" \
    "$(git rev-parse 'v0.3.0^{}')" \
    "$immutable_v030"
require_equal "origin/main" "$(git rev-parse origin/main)" "$immutable_v030"
if [[ -n "$(git tag --list "$expected_tag")" ]]; then
    fail "$expected_tag must remain uncreated during local-candidate audit"
fi
require_equal \
    "GitHub repository visibility" \
    "$(gh repo view --json visibility --jq .visibility)" \
    PRIVATE

metadata_version=$(
    cargo metadata --locked --no-deps --format-version 1 |
        node -e '
            let source = "";
            process.stdin.on("data", (chunk) => source += chunk);
            process.stdin.on("end", () => {
                const packageRecord = JSON.parse(source).packages
                    .find((candidate) => candidate.name === "occam71_rust");
                if (!packageRecord) process.exit(2);
                process.stdout.write(packageRecord.version);
            });
        '
)
manifest_version=$(
    awk -F'"' '/^version = / { print $2; exit }' \
        challenge-71-occam/Cargo.toml
)
snapshot_version=$(
    awk -F'"' '/^version = / { print $2; exit }' \
        challenge-71-occam/solutions/rewrite-it-in-rust/search/Cargo.toml
)
require_equal "Cargo metadata version" "$metadata_version" "$expected_version"
require_equal "package manifest version" "$manifest_version" "$expected_version"
require_equal "snapshot manifest version" "$snapshot_version" "$expected_version"
for lockfile in \
    Cargo.lock \
    fuzz/Cargo.lock \
    challenge-71-occam/solutions/rewrite-it-in-rust/search/Cargo.lock
do
    require_equal \
        "$lockfile package version" \
        "$(lock_package_version "$lockfile")" \
        "$expected_version"
done
require_equal \
    "CLI version" \
    "$(cargo run --quiet --locked -p occam71_rust --bin occam71_rust -- --version)" \
    "occam71-rust $expected_version"
rg -q '^## \[0\.5\.0\] - 2026-07-28$' CHANGELOG.md ||
    fail "CHANGELOG.md lacks the exact 0.5.0 release heading"
rg -q '^# v0\.5\.0 — Measured and Auditable Occam Research$' \
    docs/releases/v0.5.0.md ||
    fail "v0.5.0 release notes have the wrong title"

echo "[2/5] complete correctness, research, Julia, fuzz, and secret audit"
./scripts/audit-occam-v030.sh
if [[ -n "$(git status --porcelain)" ]]; then
    git status --short >&2
    fail "complete prior audit changed tracked files"
fi

echo "[3/5] byte-reproducible exact-commit release archive"
first_output=$(mktemp -d "${TMPDIR:-/tmp}/occam-v050-first.XXXXXX")
second_output=$(mktemp -d "${TMPDIR:-/tmp}/occam-v050-second.XXXXXX")
trap 'rm -rf "$first_output" "$second_output"' EXIT HUP INT TERM
commit=$(git rev-parse HEAD)
./scripts/build-release-evidence "$first_output" "$commit"
./scripts/build-release-evidence "$second_output" "$commit"
cmp \
    "$first_output/$archive_name" \
    "$second_output/$archive_name"
cmp \
    "$first_output/$archive_name.sha256" \
    "$second_output/$archive_name.sha256"
(
    cd "$first_output"
    shasum -a 256 -c "$archive_name.sha256"
)

echo "[4/5] archive metadata, checksums, allowlist, and safety"
members="$first_output/members.txt"
tar -tzf "$first_output/$archive_name" >"$members"
awk -v prefix="$archive_prefix" '
    index($0, prefix) != 1 {
        print "archive member has wrong prefix: " $0 > "/dev/stderr"
        invalid = 1
    }
    END { exit invalid }
' "$members"
if rg -n '(^|/)\.\.(/|$)|(^/)' "$members"; then
    fail "archive contains an absolute or parent-traversal path"
fi
if rg -n '/(\.git|target|vendor)(/|$)' "$members"; then
    fail "archive contains a forbidden repository or generated directory"
fi
if rg -n '\.(a|o|so|dylib|dll|exe)(/)?$' "$members"; then
    fail "archive contains a prebuilt binary or object"
fi

extraction="$first_output/extracted"
mkdir -p "$extraction"
tar -xzf "$first_output/$archive_name" -C "$extraction"
evidence_root="$extraction/${archive_prefix%/}"
release_json="$evidence_root/RELEASE.json"
node - "$release_json" "$commit" <<'NODE'
import fs from "node:fs";

const [releasePath, expectedCommit] = process.argv.slice(2);
const release = JSON.parse(fs.readFileSync(releasePath, "utf8"));
const expectedProtocols = [
  "occam-generalization-v1-immutable",
  "occam-generalization-v2-measured-semantic",
];
if (
  release.schema_version !== 2 ||
  release.version !== "v0.5.0" ||
  release.package_version !== "0.5.0" ||
  release.commit !== expectedCommit ||
  JSON.stringify(release.evidence_protocols) !== JSON.stringify(expectedProtocols) ||
  release.contains_prebuilt_binaries !== false ||
  release.contains_abc_source_or_binary !== false ||
  release.contains_vendor_dataset !== false
) {
  throw new Error(`invalid RELEASE.json: ${JSON.stringify(release)}`);
}
NODE

(
    cd "$evidence_root"
    shasum -a 256 -c SHA256SUMS >/dev/null
    find . -type f \
        ! -name RELEASE.json \
        ! -name SHA256SUMS \
        -print |
        sed 's#^\./##' |
        sort >"$first_output/archive-files.txt"
    cut -c67- SHA256SUMS |
        sort >"$first_output/checksummed-files.txt"
)
cmp "$first_output/archive-files.txt" "$first_output/checksummed-files.txt"

while IFS= read -r executable; do
    if [[ "$(head -c 2 "$executable")" != '#!' ]]; then
        fail "archive contains a non-script executable: $executable"
    fi
done < <(find "$evidence_root" -type f -perm -111 -print)

if rg -n --hidden \
    '(gho[_]|github[_]pat[_]|BEGIN (RSA|OPENSSH|EC) PRIVATE K[E]Y|AWS[_]SECRET_ACCESS_KEY)' \
    "$evidence_root"; then
    fail "archive contains possible secret material"
fi
if rg -n -F "$repo_root" "$evidence_root"; then
    fail "archive contains the local absolute repository path"
fi
raw_hostname=$(hostname)
if [[ -n "$raw_hostname" ]] && rg -n -F "$raw_hostname" "$evidence_root"; then
    fail "archive contains the raw local hostname"
fi

echo "[5/5] stable local candidate artifact and clean handoff"
mkdir -p "$stable_output"
cp "$first_output/$archive_name" "$stable_output/$archive_name"
cp "$first_output/$archive_name.sha256" \
    "$stable_output/$archive_name.sha256"
(
    cd "$stable_output"
    shasum -a 256 -c "$archive_name.sha256"
)
if [[ -n "$(git status --porcelain)" ]]; then
    git status --short >&2
    fail "release audit left tracked changes"
fi
digest=$(awk '{ print $1; exit }' "$stable_output/$archive_name.sha256")
size=$(wc -c <"$stable_output/$archive_name" | tr -d ' ')
printf 'v0.5.0 local release candidate passed.\n'
printf 'commit:  %s\n' "$commit"
printf 'archive: %s\n' "$stable_output/$archive_name"
printf 'bytes:   %s\n' "$size"
printf 'sha256:  %s\n' "$digest"
