# SDP Gap Seekers

> **TL;DR — what we did, what we found, why it's useful.** We attacked
> challenge #88: certify upper bounds on the bulk spectral gap of frustrated
> spin-1/2 models via the state-polynomial γ-feasibility SDP hierarchy
> (arXiv:2606.03836). At the smallest tractable relaxation level (L=1, d=2),
> **all three target models — square J1-J2, Shastry-Sutherland, triangular —
> are feasible at every γ we tested**, so that level is too weak to bound the
> gap. **No certified bound is claimed.** The contribution is **method +
> machinery**: an exact D4 quotient for the square lattice and a six-layer
> full-spin isotypic reduction that transfers *unchanged* across all three
> geometries, plus the tractability analysis that drops the Rung-C solve from
> ~295 GiB to ~1 GiB. Stronger levels (square L=1/d=3; Shastry-Sutherland L=2)
> are in flight and are the route to an actual bound. Read on for the strict
> certification language, two reproduction routes, and limitations.

## Team

| | |
|---|---|
| **Team name** | sdp-gap-seekers |
| **Members** | Xiansheng Cai (蔡贤盛), Sihan Hu (胡思寒) |

## Challenge

Certified bulk spectral-gap bounds for frustrated spin-1/2 models — compute
upper bounds on the locally non-degenerate bulk gap of infinite systems via the
state-polynomial γ-feasibility SDP hierarchy of arXiv:2606.03836.

Addresses #88 — released by Xiangling Xu (许湘灵) and Jie Wang (王杰), polyopt
track.

## Headline

A finite hierarchy level *upper-bounds* the bulk gap only when its γ-relaxation
is **infeasible** (excluding that gap threshold); feasibility excludes nothing.

**Current certified status: no bulk-gap upper bound has yet been produced.**
At the smallest tractable relaxation level (L=1, d=2) **all three #88 target
models are feasible at every tested γ**, so that level is too weak to bound the
gap:

| Model (L=1, d=2) | Reduction used | γ tested | Result | Gap bound |
|---|---|---|---|---|
| Square J1-J2 (g=½), Rung A | none (28/4) | 0, ¼, 2 | all OPTIMAL-feasible | — (too weak) |
| Square J1-J2 (g=½), Rung B | D4 quotient (352→5 blocks) | 0, ¼, 0.40, 2 | all OPTIMAL-feasible | — (too weak) |
| Square J1-J2 (g=½), Rung C | full-spin isotypic (703→max side 45) | 0, 2 | OPTIMAL-feasible (exact rational witness at γ=2) | — (too weak) |
| Shastry-Sutherland (g=0.8) | 6-layer full-spin isotypic (703→max side 45) | ½, 1, 2, 4 | all OPTIMAL-feasible | — (too weak) |
| Triangular J1 Heisenberg | 6-layer full-spin isotypic (703→max side 45) | 0, 1, 2 | all OPTIMAL-feasible | — (too weak) |
| Square J1-J2, L=1/d=3 *(in flight)* | full-spin isotypic + spatial reflection | *(pending)* | *(pending)* | *(pending)* |
| Shastry-Sutherland, L=2 *(in flight)* | dynamic full-state spin isotypic | *(pending)* | *(pending)* | *(pending)* |

