# LITERATURE_CONTRACT — coarse-grained NPA/RDMT for challenge #49

Literature-to-architecture analysis only. No code was modified. This document
is the contract between the three source papers and any future implementation
in this repository.

**Sources (all statements below cite one of these):**

| ref | paper | where read |
|---|---|---|
| [K] | Kull, Schuch, Dive, Navascués, PRX **14**, 021008 (arXiv:2212.03014) | `.knowledge/.../2212.03014_*.md`, §II-C/D/E, §III-A, §III-D-1/2, §IV-A/C; Eqs. (33)–(42) read from rendered equation images |
| [B] | *Coarse-grained Bootstrap of Quantum Many-body Systems*, JHEP 02 (2026) 222 (arXiv:2412.07837) | `.knowledge/.../2412.07837_*.md`, §2.2–2.3, §3.1–3.3, §4.1 |
| [W] | Wang et al., *Scalable Ground-State Certification…* (arXiv:2604.01555) | `.knowledge/.../2604.01555_*.md`, §4.1–4.2, §5.1–5.2 |
| — | arXiv:2602.21468 | **Physics controversy reference for 2D J₁–J₂ only** (unsupervised phase discovery; NOT a polyopt methods paper). Not used here. |

QMBCertify at commit `be63c27ece7322effe6d95c69ce6c3c5d8d92c14` (unmodified).
Measured numbers cite `tracks/polyopt/results/overnight-20260728-004512/results.csv`.

---

## 0. Pre-work audit: the "N≈28 wall" claim (required before anything else)

Claim as previously stated: *"rdm=8 does NOT satisfy the challenge's 1e-5
target beyond N ~ 28."*

Audit against `results.csv` (step4rdm8 rows), under **both** references:

| N | dev vs Table3-New | dev vs DMRG |
|---|---|---|
| 26 | −8.696e−06 | −9.396e−06 |
| 30 | −1.084e−05 | −1.224e−05 |

- The crossing of |dev| = 1e−5 is **bracketed in [26, 30]** under both
  references. "N≈28" is linear-interpolation cosmetics with no functional-form
  justification; the bracket is the honest statement. **Deprecated wording:**
  "N≈28 wall". **Replacement:** "|dev| < 1e−5 at N ≤ 26 and ≥ 1e−5 at N ≥ 30".
- Status caveat: 7/8 cells terminated `SLOW_PROGRESS`, not `OPTIMAL`. Measured
  duality gaps were ~1e−11 — six orders below the 1e−5 threshold — so the
  bracket is robust to the uncertified solver status; the *individual digits*
  beyond ~1e−9 are not.
- The bracket is a property of the **rdm=8, r=5, d=4, pso=3, lso=true**
  configuration on this machine, not of "RDM positivity" in general.

---

## A. Mathematical specification of the compressed RDMT/NPA hierarchy [K §III-D-2]

Setting: n qubits, 2-local Hamiltonian H = Σ_{i<j} h^(i,j) ∈ span(M†M).

### A.1 Level functionals L^(k)

A state is a positive linear functional. At level k, L^(k) is defined on
span(M_k† M_k) and required positive there: L^(k)(g†g) ≥ 0 ∀g ∈ span(M_k).
Consistency across levels (Eq. 33):

    Tr_{k+1}(L^(k+1)) := L^(k+1)|_span(M_k† M_k) = L^(k)

giving the hierarchy (Eq. 34):  L^(0) ← L^(1) ← L^(2) ← … ← L^(n).

### A.2 Level operator sets M_k (Eq. 36)

    M_k = { σ_a^(l) · Π_{j=1..k} σ_{b_j}^(j)  |  l > k,  a, b_j ∈ {0,x,y,z} }

i.e. a **full Pauli basis on spins 1…k, plus one floating spin l > k**.
Note this is NOT QMBCertify's contiguous-window basis [W §4.1]; the flow
singles out spins 1…k sequentially and **breaks translation covariance**.

### A.3 Coarse maps B_k and flows C_k (Eq. 35)

Pairwise coarse-graining maps B_(Q_{k−1},k)→Q_k act on (coarse system Q_{k−1},
physical spin k) and output Q_k. The cumulative flow is

    C_k = B_(Q_{k−1},k)→Q_k ∘ … ∘ B_(Q_2,3)→Q_3 ∘ B_(1,2)→Q_2 ,   C_1 := I

C_k maps states of spins (1…k) to states of Q_k; its adjoint C*_k maps
operators on Q_k to operators on spins (1…k) via C*(·) = Σ_i W_i†(·)W_i.

### A.4 Compressed operator spaces M′_k (Eq. 37) and compressed functionals Λ^(k) (Eq. 38)

    M′_k = { σ̃_q^(Q_{k−1}) σ_a^(k) σ_b^(l)  |  l > k,  a,b ∈ {0,x,y,z},
             q = 1 … dim(Q_{k−1})² }

