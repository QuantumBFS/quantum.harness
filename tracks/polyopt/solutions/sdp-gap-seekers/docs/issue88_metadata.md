# Issue #88 per-calculation metadata

Every calculation the submission presents must carry the eight fields issue #88
requires. Below, each completed calculation is a self-contained block; two
in-flight calculations (Square Rung C via full-spin isotypic; SS L=2) have
skeleton slots at the end. Certification language is strict: a feasible
numerical solve never counts as a certified gap bound.

All solves used **Mosek 11.2.0** via **JuMP 1.31.1 / MathOptInterface 1.51.2**
on **Julia 1.11.5**, on **SCNet** (scnet1, xh5 cluster, partition
`xhacnormalb`). The Rung C sizing gate ran on scnet2 (Kunshan, `kshcnormal`).

Common Hamiltonian convention for the Square calculations:
`H = (1/4)Σ_J1(XX+YY+ZZ) + (g/4)Σ_J2(XX+YY+ZZ)`, antiferromagnetic `J1=1`,
`g = J2/J1 = 1/2`, on a 3×3 local-consistency patch Λ₁={−1,0,1}² with one inner
site, nine outer sites, and no physical boundary condition.

---

## S-RA — Square J1-J2, Rung A (`bare_weight_one`), L=1, d=2

| Field | Content |
|---|---|
| **Model** | Square J1-J2 Heisenberg, J1=1, g=1/2 (see convention above). |
| **Restrictions** | **Unrestricted.** No symmetry quotient (`state_symmetry = none_unrestricted`); no conserved-sector projection. |
| **Relaxation** | L=1, d=2; positive/gap basis family `bare_weight_one` v1 (dimensions 28/4); stationarity equalities = all bare Pauli operator words through degree 2d−2 on the inner patch. |
| **Size** | Positive PSD cone side **28**, gap PSD cone side **4**; **352** moment variables; **3** stationarity equalities; 2 Hermitian PSD cones. |
| **Solver** | Mosek 11.2.0; termination `OPTIMAL`, primal `FEASIBLE_POINT`, dual `FEASIBLE_POINT`, raw `MSK_SOL_STA_OPTIMAL`. |
| **Cost** | γ=0: solve **1.4 s** wall (0.33 s solver-reported), **0.62 GiB** peak RSS, 4 threads, node a02r02n08 — job **22994039**. |
| **Gap result** | **Not certified / not produced.** OPTIMAL-feasible at γ ∈ {0, ¼, 2}; the relaxation excludes no γ, so it cannot upper-bound the spectral gap. |
| **Observable result** | Not produced (feasibility-only target). |

γ-scan evidence: `evidence/square-conic-rung-a-validate-22994039/` (γ=0),
`evidence/square-rung-a-gamma-0p25-22991825/` (γ=¼),
`evidence/square-rung-a-gamma-2-22992596/` (γ=2).

---

## S-RB-D4 — Square J1-J2, Rung B (`bare_operator`), L=1, d=2, D4-quotiented

| Field | Content |
|---|---|
| **Model** | Square J1-J2 Heisenberg, J1=1, g=1/2 (see convention above). |
| **Restrictions** | **Unrestricted relaxation, exactly reparameterized by D4 averaging.** The D4 (point-group) block-diagonalization is a group-averaging equivalence of the *finite relaxation*, not a restriction to a physical symmetry sector. Exact coefficient gates: Hamiltonian D4-invariant ✓, basis D4-closed ✓, block-diagonal verified ✓, max off-block ‖·‖∞ = 0. |
| **Relaxation** | L=1, d=2; positive/gap basis family `bare_operator` v1 (352/4). |
| **Size** | Unreduced: positive side **352**, gap side **4**, **12,826** moments. **D4 moment-orbit quotient: 12,826 → 1,831 variables.** 5 positive PSD blocks A1=70, A2=24, B1=45, B2=45, E=168 (the E block is the unsplit side-2n_E form; exact but redundant). |
| **Solver** | Mosek 11.2.0; termination `OPTIMAL`, primal/dual `FEASIBLE_POINT`, raw `MSK_SOL_STA_OPTIMAL`. |
| **Cost** | γ=0: solve **1,702 s** (~28 min), **86.5 GiB** peak RSS, 32 threads, node a02r04n02 — job **23005746**. γ=¼: 1,484 s, 87.4 GiB — job 23006792. γ=0.40 — job 23006706. γ=2 — job 23006793. |
| **Gap result** | **Not certified / not produced.** OPTIMAL-feasible at γ ∈ {0, ¼, 0.40, 2}; excludes no γ. (Rung B unsymmetrized is the same feasibility problem but intractable: >250 GiB estimated, 0 IPM iterations observed on a 499 GiB node.) |
| **Observable result** | Not produced (feasibility-only target). |

γ-scan evidence: `evidence/square-d4q-rungb-gamma{0-23005746,0p40-23006706,1p4-23006792,2-23006793}/`.
D4 gate transcript: `evidence/d4-coefficient-gates-5f79c93/`. Equivalence proof:
`notes/d4-averaging-lemma.md`.

