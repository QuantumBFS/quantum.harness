# Tractability and symmetry reduction

The γ-feasibility hierarchy is memory-bound: the cost is dominated by the
positive moment PSD cone, scaling roughly as Σ(sideᵢ³). Symmetry reduction is
not cosmetic here — it is the difference between "intractable on any available
node" and "solves in seconds on one CPU". This file documents the before/after
dimensions for each reduction we use, and why the full-spin isotypic route is
the reason Square Rung C becomes hopeful.

All numbers are read from harvested evidence (cited per row).

---

## 1. Square J1-J2 track — the resource ladder

| Stage | Positive side(s) | Moments / vars | Peak RSS | Solve wall | Affordability |
|---|---|---:|---:|---:|---|
| **Rung A** (`bare_weight_one`, L=1 d=2) | 28 (+ gap 4) | 352 | 0.62 GiB | 1.4 s | trivial |
| **Rung B unsymmetrized** (`bare_operator`) | 352 (+ gap 4) | 12,826 | >250 GiB est.; 0 IPM iters on 499 GiB node | — | **intractable** |
| **Rung B + D4 quotient** | 70, 24, 45, 45, 168 | 12,826 → **1,831** | **86.5 GiB** | **28 min** | tractable on a 499 GiB / 32-core node |
| **Rung C, D4-only** (`one_symbol_lift`) | 139, 48, 90, 90, 336 | 703 / gap 7 | **295–347 GiB** est. (Σside² = 3.99× Rung B) | — | **intractable** (scnet2 Gate 0, job 118169776) |
| Rung C, D4 + E-partner (unimplemented) | 139, 48, 90, 90, 168 | — | 129–152 GiB est. | — | still over scnet2 budget |
| **Rung C, full-spin isotypic** *(measured, γ=2)* | max **45** (9 cones) | 74,602 → **3,250** | **~1.17 GiB** | feasible (OPTIMAL) | affordable; too weak at d=2 |

Sources: Rung A `result.toml` (job 22994039); Rung B+D4 `result.toml` (jobs
23005746 / 23006792); Rung C D4-only sizing
`evidence/square-rungc-d4-sizing-118169776/`; Rung C spin solve + exact
rational witness `evidence/square-spin-rungc-isotypic-20260729/` (job 118171150;
identical reduced inventory to SS / triangular).

**The headline contrast:** for Square Rung C, D4-only estimates **295–347 GiB**
while the full-spin isotypic reduction is expected at **~1 GiB** — roughly a
**300× memory reduction**, which moves the problem from "no available node can
run it" to "runs in seven seconds". That asymmetry is why the spin port is the
deadline-compatible route and D4-only Rung C was stopped.

### D4 quotient detail (Rung B, measured)

| Irrep | A1 | A2 | B1 | B2 | E |
|---|---:|---:|---:|---:|---:|
| Cone side | 70 | 24 | 45 | 45 | 168 |

Moment-orbit histogram: 10 orbits of size 1, 30 of size 2, 393 of size 4, 1398
of size 8 → 1,831 quotient variables (85.7% reduction from 12,826). Exact
coefficient gates all pass (off-block ‖·‖∞ = 0); transcript
`evidence/d4-coefficient-gates-5f79c93/`. Note: the E cone is currently emitted
at side `2 n_E = 168` rather than the Schur-optimal `n_E = 84`; this is an
efficiency gap, not a correctness defect (the larger cone is exact).

---

## 2. Shastry-Sutherland track — the six-layer spin reduction

One source assembly (positive 703 / gap 7, 74,602 moments) reduced through six
exact layers to a 3,250-variable, max-side-45 model. Every layer is an exact
congruence/isotypic operation verified by a truth gate on the actual
coefficients (not merely a symmetry argument).