where (σ̃_q^(Q_{k−1}))_q is an operator basis of Q_{k−1}. The compressed
functional Λ^(k) := C_{k−1}(L^(k)) acts on span((M′_k)† M′_k) by

    Λ^(k)( R^(Q_{k−1}) S^(k) σ_b^(l)† σ_{b′}^(l′) )
        := L^(k)( C*_{k−1}(R^(Q_{k−1})) · S^(k) σ_b^(l)† σ_{b′}^(l′) )

(evaluable because M_k contains a full basis on spins 1…k).

### A.5 Restriction maps Tr′_{k+1} (Eqs. 39, 41)

With the post-B_k monomial set

    M″_k = { σ̃_q^(Q_k) σ_a^(l)  |  l > k,  a ∈ {0,x,y,z}, q = 1…dim(Q_k)² },

M″_k ⊂ M′_{k+1}, and Tr′_{k+1} restricts:

    Tr′_{k+1}(Λ^(k+1)) := Λ^(k+1)|_span((M″_k)† M″_k)

### A.6 The commuting condition (Eq. 40 — the analogue of Eq. 18)

    B_(Q_{k−1},m)→Q_k ∘ C_{k−1} ∘ Tr_{k+1}  =  Tr′_{k+1} ∘ C_k

This is what makes the compressed constraints *consequences* of the
uncompressed ones (relaxation soundness). Any implementation must verify it
holds for the chosen maps — it is a testable identity on linear maps.

### A.7 Moment matrices and the final SDP (Eq. 42)

Each Λ^(k) is a vector **x**^(k) of values on a basis of span((M′_k)†M′_k);
its moment matrix is linear: Γ(Λ^(k)) = Σ_i x_i^(k) A_i^(k). B and Tr′ are
matrices **B**_k, **T**_{k+1} acting on **x**^(k), **x**^(k+1). The SDP:

    min  Λ^(2)(H)
    s.t. Λ^(2)(𝕀) = 1
         Γ(Λ^(k)) ⪰ 0                                  k = 2, …, n
         B_(Q_{k−1},k)→Q_k(Λ^(k)) = Tr′_{k+1}(Λ^(k+1))  k = 2, …, n−1

Variables: {**x**^(k)}_k — **one vector per level, coupled by inter-level
linear equalities**. Per-level size is polynomial (dim(Q)² × 4 × (n−k) × …)
once dim(Q_k) is capped; the theorem-level exponential in k is gone.

### A.8 Dual-shift certification [K §IV-A + §IV-C] (amendment 1)

Dual SDP (Eq. 44 schema): variables ε (normalization multiplier), λ_m
(inter-level constraint multipliers), X_m (Hermitian, for subspace/LTI-type
constraints); constraints are PSD conditions per level.

Rigorous-bound repair of a numerically infeasible dual point:
1. Sweep constraints **from the last level backwards**. For level m, compute
   e_m = min-eigenvalue of the constraint's LHS; replace λ_m ↦ λ_m − e_m·𝕀.
2. The shift propagates into the previous constraint through B*_m(𝕀).
   **If every B_m is trace non-increasing (B*_m(𝕀) ≤ 𝕀), the corrections at
   most add** and the final energy correction is Σ_m |e_m|-bounded.
3. For MPS-built maps, the trace-non-increasing property is obtained by
   putting the MPS in **left gauge** before constructing the maps.
4. The certified statement is "dual-feasible point ⇒ lower bound" — it needs
   only exact eigenvalue enclosures of modest-size matrices (Arblib-suitable),
   NOT an exact SOHS identity. This is the certification route for the
   coarse-grained SDP; it is structurally different from QMBCertify's
   `certify_qmb` (primal Gram projection), which the Step-5 audit showed
   cannot cover rdm/pso/lso constraints.

### A.9 Acceptance gate: explicit k = 2, 3 example (amendment 2)

Before any large run, the implementation must pass this hand-checkable gate
on the N = 6 Heisenberg ring (H = ¼ Σ_i Σ_a σ_i^a σ_{i+1}^a, E₀ known by ED):

1. **Enumerate M_2, M_3 by Eq. (36)** and assert the hand-counted dimensions:
   distinct monomials in M_2 = 16·(4·(N−2)/… ) — the code must expose its
   count and the contract reviewer recomputes it by the counting rule
   |{(b₁,b₂)}| × |{(l,a): l>2, a≠0}| + |{(b₁,b₂)}| (a=0 duplicates collapse);
   any mismatch fails the gate.
