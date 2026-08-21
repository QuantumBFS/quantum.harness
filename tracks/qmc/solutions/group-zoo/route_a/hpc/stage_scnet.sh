#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C LANG=C
umask 077

die() {
    printf 'stage_scnet: %s\n' "$*" >&2
    exit 1
}

(( $# <= 2 )) || die "usage: stage_scnet.sh [SSH_HOST] [40_HEX_COMMIT]"
repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
remote_host=${1:-scnet}
requested_commit=${2:-HEAD}
remote_root=${SCNET_REMOTE_ROOT:-/work/home/zhangchenqi/challenge148}
locked_julia=/home/zcq/.julia/juliaup/julia-1.12.6+0.x64.linux.gnu

[[ "$remote_host" =~ ^[A-Za-z0-9_.@-]+$ ]] || die "unsafe SSH host"
[[ "$remote_root" =~ ^/[A-Za-z0-9._/-]+$ && "$remote_root" != / ]] ||
    die "SCNET_REMOTE_ROOT must be a safe absolute path"
[[ ! "$remote_root" =~ (^|/)\.\.(/|$) ]] || die "SCNET_REMOTE_ROOT must not escape through .."
if (( $# >= 2 )); then
    [[ "$requested_commit" =~ ^[0-9a-f]{40}$ ]] || die "release commit must be exactly 40 lowercase hex characters"
fi

cd "$repo_root"
git diff --quiet --ignore-submodules -- || die "tracked working tree changes must be committed"
git diff --cached --quiet --ignore-submodules -- || die "index changes must be committed"
release_commit=$(git rev-parse --verify "${requested_commit}^{commit}") || die "release commit does not exist"
[[ "$release_commit" =~ ^[0-9a-f]{40}$ ]] || die "Git returned a noncanonical release commit"

required_release_files=(
    Project.toml Manifest.toml src/Challenge148.jl scripts/run_cluster.jl
    scripts/aggregate_route_a.jl scripts/make_route_a_manifest.jl
    hpc/slurm/route_a_array.sbatch test/runtests.jl
)
for relative in "${required_release_files[@]}"; do
    git cat-file -e "${release_commit}:${relative}" 2>/dev/null ||
        die "release is not runnable: missing $relative"
done
[[ -x "$locked_julia/bin/julia" ]] || die "locked Julia distribution is unavailable"

stage_dir=$(mktemp -d)
cleanup() {
    rm -rf -- "$stage_dir"
}
trap cleanup EXIT

project_tar="$stage_dir/project.tar"
julia_tar="$stage_dir/julia.tar.gz"
depot_tar="$stage_dir/depot.tar.gz"
release_json="$stage_dir/release.json"
project_dir="$stage_dir/project"
depot_dir="$stage_dir/depot"
mkdir -p "$project_dir" "$depot_dir"

# The project payload is derived only from the named commit, never the working tree.
git archive --format=tar "$release_commit" >"$project_tar"
tar -xf "$project_tar" -C "$project_dir"

JULIA_DEPOT_PATH="$depot_dir" JULIA_PKG_PRECOMPILE_AUTO=0 LC_ALL=C \
    "$locked_julia/bin/julia" \
    --startup-file=no --project="$project_dir" -e 'using Pkg; Pkg.instantiate()'

depot_parts=()
for part in registries packages artifacts; do
    [[ -e "$depot_dir/$part" ]] && depot_parts+=("$part")
done
((${#depot_parts[@]} > 0)) || die "instantiation produced no distributable depot content"
tar --sort=name --mtime=@946684800 --owner=0 --group=0 --numeric-owner -cf - \
    -C "$depot_dir" "${depot_parts[@]}" | gzip -n >"$depot_tar"
tar --sort=name --mtime=@946684800 --owner=0 --group=0 --numeric-owner -cf - \
    -C "$locked_julia" . | gzip -n >"$julia_tar"

# The extracted release plus retained immutable payload archives must remain
# within the reviewed 25 GB storage request.
payload_bytes=$(stat -c '%s' "$project_tar" "$julia_tar" "$depot_tar" | awk '{total += $1} END {print total + 0}')
expanded_bytes=$(du -sb "$project_dir" "$locked_julia" "$depot_dir" | awk '{total += $1} END {print total + 0}')
((payload_bytes + expanded_bytes <= 25000000000)) || die "release payload exceeds 25 GB"

code_sha256=$(sha256sum "$project_tar" | awk '{print $1}')
manifest_sha256=$(git show "${release_commit}:Manifest.toml" | sha256sum | awk '{print $1}')
julia_sha256=$(sha256sum "$julia_tar" | awk '{print $1}')
depot_sha256=$(sha256sum "$depot_tar" | awk '{print $1}')
cat >"$release_json" <<JSON
{"schema_version":1,"kind":"route_a_scnet_release","release_commit":"$release_commit","code_archive_sha256":"$code_sha256","manifest_sha256":"$manifest_sha256","julia_archive_sha256":"$julia_sha256","depot_archive_sha256":"$depot_sha256"}
JSON
release_json_sha256=$(sha256sum "$release_json" | awk '{print $1}')

remote_stage="$remote_root/.stage-${release_commit}-$$"
ssh "$remote_host" bash -s -- "$remote_root" "$remote_stage" <<'REMOTE_PREPARE'
set -euo pipefail
root=$1
stage=$2
[[ "$root" =~ ^/[A-Za-z0-9._/-]+$ && "$root" != / && ! "$root" =~ (^|/)\.\.(/|$) ]] || exit 2
[[ "$stage" =~ ^/[A-Za-z0-9._/-]+$ && "$stage" == "$root/.stage-"* ]] || exit 2
mkdir -p "$root/releases"
rm -rf -- "$stage"
mkdir -p "$stage"
REMOTE_PREPARE

for payload in project.tar julia.tar.gz depot.tar.gz release.json; do
    ssh "$remote_host" "cat > '$remote_stage/$payload'" <"$stage_dir/$payload"
done

ssh "$remote_host" bash -s -- "$remote_root" "$remote_stage" "$release_commit" \
    "$code_sha256" "$julia_sha256" "$depot_sha256" "$release_json_sha256" <<'REMOTE_INSTALL'
set -euo pipefail
root=$1
incoming=$2
commit=$3
expected_code=$4
expected_julia=$5
expected_depot=$6
expected_release_json=$7
[[ "$root" =~ ^/[A-Za-z0-9._/-]+$ && "$root" != / && ! "$root" =~ (^|/)\.\.(/|$) ]] || exit 2
[[ "$commit" =~ ^[0-9a-f]{40}$ ]] || exit 2
[[ "$incoming" =~ ^/[A-Za-z0-9._/-]+$ && "$incoming" == "$root/.stage-${commit}-"* ]] || exit 2
for expected in "$expected_code" "$expected_julia" "$expected_depot" "$expected_release_json"; do
    [[ "$expected" =~ ^[0-9a-f]{64}$ ]] || exit 2
done
[[ $(sha256sum "$incoming/project.tar" | awk '{print $1}') == "$expected_code" ]] || exit 5
[[ $(sha256sum "$incoming/julia.tar.gz" | awk '{print $1}') == "$expected_julia" ]] || exit 5
[[ $(sha256sum "$incoming/depot.tar.gz" | awk '{print $1}') == "$expected_depot" ]] || exit 5
[[ $(sha256sum "$incoming/release.json" | awk '{print $1}') == "$expected_release_json" ]] || exit 5
release="$root/releases/$commit"
install="$root/releases/.${commit}.install.$$"
new_release=0
cleanup() {
    rm -rf -- "$incoming" "$install"
    if ((new_release)); then
        rm -rf -- "$release"
    fi
}
trap cleanup EXIT
exec 9>"$root/.release.lock"
flock -x 9

if [[ -e "$release" || -L "$release" ]]; then
    [[ -d "$release" && ! -L "$release" && -f "$release/release.json" ]] || exit 3
    cmp -s "$incoming/release.json" "$release/release.json" || exit 4
    for payload in project.tar julia.tar.gz depot.tar.gz; do
        cmp -s "$incoming/$payload" "$release/.payload/$payload" || exit 4
    done
else
    mkdir -p "$install/project" "$install/julia" "$install/depot" "$install/.payload"
    tar --warning=no-timestamp -xf "$incoming/project.tar" -C "$install/project"
    tar --warning=no-timestamp -xzf "$incoming/julia.tar.gz" -C "$install/julia"
    tar --warning=no-timestamp -xzf "$incoming/depot.tar.gz" -C "$install/depot"
    cp "$incoming/release.json" "$install/release.json"
    cp "$incoming/project.tar" "$incoming/julia.tar.gz" "$incoming/depot.tar.gz" "$install/.payload/"
    mv "$install" "$release"
    new_release=1
    LC_ALL=C "$release/julia/bin/julia" --startup-file=no --version
    chmod -R a-w "$release"
    new_release=0
fi

link_tmp="$root/.current-${commit}-$$"
ln -s "releases/$commit" "$link_tmp"
mv -Tf "$link_tmp" "$root/current"
REMOTE_INSTALL

printf 'verified immutable release %s:%s/releases/%s\n' \
    "$remote_host" "$remote_root" "$release_commit"