| Stage | Moments | Max PSD side | Packed real PSD entries |
|---|---:|---:|---:|
| Source assembly | 74,602 | 703 | — |
| 1. V4 spin-rotation + gap facial reduction | 19,108 | 109 | — |
| 2. Computational-basis conjugation (realification) | 16,660 | 109 | 31,810 |
| 3. Order-two spin-axis involution | 8,803 | 81 | 16,707 |
| 4. Full spin-axis-permutation quotient | 3,250 | 81 | 16,707 |
| 5. Redundant nontrivial-character cone removal | 3,250 | 73 | 10,064 |
| 6. Trivial-character S3 isotypic split | 3,250 | **45** | **6,104** |

Reduced solve (γ=1): **1.17 GiB** peak RSS, **7.2 s** wall (2.0 s
solver-reported, 5 IPM iterations, MU→4.7e-12), 16 threads — job 23009024.
Source: `points/gamma-1/input/runmeta.toml` + `solve/result.toml`.

Optional further layer (not used in the headline solve): a single spatial
reflection (anti-diagonal `(x,y)→(−y,−x)`) would take the SS model to **1,711
moments, max side 24, 3,191 entries** — a robustness/performance gain, not
needed for tractability.

### 2a. Triangular J1 Heisenberg — a third model, identical inventory

The triangular-lattice Heisenberg AFM (3 NN bonds, J1=1, J2=0) was ported through
the *same* six-layer spin reduction as a **portability control** (issue #88's
triangular target is J1-J2 at g=0.10, 0.12 and is not addressed here). Because
the reduced inventory is set by the patch + basis + SU(2) spin action (not the
bond geometry), triangular lands on the **identical** reduced model: **3,250
moments, 9 cones, max side 45, 6,104 entries**, and solves at **~1.16 GiB / ~9
s** (γ=1, job 23012955). All six truth gates pass on the actual triangular
coefficients. This confirms the reduction's model-generality on a third geometry
and extends the "spin reduction makes the stronger relaxation tractable" result
beyond the square/SS lattices.

---

## 3. Why the spin reduction transfers to Square J1-J2

The six-layer SS reduction is **model-generic**: it operates on the primal
assembly and basis rows, with no Shastry-specific dispatch. It transfers to
Square J1-J2 because:

1. **The symmetry is exact.** Each Square bond `S_i·S_j = (X_iX_j+Y_iY_j+Z_iZ_j)/4`
   is invariant under global proper spin rotations — in particular the 24-element
   signed-axis rotation group (Klein V4 ⋊ S₃) the pipeline uses — and the
   computational-basis conjugation is valid (every `YY` term has two Y factors).
2. **Same patch/basis/L/d.** Both use the 3×3 patch, L=1, d=2, `one_symbol_lift`
   v1, giving identical source dimensions (703 / 7 / 74,602).
3. **It fails closed.** The builder tests, over exact arithmetic, Hamiltonian
   invariance, per-coefficient covariance, moment-inventory closure,
   equality-row invariance, exact cross-block zeros, row-basis ranks, cone
   congruence, the `W=3M` isotypic relation, two deterministic coefficient
   builds, and optimizer-free JuMP reconstruction. A hidden Square
   incompatibility stops the build rather than silently shrinking the SDP.

Mathematically the route is an **exact reparameterization of the finite
relaxation** (convex F, spin-stable constraints ⇒ averaging preserves
feasibility). It does not turn finite-relaxation feasibility into a physical
bulk-gap lower bound, and a solver infeasibility remains only a candidate until
independently certified.

---

## 4. What the reductions do *not* change

All reductions here are **feasibility-equivalent reparameterizations of the
declared finite relaxation**, not restrictions to a physical symmetry sector
and not strengthenings of the relaxation. They change the *cost* of solving a
given (L, d) level; they do not change *whether* that level bounds the gap. The
L=1/d=2 level is feasible across all tested γ for both Square (Rung B) and SS,
so it is too weak regardless of how cheaply it solves. The path to an actual
bound is a **stronger relaxation** — Square Rung C (spin port) or SS L=2 —
which is exactly the in-flight work.