2. **Lossless oracle:** choose W: ℂ⁴ → ℂ^χ with χ = 4 unitary (B_(1,2)→Q_2
   lossless). Then Eq. (42) truncated at k = 3 must reproduce the uncompressed
   RDMT value (Eq. 31 with basis M_3) to ≤ 1e−8, and both must be ≤ E₀(ED).
3. **Commuting condition check:** verify Eq. (40) as a matrix identity for
   the chosen maps to machine precision before solving.
4. Only a run that logs all three assertions passes.

---

## B. Comparison with QMBCertify (commit be63c27)

### B.1 What exists and is reusable

| asset | file | reuse |
|---|---|---|
| Pauli-word canonicalization `reduce!`/`reduce4` | `basic_function.jl` | yes — evaluating C*_{k−1}(·) products of physical Paulis |
| `tsupp` sorted-support + `bfind` moment indexing | `bound_gsp.jl` | yes — for the Λ^(2)/physical layer |
| JuMP + Mosek scaffold, `mosek_para` tolerances | `bound_gsp.jl:227` | yes |
| symmetry machinery (translation, mirror, sign, conjugation) [W §4.2] | `bound_gsp.jl` | **partially** — see B.4/D.3; the sequential Q-flow breaks translation covariance |
| DMRG cross-check (ITensors) | deps | yes |
| exact-rational certification `certify_qmb` | `certification/` | **no** for the coarse-grained SDP (Step-5 audit: reads only GramMat[1..2]; RDM/pso blocks never exported; `qmb_data` has no field for them). Use [K §IV-C] dual-shift instead (A.8) |

### B.2 Required abstractions that are absent

1. **A sequence of functionals.** QMBCertify has exactly one functional — one
   `tsupp` moment vector, one monomial basis, one moment-matrix family. Kull
   Eq. (42) needs n coupled vectors **x**^(k) with different domains.
2. **Coarse-system bookkeeping.** Operators σ̃_q^(Q_k) live on virtual systems
   of dim(Q_k)², not on physical Pauli words; nothing in `qmb_data`
   (correlation1/2/3, basis, sbasis, tsupp, GramMat, sGramMat, multiplier,
   moment) can represent them.
3. **Inter-level linear maps as data.** **B**_k and **T**_{k+1} matrices and
   the equality constraints coupling levels do not exist anywhere.
4. **Hyperparameter input.** The MPS/isometry tensor W is an *input* of the
   relaxation (and the knob that tightens it); GSB has no such input.
5. **Dual-side certification.** `certify_qmb` is primal/SOHS; A.8 needs a
   dual-repair routine (min-eigenvalue sweeps + left-gauge check).

### B.3 Why this is NOT "a replacement of rdm=10"

- `rdm=k` (`posepsd8!/9!/10!`, `rdm_positivity.jl`) is a **strengthening
  inside the single-level relaxation**: it adds PSD multiplier blocks whose
  entries couple to *existing* moments via `bfind(tsupp, …)`. It creates no
  new moment variables and no new levels.
- Kull's scheme changes the **variable structure**: new per-level vectors,
  new moment matrices, new inter-level equalities. The compressed functionals
  cannot be expressed through the existing `tsupp` moments — the boundary
  contraction with W is what defines them.
- Mechanically: the rdm path is three hand-unrolled routines with hard-coded
  U(1) block index lists (sizes C(8,j), C(9,j), C(10,j)); there is no "k as a
  parameter" abstraction to swap out.
- Therefore the integration is a **new constraint/variable family added
  beside** the existing machinery, not a drop-in replacement of `rdm=10`.

### B.4 The 255× cost, as a double ledger (amendment 3)

Measured (overnight run, N-independent): rdm=10 construction 2029.6 s;
rdm=8 construction 7.96 s → **255.0×**.

Code fact (`rdm_positivity.jl`): `posepsd{k}!` loops over **all 4^k Pauli
index tuples**; each surviving tuple materializes a **dense 2^k × 2^k
Kronecker product** (`kron(Pauli[ind.+1]...)`), then slices it into the U(1)
blocks. Cost model ∝ 4^k (tuples) × 4^k (dense entries) = **16^k**, giving
16¹⁰/16⁸ = **256** — matching the measured 255.0 to 0.4%.

| ledger side | factor | who pays it |
|---|---|---|
| theorem-level | ~16× = 4¹⁰/4⁸ — the k-site Pauli-basis data itself (emitted scalarized PSD entries grew 62,384/4,524 = 13.8×) | **any** implementation of k-site RDM positivity |
| implementation-level | ~16× — dense Kronecker materialization per tuple; a Pauli word is a monomial matrix (one nonzero per row), so this factor is removable by direct sparse element generation | this code path specifically |

**Non-claims (mandated):** coarse-graining does **not** automatically
accelerate the present rdm=10 construction. It replaces exponential-in-k
objects with fixed-size coarse blocks — a different constraint family. The
implementation-level 16× above is an orthogonal engineering fix (sparse Pauli
element generation) and must not be attributed to coarse-graining. Any speed
claim must state which ledger line it addresses.

