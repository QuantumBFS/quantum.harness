# REPRODUCE — how to regenerate every result in this solution

Two blocks: **LOCAL** (fits a 32 GB workstation under our 18 GiB
single-process law) and **HPC** (needs a cluster of the SCNet
xhacnormalb class: 128 cores / ~460 GB scopes). Every table in
`FINAL_REPORT.md` / `RESULTS.md` / `CAMPAIGN_REPORT.md` maps to one stage
below. Frozen originals live in the CSVs; a reproduction regenerates
fresh copies NEXT TO them (suffix or separate out-dir), never overwrites.

## 0. Environment manifest

| item | value |
|---|---|
| Julia | 1.12.6 (juliaup) |
| project | `julia-env/` at repo root — `julia --project=julia-env -e 'using Pkg; Pkg.instantiate()'` |
| QMBCertify | pinned, UNMODIFIED, at `.external/QMBCertify` commit be63c27 (keep chmod a-w) |
| MOSEK | 11.2 + valid license (`~/mosek/mosek.lic` or MOSEKLM_LICENSE_FILE) |
| solver seam | `cg_hybrid/gsb_cg.jl` sha-pins `bound_gsp.jl` (bc33d591…) — refuses to run on a drifted upstream |
| python3 | tables/figures only (no packages needed) |
| memory law | one Julia/MOSEK process at a time; `systemd-run --user -p MemoryMax=18G` scopes |
| tolerances | Mosek 1e-8; expect run-to-run drift ≤ ~1e-9 in bounds, ±20% in wall/RSS |

## 1. LOCAL block — `./reproduce_local.sh <stage>`

| stage | reproduces | wall (approx) | peak RSS |
|---|---|---|---|
| `env` | environment sanity + seam sha check + tower self-test | 5 min | <2 G |
| `refs` | Bethe battery (5-part gate, ED cross-check ≤1e-10), MG anchor | 10 min | <4 G |
| `paper` | RESULTS.md §2–3: gate/step2/step3 cells + rdm=8 ladder N=10–40 | ~3 h | ≤17 G |
| `dmrg` | T2 upper bounds (J2 sweep, N=100 PBC DMRG) | ~6 h | <8 G |
| `gates` | method gate chain G1→G2→(G3)→G4→vcheck→G4b (G3 exact enumeration is the long pole) | G1/G2/G4/vcheck ~1.5 h; G3 ~5–6 h | ≤19 G |
| `agates` | A200 release gates R1+R2+R3+R4b (staged, one solve/process) | ~25 min | ≤17 G |
| `replacement` | four-hour lock: build scan + mandatory 8 rows (B/C6/D/A × N=14,20; D rows hit the 18 G frontier BY DESIGN — expect OOM rows) | ~1.5 h | 18 G cap |
| `direct` | direct MVP gates + arms + N-extension (C/C4/D rows, wbundle, curve) + figures F2/F3 | ~1.5 h | ≤10 G |
| `twod-canary` | 2D L=4 canary vs exact torus ED (needs the resort patch, applied automatically) | ~5 min | <2 G |
| `all` | everything above in order | ~18 h | — |

Outputs land in the same CSV schemas as the frozen files; compare with
`diff` / the finalize scripts. Rows whose STATUS is a frontier marker
(OOM_18G_CAP, TIMEOUT, STRUCTURALLY_ABSORBED) are part of the result —
reproducing them means reproducing the marker, not a number.

## 2. HPC block — `./reproduce_hpc.sh <stage>` (SCNet-tested)

Prereqs on the cluster: julia at `$HOME/julia`, shipped Mosek at
`$HOME/mosek` with license, repo mirrored to `$HOME/qh-method` (rsync;
cluster git is too old for worktrees — provenance via sha256), CPU
partition with ≥3.8 GB/core (we used xhacnormalb: no `--mem` above
cpus×DefMemPerCPU; size by `--cpus-per-task`). No python3 on compute
nodes — checkers are Julia.

| stage | reproduces | resources | wall |
|---|---|---|---|
| `ship` | rsync the repo + sbatch templates to `$REMOTE` | login node | minutes |
| `t1ladder` | T1 table: v50–v140 (CONFIG A) + v100e8 (r=9) + v14 fingerprint | 32–64c / 120–240 G per cell (array) | 1–10 h/cell |
| `t2sweep` | T2 table: J2 ∈ {0.2…1.0} at N=100 | 32c / ~120 G per cell | 2–8 h/cell |
| `twod` | T3 probes L=6/L=8 + T4 10×10 j02/j05 (resort patch via `julia -L`) | 32–64c / 110–230 G | 1–2 h solve, 4–6 h wall |
| `n200frontier` | the N=200 frontier rows — EXPECT one-sided outcomes (construction >11.7 h; 6 h template TIMEOUTs at 174–182 G). Reproducing this stage = reproducing the frontier, not a bound | 64–128c / ≤460 G | 6–24 h |

Job templates: `hpc/submit.sbatch` (+ `hpc/cells.txt`),
`hpc/2d/{canary_L4,probe_L6,probe_L8}.sbatch`, `rg_selection`'s
`n200_probe/pair` templates. All results return via `rsync` of the
remote `results/` and merge through `overnight_harness`'s CSV append —
see `tracks/polyopt/results/scnet-final/` for the frozen layout.

## 3. What you should get

- Bounds match frozen CSVs to ≤1e-9 per site (solver determinism limit);
  structural counters (psd_scalars, rows, nnz, block dims) match EXACTLY.
- Gate verdicts (PASS/RED) are bitwise-stable except wall/RSS columns.
- The three figures regenerate byte-identically from the same CSVs
  (`python3 figs/make_figs.py`).
