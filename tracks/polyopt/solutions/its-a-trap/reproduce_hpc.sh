#!/bin/bash
# reproduce_hpc.sh <ship|t1ladder|t2sweep|twod|n200frontier>
# HPC reproduction block (SCNet-tested; see REPRODUCE.md §2). Set REMOTE to
# your cluster ssh alias. Templates assume: julia at $HOME/julia, Mosek at
# $HOME/mosek (+license), repo mirrored at $HOME/qh-method, CPU partition
# with >=3.8 GB/core (size jobs by --cpus-per-task, no --mem).
set -eu
REMOTE="${REMOTE:-scnet}"
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../../.." && pwd)"
STAGE="${1:?usage: $0 ship|t1ladder|t2sweep|twod|n200frontier}"

case "$STAGE" in
ship)
  # mirror the repo (cluster git too old for -C/worktrees; provenance via sha256)
  rsync -az --delete --exclude '.git' --exclude 'tracks/*/results' \
    "$ROOT/" "$REMOTE:qh-method/"
  ( cd "$ROOT" && git rev-parse HEAD ) | ssh "$REMOTE" 'cat > qh-method/SNAPSHOT_COMMIT.txt'
  scp -q "$HERE"/hpc/submit.sbatch "$HERE"/hpc/2d/*.sbatch "$REMOTE:~/"
  echo "shipped; verify: ssh $REMOTE 'cd qh-method && sha256sum tracks/polyopt/solutions/its-a-trap/cg_hybrid/gsb_cg.jl'"
  ;;
t1ladder)
  # T1 table cells: v50..v140 (CONFIG A) + v100e8 (extra=8) + v14 fingerprint.
  # hpc/cells.txt carries the cell specs; the array driver enforces budgets.
  ssh "$REMOTE" 'cd ~ && sbatch --array=1-12%4 submit.sbatch qh-method tracks/polyopt/solutions/its-a-trap/hpc/cells.txt'
  ;;
t2sweep)
  ssh "$REMOTE" 'cd ~ && sbatch --array=13-18%3 submit.sbatch qh-method tracks/polyopt/solutions/its-a-trap/hpc/cells.txt'
  ;;
twod)
  for T in canary_L4 probe_L6 probe_L8; do ssh "$REMOTE" "sbatch ~/$T.sbatch"; done
  # 10x10 cells (reconstructed spec of the frozen rows):
  ssh "$REMOTE" 'cd qh-method && echo "use overnight_harness cellspecs: \
c2d10_j02:10:model=j1j2sq,J2=0.2,extra=4,rdm=10,pso=0,lso=false and \
c2d10_j05:10:model=j1j2sq,J2=0.5,... with julia -L resort_patch (64c, ~230G)"'
  ;;
n200frontier)
  echo "NOTE: this stage reproduces a FRONTIER, not a bound. Expected outcomes:"
  echo "  - CONFIG A N=200: construction exceeds ~11.7 h without starting a solve"
  echo "  - V_{S*}(200) 64c: 6 h template TIMEOUT at ~182 GB"
  echo "  - 128c probe:      6 h template TIMEOUT at ~174 GB, still in construction"
  ssh "$REMOTE" 'cd ~ && sbatch --hold n200_probe.sbatch && sbatch --hold n200_pair.sbatch && squeue -u $USER'
  echo "release with: ssh $REMOTE 'scontrol release <jobid>' when you accept the wall budget"
  ;;
esac
echo "HPC stage '$STAGE' dispatched"
