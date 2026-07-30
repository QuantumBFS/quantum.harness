#!/bin/bash
# reproduce_local.sh <env|refs|paper|dmrg|gates|agates|replacement|direct|twod-canary|all>
# LOCAL reproduction block (see REPRODUCE.md). One Julia/MOSEK process at a
# time; 18 GiB scopes via systemd-run; ≥4 GiB free before each launch.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../../.." && pwd)"           # repo root
JENV="$ROOT/julia-env"
J() { # memory-scoped julia
  local CAP=$1; shift
  systemd-run --user --scope -q -p MemoryMax="$CAP" -p MemorySwapMax=0 \
    julia --project="$JENV" "$@"
}
guard() { [ "$(awk '/MemAvailable/{print int($2/1048576)}' /proc/meminfo)" -ge 4 ] \
  || { echo "mem-guard: <4G free"; exit 4; }; }
STAGE="${1:-all}"

do_env() {
  julia --project="$JENV" -e 'using Pkg; Pkg.instantiate(); using JuMP, Mosek, MosekTools; println("env OK")'
  # seam sha check fails loudly if QMBCertify drifted
  J 4G "$HERE/cg_hybrid/gsb_cg.jl" --selftest 2>/dev/null || \
    J 4G -e "include(\"$HERE/cg_hybrid/gsb_cg.jl\"); println(\"seam sha OK\")"
  J 6G -t 2 "$HERE/cg_hybrid/tower.jl" /tmp/repro_tower_gates || true
}
do_refs()  { guard; J 6G "$HERE/bethe_ref.jl"; }
do_paper() { guard
  # RESULTS.md protocol cells (gate/step2/step3) + rdm=8 ladder — see
  # RESULTS.md §1 for the exact knob vectors; overnight_harness enforces
  # per-cell wall/RSS budgets.
  OUT="$HERE/../../results/repro-$(date +%Y%m%d-%H%M)"
  mkdir -p "$OUT"
  J 18G -t 2 "$HERE/overnight_harness.jl" "$OUT" step1 "gate:10:rdm=10,pso=3"
  J 18G -t 2 "$HERE/overnight_harness.jl" "$OUT" step23 \
    "step2_A:14:rdm=10,pso=3" "step2_B:14:rdm=false,pso=3" \
    "step3_C:14:rdm=10,pso=0" "step3_D:14:rdm=10,pso=3,lso=false"
  for N in 10 14 18 22 26 30 34 40; do guard
    J 18G -t 2 "$HERE/overnight_harness.jl" "$OUT" step4rdm8 "lad:$N:rdm=8,pso=3"
  done
  python3 "$HERE/make_results_md.py" "$OUT" || true
}
do_dmrg()  { guard; J 8G -t 4 "$HERE/dmrg_ref_j1j2.jl"; }
do_gates() { guard; cd "$HERE/rg_selection"
  for G in g1 g2 g3 g4 vcheck g4b; do guard
    J 19G run_small.jl "$G" || { echo "gate $G FAILED"; exit 1; }
  done }
do_agates() { guard; cd "$HERE/rg_selection"
  for ST in r123 r4bauto r4bpool r4bverdict; do guard
    J 18G release_gates.jl "$ST"; done }
do_replacement() { guard; "$HERE/rg_selection/run_replacement.sh"; }
do_direct() { guard
  "$HERE/rg_selection/direct/run_direct.sh"
  "$HERE/rg_selection/direct/run_ext.sh"
  ( cd "$HERE" && python3 figs/make_figs.py )
}
do_twod()  { guard
  OUT="$HERE/../../results/repro2d-$(date +%Y%m%d-%H%M)"; mkdir -p "$OUT"
  systemd-run --user --scope -q -p MemoryMax=6G julia --project="$JENV" -t 2 \
    -L "$HERE/hpc/2d/resort_patch.jl" "$HERE/overnight_harness.jl" "$OUT" t2d \
    "c2d_L4:4:model=heis2d,extra=0,rdm=8,pso=0,lso=false"
}

case "$STAGE" in
  env) do_env;; refs) do_refs;; paper) do_paper;; dmrg) do_dmrg;;
  gates) do_gates;; agates) do_agates;; replacement) do_replacement;;
  direct) do_direct;; twod-canary) do_twod;;
  all) do_env; do_refs; do_paper; do_dmrg; do_gates; do_agates
       do_replacement; do_direct; do_twod;;
  *) echo "usage: $0 env|refs|paper|dmrg|gates|agates|replacement|direct|twod-canary|all"; exit 2;;
esac
echo "LOCAL stage '$STAGE' done"