The contribution so far is therefore **method + machinery**: an exact D4
quotient for the square lattice, a six-layer full-spin isotypic reduction that
transfers unchanged to all three geometries (Square, Shastry-Sutherland,
Triangular — they share the identical reduced inventory), and the tractability
analysis that makes the stronger relaxations affordable. Full per-calculation
metadata (the eight issue-#88 fields) lives in [`docs/issue88_metadata.md`](docs/issue88_metadata.md);
the tractability numbers in [`docs/tractability_reduction.md`](docs/tractability_reduction.md).

## Approach

The finite patch is a **local-consistency window**, not a periodic
finite-volume Hamiltonian. Each hierarchy level asks whether an infinite-volume
KMS ground state can have gap ≥ γ; finite-level infeasibility excludes that
threshold, finite-level feasibility does *not* prove gappedness.

Three target models, all spin-1/2, on the 3×3 level-1 patch:

- **Square J1-J2 Heisenberg**, `H=(1/4)Σ_J1(XX+YY+ZZ)+(g/4)Σ_J2(XX+YY+ZZ)`,
  J1=1, g=½.
- **Shastry-Sutherland**, dimer/plaquette ratio g_square/dimer = 4/5.
- **Triangular J1 Heisenberg** (120° geometrically-frustrated order), J1=1.

The decisive engineering step is **exact symmetry reduction** — feasibility-
equivalent reparameterizations of the finite relaxation (group averaging + exact
congruence/isotypic decomposition), verified by fail-closed truth gates over
exact arithmetic. They are *not* restrictions to a physical symmetry sector and
do not change what the relaxation bounds; they change what is tractable. The
headline contrast: Square Rung C needs **~295 GiB** with D4 alone but **~1 GiB**
with the full-spin isotypic reduction — the ~300× drop that makes the stronger
relaxations affordable on ordinary hardware.

## Reproduction

Two routes, as the submission requires.

### Route 1 — quick, solver-free, no SCNet, no Mosek licence

Validates the exact reductions and assembly structurally, without solving any
SDP. Runs in under a minute on a laptop.

```bash
# from the team directory, with the Julia environment active
julia --project=julia-env test/runtests.jl
# the exact spin-reduction truth chain (six layers, all coefficient gates)
julia --project=julia-env test/run_exact_symmetry_reduction_truth.jl
# the D4 coefficient gates for the square lattice (fail-closed)
julia --project=julia-env scripts/check_d4_coefficient_gates.jl
```

These check Hamiltonian invariance, basis closure, per-coefficient covariance,
moment-inventory closure, exact cross-block zeros, row-basis ranks, cone
congruence, and the `W=3M` isotypic relation — the same gates every harvested
solver run passed before Mosek was attached.

### Route 2 — full build + solve (SCNet + Mosek)

Reproduces the harvested γ-scan results. Requires SCNet access, Mosek 11.2,
Julia 1.11.5, and the pinned environment. The runners are parameterized by
environment variables (no hardcoded account or cluster path). Pinned versions,
the external SpectralGap source pin/patch, the SCNet resource allocations, and
exact per-calculation commands are enumerated in
[`docs/reproducibility.md`](docs/reproducibility.md).

```bash
# Square J1-J2 Rung B, D4-quotiented, γ-scan
sbatch scripts/square_conic_solve.sbatch           # CONIC_BUILD_SCRIPT selects the builder

# Shastry-Sutherland / Triangular, full-spin isotypic, γ-scan
sbatch scripts/shastry_sutherland_full_spin_isotypic_solve_xh5.sbatch
sbatch scripts/triangular_gamma_scan_xh5.sbatch
```

Each harvested run records its own `git commit`, `git tree`, source-file
SHA-256s, solver status, dimensions, runtime, and RSS under `evidence/<run>/`.

## Result language (strict)

Per the source method and the review discipline:

- `OPTIMAL` + `FEASIBLE_POINT` is a **numerical feasibility** statement, never a
  certified gap bound. It is reported as "not produced" with the reason
  (feasible at all tested γ ⇒ excludes no γ).
- A solver `infeasible` is only a **candidate** until independently certified
  (exact dual-infeasibility / rational ray replay). No such transition has
  occurred yet.
- No row in any table claims a certified bulk-gap bound unless it carries an
  audited infeasibility certificate.

## Limitations

- **No certified bound at d=2.** The L=1/d=2 level is feasible across all tested
  γ for all three models, so it is too weak regardless of how cheaply it solves.
- **Partial result.** This submission does not close #88. Stronger relaxations
  (Square L=1/d=3; SS L=2) are the route to an actual bound; both are in flight.
  L=2/d=2 is currently intractable to solve (max PSD side ~490 → Mosek
  factor-fill OOM).
- **D4 E-cone.** The Square D4 builder emits the E isotypic block at side `2 n_E`
  rather than the Schur-optimal `n_E`; exact but redundant (an efficiency gap,
  not a correctness defect).
- **Environment portability.** The Julia environment currently lives at the
  repo-root `julia-env/`; final packaging relocates a solution-specific project
  under the team directory and restores the shared root.

## Repository layout

```
tracks/polyopt/solutions/sdp-gap-seekers/
├── README.md                  # this file — start here
├── docs/                      # issue88 per-calc metadata, tractability, reproducibility
├── src/                       # CoreMGK, SquareGapConic, D4, ExactSymmetryReduction,
│                              # the FullSpin* isotypic reduction modules
├── scripts/                   # build_*_mof.jl builders, solve_*_mof.jl solvers,
│                              # check_d4_*.jl gates, *_xh5.sbatch runners
├── test/                      # solver-free exact truth gates (Route 1)
├── evidence/                  # harvested per-run result/runmeta/SHA256SUMS bundles
├── results/                   # generated MOFs, logs, plots (gitignored)
└── notes/
    ├── proofs/                # EXACT_*.md per-layer exact-reduction proof contracts
    │                          # + CHALLENGE88_RESULT.md (SS reduction-ladder result log)
    ├── specs/                 # Square/SS basis & model specs (SQUARE_BASIS_SPEC,
    │                          # square-j1j2-gap-sdp-spec, basis-counts, SS dimer gate)
    └── process/               # internal session / advisor / decision logs (working record,
                               # not part of the claimed result)
```

## Division of labor

- **Xiansheng Cai (蔡贤盛)** — Square J1-J2 (CoreMGK + SquareGapConic + the D4
  reduction, the Rung C full-spin isotypic port, the L=1/d=3 experiment);
  Triangular J1 port; the γ-scans; integration.
- **Sihan Hu (胡思寒)** — Shastry-Sutherland: the six-layer full-spin isotypic
  reduction, its exact truth gates, and the L=2 extension.
- Joint review on certification language and the final PR.