---

## C. Comparison with arXiv:2412.07837 [B]

### C.1 Which constraints it coarse-grains

Representation: density matrices (state picture), not functionals.
ρ₂, ρ₃ kept **uncompressed**; ω_M := C(ρ_M) for M = 4…N with a fixed uMPS
tensor B (bond dim m), each ω_M of constant dimension (d·m·m·d)².
Coarse-grained constraint families:

1. **LTI conditions** (§2.3, = Kull §II);
2. **Equations of motion** ⟨[H,O]⟩ = 0 via the on-site product ⊙ (§3.1–3.2)
   — the analogue of QMBCertify's `lso`;
3. **Perturbative positivity** C_ij = ⟨O_i†[H,O_j]⟩ ⪰ 0 (EEB at β→∞, §3.3)
   — the analogue of QMBCertify's `pso`;
4. **Thermal (EEB/KMS) matrices** at finite β (out of scope for #49).

The correspondence {LTI, EOM, PP} ↔ {marginal consistency, lso, pso} means
[B] has already demonstrated coarse-graining of precisely the constraint
families QMBCertify's strengthenings implement.

### C.2 How its implementation differs from Kull Eq. (42)

| | Kull Eq. (42) (RDMT picture) | [B] §2.3/§3 (state picture) |
|---|---|---|
| variables | functionals Λ^(k) on growing composites (Q_{k−1},k,l,l′) | ρ₂, ρ₃ + fixed-size ω_M |
| levels | n coupled levels, each its own basis M′_k | one ω per window M, all same shape |
| translation invariance | broken by the sequential Q-flow | **kept** (uniform MPS, LTI constraints) |
| maps as SDP data | **B**_k, **T**_{k+1} matrices per level | one tensor B contracted graphically |
| status | proposed, explicitly unimplemented ("we leave the implementation … for future work", §III-D-1 end) | implemented; numbers published |

Reach reported in [B] Table 1 (TFIM, m = 2): energy-only N≲10 → **N∼100**
with CG; with PP (two-sided bounds on any local observable) N≲5 → **N∼20**.
Observed accuracy plateau attributed to Mosek double precision or m = 2.

### C.3 Simpler prototype path?

**Yes.** [B] Eq. (2.17) is a complete, closed SDP specification with
fixed-size blocks and no per-level basis bookkeeping; it keeps translation
invariance, so [W §4.2.4] translation replacement rules remain meaningful;
and its EOM/PP extension (§3) maps 1:1 onto the lso/pso concepts we already
measure. The pragmatic prototype is a **standalone JuMP script implementing
(2.17)** (later (3.x) for EOM/PP), validated against the A.9 gate — not an
in-place extension of GSB.

---

## D. Minimal implementation proposal (staged; gates are blocking)

**Stage 0 — lossless coarse-graining oracle (A.9 gate).**
N = 6–8 ring, k ≤ 3 levels, W unitary (χ = 4). Assertions: hand-counted basis
dims; Eq. (40) as matrix identity; compressed value = uncompressed value to
1e−8; both ≤ E₀(ED). Also run the [B]-(2.17) form with lossless B and assert
equality with the ρ-picture uncompressed SDP.

**Stage 1 — lossy monotonicity tests.**
- χ (or m) descending with **nested isometries** W_χ₁ ⊂ range(W_χ₂):
  bound(χ₁) ≤ bound(χ₂) ≤ uncompressed bound ≤ E₀. Nestedness is required for
  guaranteed monotonicity; un-nested maps get an expected-but-not-guaranteed
  annotation, never an assertion.
- VUMPS-tensor heuristic [K §II-E, B §3.2] enters here as a *choice of W*,
  compared against random isometries.
- Every run logs the full provenance row schema of the overnight harness.

**Stage 2 — only after Stages 0–1 pass: integrate [W] structure exploitation.**
- Survives coarse-graining directly: Pauli algebra equalities (physical
  layer), conjugation/realification [W §4.2.3], sign symmetries if W is
  chosen sign-covariant.
- Translation/mirror [W §4.2.4/4.2.6]: only in the state picture ([B]/Kull-II
  route); the sequential RDMT flow forfeits them — this is a deciding
  argument for prototyping in the state picture.
- Certification: implement the A.8 dual-shift repair (left-gauge check,
  backward min-eigenvalue sweep, Arblib enclosures). `certify_qmb` is not a
  candidate (B.1).

**Explicit non-claims carried into all stages:** no claim that rdm=10 is
accelerated (B.4); no claim about challenge targets (N = 200 @ 1e−5) until a
Stage-2 N-ladder with provenance exists; "N≈28" wording retired (§0).
