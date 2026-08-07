#!/bin/bash
# LOCAL: ship the working tree + refs + Mosek licence to SCNet.
# Ships the tree AS-IS (including uncommitted julia-env/harness edits) — this
# is deliberate and requires the operator to have okayed dirty-tree shipping
# (using-slurm binding rule). Excludes results/ and repo history.
set -eu
REPO="$(cd "$(dirname "$0")/../../../../.." && pwd)"
cd "$REPO"

# refs snapshot for the cells (bethe for Target 1, Table 4 for provenance)
mkdir -p tracks/polyopt/solutions/its-a-trap/hpc/refs
cp tracks/polyopt/results/targets-20260728-171149/bethe_ref.json \
   tracks/polyopt/solutions/its-a-trap/hpc/refs/
cp tracks/polyopt/solutions/its-a-trap/table4_refs.json \
   tracks/polyopt/solutions/its-a-trap/hpc/refs/ 2>/dev/null || true

echo "== rsync tree -> scnet:~/quantum.harness"
rsync -az --info=stats1 \
  --exclude '.git/' --exclude 'tracks/*/results/' --exclude 'results/' \
  --exclude '.knowledge/' --exclude '*.cov' \
  ./ scnet:quantum.harness/

echo "== rsync Mosek licence (HOSTID=DEMO, not machine-locked) + binaries"
# login node cannot reach download.mosek.com — ship the local linux64x86
# binary dir; bootstrap points MOSEKBINDIR at it
MSKBIN=$(dirname "$(cat "$HOME/.julia/packages/Mosek/"*/deps/mosekbindir | head -1)")/bin
ssh scnet 'mkdir -p ~/mosek'
rsync -az "$HOME/mosek/mosek.lic" scnet:mosek/mosek.lic
rsync -az "$MSKBIN/" scnet:mosek/bin/

echo "SHIP OK — next: ssh scnet 'bash quantum.harness/tracks/polyopt/solutions/its-a-trap/hpc/bootstrap_remote.sh'"