---

## SS-L1 — Shastry-Sutherland, L=1, d=2, full-spin isotypic reduction

| Field | Content |
|---|---|
| **Model** | Shastry-Sutherland; dimer/plaquette ratio `g_square/dimer = 4/5` (0.8). Same 3×3 local-consistency patch, L=1, d=2, basis `one_symbol_lift` v1. |
| **Restrictions** | **Unrestricted relaxation, exactly reparameterized by a six-layer spin reduction:** V4 spin-rotation + gap facial reduction → computational-basis conjugation (realification) → order-two spin-axis involution → full spin-axis-permutation moment quotient → redundant nontrivial-character cone removal → trivial-character S3 isotypic split. Exact-equivalent reparameterization, not a physical spin-sector restriction. Every layer passes an exact truth gate on the actual coefficients. |
| **Relaxation** | L=1, d=2; `one_symbol_lift` v1. |
| **Size** | Source: positive **703**, gap **7**, **74,602** moments, 3 stationarity equalities. **Reduced: 3,250 variables, 9 real PSD cones** (positive sides 36,36,36,45,37,36,36,45 + gap side 1), **max side 45, 6,104 packed triangle entries.** |
| **Solver** | Mosek 11.2.0; termination `OPTIMAL`, primal/dual `FEASIBLE_POINT`, raw `MSK_SOL_STA_OPTIMAL`. |
| **Cost** | γ=1: solve **7.2 s** wall (2.0 s solver-reported, 5 IPM iterations, MU→4.7e-12), **1.17 GiB** peak RSS, 16 threads, node a01r04n07 — job **23009024**. Residual audit: max affine-equality residual 0.0, worst PSD violation 0.0. |
| **Gap result** | **Not certified / not produced.** OPTIMAL-feasible at γ ∈ {½, 1, 2, 4} (½ is Sihan's exact-rational witness; 1, 2, 4 from this scan); excludes no γ, so the L=1/d=2 relaxation cannot upper-bound the SS gap. |
| **Observable result** | Not produced (feasibility-only target). |

γ-scan evidence: `evidence/ss-g4p5-scan-20260729-23009024/` (γ=1,2,4; branch
`f1fb24c`). Source reduction module:
`scripts/build_shastry_sutherland_full_spin_isotypic_reduced_mof.jl`.

---

## TRI-L1 — Triangular J1 Heisenberg AFM, L=1, d=2, full-spin isotypic reduction *(portability control — NOT #88 target 3)*

| Field | Content |
|---|---|
| **Model** | Triangular-lattice spin-1/2 Heisenberg antiferromagnet, `H = Σ_<ij> S_i·S_j`, J1=1, **J2=0** (120° geometrically-frustrated order). 3 NN bond directions `(1,0),(0,1),(1,-1)` on the integer grid. Same 3×3 level-1 patch. **This is a J1-only portability control; #88 target 3 is triangular J1-J2 at g=0.10, 0.12 and is not addressed.** |
| **Restrictions** | **Unrestricted relaxation, exactly reparameterized by the same six-layer spin reduction ported from SS** (valid because the triangular Heisenberg Hamiltonian is globally spin-rotation invariant; same patch/basis). All six truth gates pass on the actual triangular coefficients. Not a physical spin-sector restriction. |
| **Relaxation** | L=1, d=2; `one_symbol_lift` v1. |
| **Size** | Source: positive **703**, gap **7**, **74,602** moments. **Reduced: 3,250 variables, 9 real PSD cones** (identical inventory to SS — the spin reduction is set by patch+basis+SU(2), not bond geometry), **max side 45, 6,104 packed entries.** |
| **Solver** | Mosek 11.2.0; termination `OPTIMAL`, primal/dual `FEASIBLE_POINT`, raw `MSK_SOL_STA_OPTIMAL`. |
| **Cost** | γ=1: solve **~9.6 s**, **~1.16 GiB** peak RSS (`peak_process_rss_kib = 1,216,676`), 16 threads — scan job **23012955**. Residual audit: max affine-equality residual 0.0, worst PSD violation 0.0. |
| **Gap result** | **Not certified / not produced.** OPTIMAL-feasible at γ ∈ {0, 1, 2}; excludes no γ, so the L=1/d=2 relaxation cannot upper-bound the triangular gap. Consistent with the square/SS results at d=2. |
| **Observable result** | Not produced (feasibility-only target). |

γ-scan evidence: `evidence/triangular-j1-scan-23012955/` (representative γ=1 `result-gamma-1.toml` + `runmeta-gamma-1.toml` + `slurm-23012955.out` scan log + source SHA-256s; run commit `d73545d`, job 23012955). Builder/solver: `scripts/build_triangular_full_spin_isotypic_reduced_mof.jl` + `solve_triangular_full_spin_isotypic_reduced_mof.jl`. The identical reduced inventory (3,250 / 9 cones / max side 45) across square/SS/triangular confirms the reduction transfers across all three geometries; only square J1-J2 and Shastry-Sutherland are #88 targets.

---

## S-RC-spin — Square J1-J2, Rung C (`one_symbol_lift`), L=1, d=2, full-spin isotypic

| Field | Content |
|---|---|
| **Model** | Square J1-J2 Heisenberg, J1=1, g=1/2. |
| **Restrictions** | **Unrestricted relaxation, exactly reparameterized by the six-layer spin reduction ported from SS** (valid because J1-J2 is globally spin-rotation invariant; same patch/basis as SS). Not combined with D4. |
| **Relaxation** | L=1, d=2; `one_symbol_lift` v1. |
| **Size** | Source: positive **703**, gap **7**, **74,602** moments. **Reduced: 3,250 variables, 9 real PSD cones, max side 45, 6,104 packed entries** (identical inventory to SS / triangular). |
| **Solver** | Mosek 11.2.0; termination `OPTIMAL`, primal/dual `FEASIBLE_POINT`. |
| **Cost** | γ=2: ~1.17 GiB peak RSS, node a07r3n19 — job **118171150**. An **exact rational feasible witness** at γ=2 (common denominator 10⁶, strictly positive exact LDL pivots in all 9 PSD blocks) corroborates the numerical result. Residual audit: max affine-equality residual 0.0, worst PSD violation 0.0. |
| **Gap result** | **Not certified / not produced.** OPTIMAL-feasible at γ ∈ {0, 2}; by monotonicity feasible on [0,2]; excludes no γ. The strongest single-site-window Square relaxation (Rung C) is still too weak at d=2. |
| **Observable result** | Not produced (feasibility-only target). |

This deadline-compatible spin-isotypic route supersedes D4-only Rung C (sizing
gate `evidence/square-rungc-d4-sizing-118169776/`, 295–347 GiB estimated, not
affordable). Evidence: `evidence/square-spin-rungc-isotypic-20260729/`.

---

## SS-L2 — Shastry-Sutherland, L=2, d=2  *(terminal — no feasibility status)*

| Field | Content |
|---|---|
| **Model** | Shastry-Sutherland, g_square/dimer = 4/5. |
| **Restrictions** | full-spin isotypic + on-demand SO(3) moment quotient + stabilizer split. |
| **Relaxation** | **L=2**, d=2 (stronger than the L=1 scan above). |
| **Size** | Preflight (job 118169520): positive basis **14,026**, gap **55**, stationarity **1,080**; moments after V4+conjugation pre-projection = **4,802,176**. After an exact SO(3) l=2 cone-congruence proof: **38 → 26 PSD blocks**, packed cone entries **2,540,067 → 1,600,017** (−37%), **max side 490**. |
| **Solver** | Mosek 11.2.0 — **exhausted memory during factor fill before iteration zero**. |
| **Cost** | factor-fill OOM; no solve completed. |
| **Gap result** | **Not produced / inconclusive** — model built, no feasibility status (resource failure). |
| **Observable result** | Not produced. |

---

## γ-feasibility summary (completed calculations)

Feasibility of the γ-relaxation `F(γ)` at each tested γ. A gap *upper bound*
requires an **infeasible** `F(γ)` (excluding that γ). "Feasible at all tested γ"
⇒ the relaxation is too weak to bound the gap at that level.

| Calculation | γ points tested | Result at each γ | Gap bound? |
|---|---|---|---|
| S-RA (Square Rung A) | 0, ¼, 2 | all OPTIMAL-feasible | No — too weak |
| S-RB-D4 (Square Rung B, D4) | 0, ¼, 0.40, 2 | all OPTIMAL-feasible | No — too weak |
| SS-L1 (SS, L=1, spin) | ½, 1, 2, 4 | all OPTIMAL-feasible | No — too weak |
| TRI-L1 (Triangular J1, spin) | 0, 1, 2 | all OPTIMAL-feasible | No — too weak |
| S-RC-spin (Square Rung C, spin) | 0, 2 | all OPTIMAL-feasible | No — too weak |

**Stronger-level attempts — terminal (no feasibility status, not pending).**
- *Square L=1/d=3* — exact cone-reduced MOF build completed (job `118201670`); **no solve was run**.
- *SS L=2/d=2* — see the SS-L2 section above: built, **Mosek factor-fill OOM before iteration zero**.
- *Square L=2/d=2* — **failed closed at an exact cone-redundancy gate**; no MOF or solve.

**Note on certification.** Every "feasible" above is a numerical OPTIMAL with a
Mosek `FEASIBLE_POINT`. Per the source method (arXiv:2606.03836) a solver
*infeasibility* is only a *candidate* until independently certified (exact
dual-infeasible / rational witness). No such transition has occurred yet, so no
row claims a certified bound. If S-RC-spin or SS-L2 returns an audited
infeasibility, that row — and only that row — becomes the headline.
