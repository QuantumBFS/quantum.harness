#!/usr/bin/env bash
#SBATCH --job-name=occ71-f347-audit
#SBATCH --partition=home
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:15:00

set -euo pipefail

repo=/home/user_milksang/private/homefile/quantum_harness/issue71_occam
search="$repo/tracks/qcs/solutions/Genshin_Impact-71/search"
target="$repo/results/occam71/frontier-347"
stage="$target/.finalize-${SLURM_JOB_ID}"

cd "$repo"
mkdir "$stage"

publish_once() {
  src=$1
  dst=$2
  if test -e "$dst"; then
    cmp -s "$src" "$dst" || {
      printf 'refusing to replace different existing artifact: %s\n' "$dst" >&2
      exit 1
    }
    rm -- "$src"
  else
    mv "$src" "$dst"
  fi
}

for instance in A B C D; do
  python "$search/audit_arithmetic_formula.py" \
    "$instance" \
    "results/occam71/frontier-347/netlists/mystery-${instance}.txt" \
    --report "$stage/audit-${instance}.json"
  publish_once "$stage/audit-${instance}.json" "$target/audit-${instance}.json"
done

python "$search/make_frontier_manifest_v2.py" \
  "$target" \
  --expected-total 347 \
  --c-source 'eSLIM stage2 job 43188 task 3' \
  --c-synthesis 'relation-SAT cascade from C154, window size 7, root seed 42' \
  --output "$stage/manifest.json"
publish_once "$stage/manifest.json" "$target/manifest.json"

sha256sum \
  "$target"/netlists/mystery-{A,B,C,D}.txt \
  "$target"/audit-{A,B,C,D}.json \
  "$target"/manifest.json \
  > "$stage/SHA256SUMS"
publish_once "$stage/SHA256SUMS" "$target/SHA256SUMS"

manifest_sha=$(sha256sum "$target/manifest.json" | cut -d' ' -f1)
printf 'status=FRONTIER_347_COMPLETE\nmanifest_sha256=%s\n' "$manifest_sha" \
  > "$stage/COMPLETE"
publish_once "$stage/COMPLETE" "$target/COMPLETE"
rmdir "$stage"

sha256sum -c "$target/SHA256SUMS"
printf 'FRONTIER_347_COMPLETE\n'
