# MPS-family methodology reference (DMRG · TEBD · VUMPS/IDMRG · TDVP)

Reproduction-grade algorithmic reference for the matrix-product-state (MPS) family, distilled
from the harness knowledge base in `.knowledge/literature/mps-based-algorithm/`. Companion to
`skills/method-mps/SKILL.md` — that card owns algorithm↔tool routing and the conversational
workflow; this file owns the *algorithms* (notation, equations, pseudocode, knobs, validation).

Math is UTF-8 unicode/plain throughout. Symbols are defined before use.

Primary sources (KB):
- Schollwöck 2010, *Ann. Phys.* 326, 96 — `1008.3477_*.md` (the central reference: SVD/canonical,
  MPO, DMRG, TEBD, iDMRG, iTEBD, transfer matrix). Section/equation numbers below are its.
- Orús 2013, *Ann. Phys.* 349, 117 — `1306.2164_*.md` (canonical form, Γ-Λ, correlation length).
- Zauner-Stauber et al. 2018, *PRB* 97, 045145 — `1701.07035_*.md` (VUMPS; A_C/C eigenproblems,
  gradient norm ‖B‖, FIG.7 benchmark).
- Vidal 2003, *PRL* 91, 147902 (`quant-ph/0310089`) — `10-1103-physrevlett-93-040502.md` (TEBD origin).
- Peschel et al. 1999 — `peschel-1999-*.md` (DMRG book stub; bibliographic only).
- TDVP one-/two-site algorithm filled from the web (see *Reproduction-sufficiency*): Haegeman et al.
  2016, *PRB* 94, 165116 (`arXiv:1408.5056`); tensornetwork.org TDVP page.

---

## 1. Overview

An MPS writes the wavefunction of an L-site chain as a product of per-site tensors:

```
|ψ⟩ = Σ_{σ₁…σ_L}  M^{σ₁} M^{σ₂} … M^{σ_L} |σ₁…σ_L⟩
```

Each `M^{σ_i}` is a D×D matrix (D×1 / 1×D at the open ends), `σ_i` runs over the d-dimensional
local Hilbert space (d=2 for spin-½, d=3 for spin-1, d=4 for a fermion site). The link size **D**
(also written **χ**) is the **bond dimension** — the single accuracy knob.

- **Why it works — area law.** Ground states of gapped, local 1D Hamiltonians have entanglement
  entropy `S(ℓ)` that *saturates* (area law) instead of growing with block size ℓ. An MPS of bond
  dimension D represents at most `S ≤ log₂ D` of entanglement across any cut, so a modest D suffices.
  Gapless/critical states violate the area law logarithmically (`S ~ (c/6) log ℓ`, c = central charge),
  so D must be pushed and *scaled* (finite-entanglement scaling, §9).
- **Cost scaling.** Every local operation (effective eigensolve, SVD, gate) costs **~D³** floating
  point work; full sweep/iteration cost is `L·d·D³` (more precisely `O(D³·D_W·d)` with an MPO of
  bond dimension D_W). Memory is `O(L·d·D²)` for the state. **D³ is the wall-clock lever.**
- **Two regimes.** *Finite* — open (OBC) or periodic (PBC) chain of fixed L: DMRG, TEBD, TDVP.
  *Infinite/uniform* — one unit cell of tensors repeated forever, giving the thermodynamic limit
  directly with no 1/L extrapolation: VUMPS, IDMRG, iTEBD.
- **What's approximated.** Truncating bonds to finite D discards the smallest Schmidt weights.
  Exact as D→∞ for gapped 1D; controlled and variational at finite D (energy is a strict upper bound).

---

## 2. MPS / MPO formalism

### 2.1 SVD and the Schmidt decomposition (Schollwöck §4.1.1)

For a bipartition A|B with coefficient matrix Ψ (entries `Ψ_{ij}`), SVD gives `Ψ = U S V†` with
non-negative singular values `s₁ ≥ s₂ ≥ … ≥ s_r > 0` (descending). This is the Schmidt decomposition:

```
|ψ⟩ = Σ_a  s_a |a⟩_A |a⟩_B ,     ρ_A = Σ_a s_a² |a⟩_A⟨a| ,     S_{A|B} = −Σ_a s_a² log₂ s_a²
```

The **optimal rank-D' approximation** in 2-norm keeps the D' largest singular values (Eckart–Young):
`Ψ̃ = U S' V†`, `S' = diag(s₁,…,s_{D'},0,…)`. The discarded weight

```
ε_trunc = Σ_{a>D'} s_a²        (the truncation error — the primary controlled error of MPS)
```

is the load-bearing diagnostic: it must be small and is the quantity extrapolated to zero (§9).

### 2.2 Canonical forms and gauge (Schollwöck §4.4; Orús §canonical form)

The MPS factorization is gauge-redundant: inserting `X X⁻¹` on any bond leaves |ψ⟩ unchanged.
Three canonical choices fix the gauge usefully:

- **Left-canonical** `A^{σ}`: `Σ_σ A^{σ†} A^{σ} = 𝟙` (each `A` is a left isometry). Built by sweeping
  SVD/QR left→right and carrying `S V†` rightward.
- **Right-canonical** `B^{σ}`: `Σ_σ B^{σ} B^{σ†} = 𝟙`. Built sweeping right→left.
- **Mixed-canonical** (the working form for DMRG/VUMPS): left-canonical up to a center, then
  right-canonical: `|ψ⟩ = Σ A^{σ₁}…A^{σ_{ℓ-1}} Ψ^{σ_ℓ} B^{σ_{ℓ+1}}…B^{σ_L} |σ⟩` (Schollwöck Eq.189).
  The single center tensor `Ψ^{σ_ℓ}` (or, splitting it, a bond matrix `C`) carries the Schmidt values
  on the active bond; left/right isometry then makes the local effective metric the identity (§3).
- **Γ-Λ (Vidal) form** (Orús): `|ψ⟩ = … Λ Γ^{σ} Λ Γ^{σ'} Λ …` with diagonal Schmidt matrices Λ on
  every bond and `Γ` the basis-change tensors. Natural for (i)TEBD; `A = Λ Γ`, `B = Γ Λ` convert it
  to the A/B forms. **Pitfall:** Γ-Λ needs division by Schmidt values — small λ make it
  ill-conditioned; modern codes prefer A_L/A_R/C forms (VUMPS is inverse-free by construction).

### 2.3 MPO representation of Hamiltonians (Schollwöck §6.1)

An operator is a matrix-product operator (MPO) `Ô = Ŵ^{[1]} Ŵ^{[2]} … Ŵ^{[L]}` of operator-valued
matrices `Ŵ^{[i]}` (bond dimension D_W). Local Hamiltonians have an exact, compact MPO from a
**finite-state machine**: each MPO bond index is a "state" of a running operator string, transitions
emit local operators. For the XXZ + field chain (Schollwöck Eq.184), with bookkeeping states
1 = "identity so far", 2/3/4 = "one S⁺/S⁻/S^z just placed", 5 = "term completed":

```
        ⎡  𝟙        0        0        0      0 ⎤
        ⎢ S⁺        0        0        0      0 ⎥
W^{[i]} =⎢ S⁻        0        0        0      0 ⎥
        ⎢ S^z       0        0        0      0 ⎥
        ⎣ −h·S^z  (J/2)S⁻ (J/2)S⁺  J_z·S^z   𝟙 ⎦      (bulk, D_W = 5)
```

with row vector `[−h·S^z, (J/2)S⁻, (J/2)S⁺, J_z·S^z, 𝟙]` on site 1 and the corresponding column on
site L. Multiplying the `Ŵ` reproduces H exactly. Longer-range terms add intermediate states
(one per unit of range); exponentially decaying `J(r)=J λ^r` packs into a single extra state
(Schollwöck Eq.188), and general `J(r)` is fit by a sum of exponentials. In practice this construction
is automated by an **OpSum / AutoMPO** interface (write H as a sum of operator strings; the library
compiles the MPO) — used by ITensor (`OpSum`), TeNPy (`CouplingMPOModel`), MPSKitModels.

---

## 3. Finite DMRG (Schollwöck §6.2–6.4)

DMRG variationally minimizes `E = ⟨ψ|H|ψ⟩ / ⟨ψ|ψ⟩` (Eq.202) over MPS of fixed D by sweeping:
freeze all sites but one (or two), solve the resulting *quadratic* local problem, move on.

### 3.1 Environments and the effective Hamiltonian

Contract the H-MPO against the MPS to the left/right of the active site into environment tensors
`L` and `R`, built iteratively site-by-site (Schollwöck Eq.197, cost `O(d·D³·D_W)`):

```
F^{[i]} = Σ_σσ'  W^{σσ'}  A^{σ†} F^{[i-1]} A^{σ'}      (left environment update)
```

The single-site **effective Hamiltonian** is `H_eff = L · W · R` reshaped to a `(d·D²)×(d·D²)` matrix
(Schollwöck Eq.210; Fig.41). In mixed-canonical form (left-iso to the left, right-iso to the right of
the center), the metric `N = 𝟙`, so the generalized eigenproblem `H v − λ N v = 0` collapses to a
**standard hermitian eigenproblem** (Eq.211):

```
H_eff · v = λ · v ,     v = vec(M^{σ_ℓ})
```

### 3.2 Local solve, truncation, sweep

Solve for the *lowest* eigenpair with an **iterative eigensolver** (Lanczos or Jacobi-Davidson) —
never a dense diagonalization (dD² is large). The current `M^{σ_ℓ}` is the **warm-start guess**, which
near convergence makes the local solve cost a few matvecs. `λ₀` is the running ground-state energy.

**Two-site DMRG (the robust default).** Optimize the merged two-site tensor `M^{σ_ℓ σ_{ℓ+1}}` on
`H_eff^{(ℓ,ℓ+1)} = L·W_ℓ·W_{ℓ+1}·R`, then **SVD with truncation** back to two single-site tensors,
keeping the D largest singular values (truncation error ε_trunc). Two-site DMRG can *change the
quantum-number distribution across the bond*, so it is robust against getting stuck; cost is ~d× the
single-site solve.

**Single-site DMRG** optimizes one site, then QR/SVD to restore canonical form. Faster, but the bond
quantum-number distribution is *frozen* (Schollwöck §6.3): the SVD only rotates within fixed
symmetry blocks, so the algorithm can trap in the wrong sector. Fix: **subspace expansion / density-
matrix (noise) mixing** (White's correction, Schollwöck Eq.217):

```
ρ̂_{A•}  =  Tr_B |ψ⟩⟨ψ|  +  α · Σ_{b}  Tr_B  Ĥ^{A•}_b |ψ⟩⟨ψ| Ĥ^{A•}_b†
```

with a small `α ~ 10⁻⁴ … 10⁻⁵` that seeds the discarded subspace with states H can reach, then is
taken slowly to zero over sweeps. This makes single-site DMRG robust (and competitive with two-site)
without the d× cost; it is the basis of modern single-site "strictly single-site" / subspace-expansion
DMRG. Diagonalize ρ̂, keep the D largest eigenvalues → the truncated isometry.

### 3.3 Sweeping schedule and convergence (Schollwöck §6.3)

```
DMRG (finite, two-site):
  1. Initialize a right-canonical MPS (random in target sector, or a product state).
  2. Build all R environments (sites L-1 … 1).
  3. Repeat sweeps until converged:
       Right sweep ℓ = 1 … L-1:
         - form H_eff^{(ℓ,ℓ+1)} = L · W_ℓ · W_{ℓ+1} · R
         - Lanczos/Davidson for lowest eigenpair (warm-start from current tensor)
         - SVD truncate to D (record ε_trunc); apply noise mixing if single-site
         - left-canonicalize site ℓ; update L; carry remainder to ℓ+1
       Left sweep ℓ = L … 2:  mirror, right-canonicalize, update R
  4. Stop when ΔE/sweep < tol  AND  variance ⟨H²⟩−⟨H⟩² → 0.
```

**Convergence diagnostics.** Energy decreases *monotonically* (variational) and flattens; the
sharpest test is the **energy variance** `⟨H²⟩ − ⟨H⟩²` (computable with the H-MPO), which → 0 only at
a true eigenstate (Schollwöck §6.3). A common protocol ramps D and α together: start small D, converge,
grow D (pad with zeros / subspace expansion), reconverge — but **never report a single D** (§9).
Low-lying excited states: target a different symmetry sector, or orthogonalize the Lanczos vectors
against already-found states.

---

## 4. TEBD (Schollwöck §7.1; Vidal `quant-ph/0310089`)

TEBD applies a Trotterized (imaginary or real) time evolution gate-by-gate, truncating after each layer.
For nearest-neighbor `H = Σ_i ĥ_{i,i+1}`, split into odd and even bonds (gates within a layer commute).

### 4.1 Trotter–Suzuki decompositions

```
1st order:  e^{−iHτ} = e^{−iH_odd τ} e^{−iH_even τ}                              + O(τ²)     (Eq.226)
2nd order:  e^{−iHτ} = e^{−iH_odd τ/2} e^{−iH_even τ} e^{−iH_odd τ/2}            + O(τ³)     (Eq.229)
4th order (Suzuki):  U(τ₁)U(τ₂)U(τ₃)U(τ₂)U(τ₁),  U(τ_i)=e^{−iH_odd τ_i/2}e^{−iH_even τ_i}e^{−iH_odd τ_i/2}
            τ₁=τ₂ = τ/(4 − 4^{1/3}),   τ₃ = τ − 2τ₁ − 2τ₂                                    (Eq.230–232)
```

The error per step accumulates over `N = t/τ` steps, so the *global* error is one order lower: 2nd
order gives `O(τ²)` global. Half-steps can be merged when no measurement falls between them (free
2nd order).

### 4.2 Gate application + truncation

Each bond gate `e^{−iĥ τ}` is a `(d²×d²)` operator. Apply it to the two-site tensor, then SVD to
restore MPS form, truncating to D (Schollwöck §7.1.2):

```
TEBD step (2nd-order):
  for each odd bond:  contract gate e^{−i h τ/2} into M^{σ_i σ_{i+1}};  SVD → A, S, B;  truncate to D
  for each even bond: same with full step τ
  for each odd bond:  same with τ/2
  monitor ε_trunc each SVD; raise D if it exceeds tolerance
```

The gate raises the bond from D to `d²D`; truncation brings it back. Applying gates in Γ-Λ form
needs division by the neighbouring Λ — use the small-singular-value-safe variant (Schollwöck §10.4).

### 4.3 Imaginary vs real time

- **Imaginary time** `τ → β = it`: `e^{−Hβ}` projects any non-orthogonal start onto the ground state
  as β→∞. A ground-state *route* (slower than DMRG/VUMPS, but simple). Refine τ→0 in stages.
- **Real time** `e^{−iHt}`: dynamics. **Entanglement grows ~linearly in t** (after a quench), so D
  must grow exponentially to hold fixed accuracy — this is the hard wall on reachable time, common to
  all MPS time-evolution methods.
- **Finite temperature** via **purification** (Schollwöck §7.2): double each physical site with an
  ancilla, start from the infinite-T maximally entangled state, evolve in imaginary time to β/2;
  `⟨O⟩_β = ⟨ψ(β)|O|ψ(β)⟩`. METTS is a sampling alternative (Schollwöck §8.3).

---

## 5. Infinite / uniform MPS — IDMRG and VUMPS (Schollwöck §10; Zauner-Stauber et al.)

A uniform MPS repeats one unit cell of length L_cell forever, representing the thermodynamic limit
*directly* (no 1/L extrapolation; the D→∞ extrapolation remains). The **unit cell must be ≥ the period
of the order**: a uniform/Haldane state → 1-site cell, a Néel/AFM state → 2-site cell (or fold a 2-site
ordered state to 1 site by a sublattice rotation, as FIG.7c rotates every second spin by π about z).

State in the **mixed canonical** parametrization (VUMPS Eq. convention): a left isometry `A_L`, a right
isometry `A_R`, a center tensor `A_C`, and a bond matrix `C`, related at the fixed point by
`A_C^{s} = A_L^{s} C = C A_R^{s}` (the gauge/fixed-point condition, Eq.23c).

### 5.1 IDMRG (Schollwöck §10.3)

Run infinite-system DMRG: repeatedly insert two fresh sites in the center, optimize, and translate the
converged center cell outward; the bulk tensor approaches the uniform fixed point. Use the **state
prediction** trick (Schollwöck Eq.218, McCulloch) to seed the next eigensolver from the previous step.
Convergence is the fixed-point relation between reduced density matrices of two successive lengths
(Eq.341): `ρ̂_L^{[ℓ]} = ρ̂_A^{[ℓ-1]}` to high accuracy, measured by the fidelity `F = Σ_i s_i` of the
overlap of successive Schmidt spectra (Eq.342). IDMRG reuses all finite-DMRG machinery (MPO H, Lanczos)
but reaches a given accuracy in *more* iterations than VUMPS and **can stall near criticality**. Expectation
values require an orthogonalization of the thermodynamic-limit state first (Schollwöck §10.5).

### 5.2 VUMPS — the variational uniform fixed point (Zauner-Stauber et al. §II)

The energy is stationary when the tangent-space gradient vanishes. VUMPS enforces this by solving two
coupled **effective eigenvalue problems** per iteration and re-gauging — *directly in the
thermodynamic limit at every step* (unlike IDMRG, which grows a finite cell).

Define two thermodynamic-limit effective Hamiltonians (the system H projected onto A_C and onto C,
with the divergent energy density subtracted so they are finite):

```
H_{A_C} :  acts on the one-site center tensor A_C        (Eq.9)
H_C     :  acts on the zero-site bond matrix C           (Eq.10, "zero-site" effective Hamiltonian)
```

For nearest-neighbor H, `H_{A_C}` is the sum of four terms — h coupling the center to the left block,
to the right block, plus the left/right *infinite environments* `H_L`, `H_R` (Eq.11). `H_L`, `H_R` are
obtained by solving **linear systems** against the transfer matrix (geometric sums of the connected
contributions); the dominant transfer-matrix eigenvectors `L = C†C`, `R = CC†` enter as the
pseudo-inverse projectors (Eq. for the regularized geometric sum). For MPOs/long-range H, the
environments come from the MPO transfer matrix (paper Appendix C).

**The two fixed-point eigenproblems** (Eq.23a–b):

```
H_{A_C} · A_C = E_{A_C} · A_C        (one-site, lowest eigenpair)
H_C     · C   = E_C     · C          (zero-site, lowest eigenpair)
```

**Re-gauging** (Eq.18–22): the freshly solved Ã_C and C̃ generally do *not* satisfy the gauge
condition `A_C = A_L C = C A_R`. Recover the isometries by minimizing `‖A_C − A_L C‖` and
`‖A_C − C A_R‖`; the solution is the isometry of a **polar decomposition**. The robust, inverse-free
choice (Eq.21–22) uses left/right polar decompositions of A_C and of C directly:

```
A_C^{[ℓ]} = U_{A_C}^{[ℓ]} P_{A_C}^{[ℓ]} ,   C = U_C^{[ℓ]} P_C^{[ℓ]}   ⇒   A_L = U_{A_C}^{[ℓ]} (U_C^{[ℓ]})†
A_C^{[r]} = P_{A_C}^{[r]} U_{A_C}^{[r]} ,   C = P_C^{[r]} U_C^{[r]}   ⇒   A_R = (U_C^{[r]})† U_{A_C}^{[r]}
```

(The SVD form Eq.20 is "theoretically optimal" but breaks down on the small Schmidt values that good
uMPS always have; Eq.22 is preferred.) This avoids ill-conditioned inverses entirely.

```
VUMPS  (Zauner-Stauber et al. Table II):
  Input: H, initial orthogonalized uMPS (A_L, A_R, C), threshold ε
  while ε_prec > ε:
    (optional) adjust D (Appendix B subspace expansion)
    build H_{A_C}, H_C environments  (solve linear systems for H_L, H_R; precision ε_S ≲ ε_prec)
    Ã_C ← lowest eigvec of H_{A_C}   (iterative solver, tol ε_H ≈ ε_prec/100, warm-started)
    C̃   ← lowest eigvec of H_C
    (Ã_L, Ã_R) ← polar decomposition of Ã_C and C̃   (Eq.22)
    ε_L = min‖Ã_C − Ã_L C̃‖,  ε_R = min‖Ã_C − C̃ Ã_R‖
    ε_prec ← max(ε_L, ε_R);  set (A_L,A_R,C) ← (Ã_L,Ã_R,C̃)
  return (A_L, A_R, C)
```

The eigenproblems need only be solved to a *relative* tolerance `ε_H ~ ε_prec/100`, not machine
precision — VUMPS takes big variational steps. Cost per iteration is higher than IDMRG (two eigensolves
+ two linear systems vs one eigensolve), but it converges in far fewer iterations and **to machine
precision even at criticality**, where IDMRG and iTEBD stagnate (FIG.7c).

### 5.3 iTEBD (Schollwöck §10.4)

Apply imaginary-time Trotter gates to the infinite Γ-Λ MPS, SVD-truncating back to D each step; same
gate machinery as TEBD with the small-singular-value-safe update. After each step, **re-orthogonalize**
the thermodynamic-limit state (Orús–Vidal / McCulloch procedure, Schollwöck §10.5) because truncation
spoils the canonical property. Simple, but carries Trotter error (τ→0 needed) and converges slowly near
criticality. **MPSKit has no TEBD/iTEBD — route iTEBD to TeNPy.**

---

## 6. TDVP — tangent-space time evolution (Haegeman et al. 2016; filled from web)

TDVP evolves the MPS by projecting the Schrödinger equation onto the MPS **tangent space** (the space
of first-order variations at fixed D) *before* integrating: `d/dt |ψ⟩ = −i P_T H |ψ⟩`. The tangent-space
projector splits into per-site forward terms minus per-bond backward terms:

```
P_T = Σ_j  P_{j-1}^L ⊗ 𝟙_j ⊗ P_{j+1}^R   −   Σ_j  P_j^L ⊗ P_{j+1}^R
```

Lie–Trotter (projector) splitting of this sum gives a **sweep** alternating *forward* local evolutions
of site tensors and *backward* evolutions of the bond tensor between them — the same `L·W·R` effective
Hamiltonians as DMRG.

### 6.1 One-site TDVP (1TDVP)

```
1TDVP right sweep (step δ; mirror left sweep for 2nd-order symmetric integrator):
  for j = 1 … L:
    1. evolve site:  M_j ← exp(−i (δ/2) H_eff^{j}) · M_j ,   H_eff^{j} = L_{j-1}·W_j·R_{j+1}   (FORWARD)
    2. QR:  M_j → A_j (left-iso), C_j (bond)
    3. update left environment L_j ← contract(L_{j-1}, W_j, A_j)
    4. if j ≠ L:  evolve bond BACKWARD: C_j ← exp(+i (δ/2) H_eff^{0,j}) · C_j ,  H_eff^{0,j}=L_j·R_{j+1}
    5. absorb into next site:  M_{j+1} ← C_j · B_{j+1}
```

- **Bond dimension is fixed** (no SVD truncation). Norm and energy are conserved *exactly*.
- **Projection error**: zero only at maximal D; finite at fixed D (the dominant error for 1TDVP).
- **Imaginary time** (`δ → −iβ`, drop the i): 1TDVP is a covariant gradient descent; in the limit of
  infinite imaginary-time step it is **provably equivalent to single-site DMRG**.

### 6.2 Two-site TDVP (2TDVP)

```
2TDVP right sweep:
  for j = 1 … L-1:
    1. merge: T_{j,j+1} = M_j · B_{j+1}
    2. evolve FORWARD: T ← exp(−i (δ/2) H_eff^{(j,j+1)})·T ,  H_eff^{(j,j+1)}=L_{j-1}·W_j·W_{j+1}·R_{j+2}
    3. SVD with truncation to D:  T → A_j, S, B_{j+1}   (records ε_trunc; D may grow)
    4. if j ≠ L-1:  evolve M_{j+1} BACKWARD: M_{j+1} ← exp(+i (δ/2) H_eff^{j+1})·M_{j+1}
```

- **Bond dimension adapts** via the SVD (it can grow), at the price of a truncation error.
- **No projection error for nearest-neighbor H** (the two-site block captures the bond term exactly) —
  this is its main advantage.

### 6.3 When TDVP over TEBD

- **Long-range or MPO Hamiltonians**: TEBD's odd/even gate split assumes nearest-neighbor terms;
  TDVP works for *any* H expressible as an MPO. This is the primary reason to choose TDVP.
- **Energy/norm conservation** over long real-time evolution: 1TDVP conserves both exactly (good for
  long times at fixed D, accepting projection error).
- **Growing entanglement / unknown D**: 2TDVP (adapts D) or a 2TDVP→1TDVP hybrid (grow D early with
  2TDVP, then conserve with 1TDVP). Time-step error is `O(δ²)` per unit time with both sweeps.

---

## 7. Observables (Schollwöck §4.2; Orús §expectation values, §correlation length)

- **Norm / overlap**: `⟨ψ|ψ⟩ = E^{[1]}E^{[2]}…E^{[L]}` as a product of transfer operators
  `E^{[i]} = Σ_σ M^{σ†} ⊗ M^{σ}` (Schollwöck Eq.113). In canonical form most contractions collapse to
  identities → cost `O(L·d·D³)`.
- **Local expectation value**: `⟨O_i⟩` — insert `E_O^{[i]} = Σ_{σσ'} O^{σσ'} M^{σ†}⊗M^{σ'}` at site i;
  with the center placed at i, only the local tensor is touched.
- **Two-point correlator**: `⟨O_i P_j⟩` = product of transfer operators with O at i, P at j (Eq.114),
  contracted in `O(D³)` using the internal product structure.
- **Entanglement entropy**: read directly off the bond Schmidt values, `S = −Σ_a s_a² log₂ s_a²`
  (Eq.25). The full set `{s_a²}` is the **entanglement spectrum** (a fingerprint of topological/SPT phases).
- **Correlation length from the transfer matrix** (Schollwöck §4.2.2; Orús Eq.18). The transfer matrix
  E has dominant eigenvalue `λ₁ = 1` (normalized canonical state); subleading eigenvalues set decaying
  modes. Connected correlators are superpositions of exponentials with decay lengths
  `ξ_k = −1/ln|λ_k|`, dominated by the *second* eigenvalue:

  ```
  ξ = −1 / ln|λ₂/λ₁|
  ```

  Finite ξ ⇔ gapped; ξ growing without bound as D increases ⇔ critical (the transfer-matrix gap
  closes as D→∞). This is the natural infinite-MPS gap/criticality diagnostic.

---

## 8. Key parameters & convergence diagnostics

| Knob | Default / typical | Effect & scaling |
|---|---|---|
| **Bond dimension D (χ)** | problem-dependent (FIG.7: 54–120; cylinders & critical want larger) | the accuracy lever; energy ↓ monotone and asymptotes; cost ~D³; gapless never converges at fixed D → scale D (§9) |
| **Truncation cutoff vs maxdim** | cutoff `ε_trunc ~ 1e-8…1e-12`, or fixed maxdim D | cutoff = drop singular values below threshold (adaptive D); maxdim = hard cap. Codes usually take both, applying whichever binds |
| **Unit cell (infinite)** | smallest cell ≥ period of the order | too small *cannot represent* the order (Néel on a 1-site cell is impossible). Sublattice rotation can fold order back to a 1-site cell |
| **Stop criterion** | VUMPS/IDMRG: ‖B‖ or ε_prec < 1e-10…1e-12; DMRG: ΔE/sweep + variance; iTEBD: energy plateau | see §8.1 |
| **Trotter step τ** (TEBD/iTEBD) | schedule 0.1 → 5e-4 in stages | error ~τ² (2nd order). **Pitfall:** tiny τ makes per-step ΔE tiny *regardless of convergence* — refine τ→0 *and* run each stage to its plateau |
| **Time step δ** (TDVP) | small, problem-dependent | global error `O(δ²)` with symmetric sweep; tradeoff vs projection/truncation error per total time |
| **Max sweeps / iterations** | DMRG ~10s; VUMPS/IDMRG ~100s | a work cap; the stop criterion should fire first. Hitting the cap = not converged |
| **Symmetry** | none, or U(1) S^z / particle number (SU(2) when available) | block-diagonalizes tensors → smaller, faster, pins the sector. VUMPS paper uses *none* to benchmark the bare algorithm |
| **Initial state** | random, or product state in target sector | product state (Néel, dimer) is robust and pins the sector; random can trap in a metastable minimum — restart with a new seed |

### 8.1 The convergence diagnostics, by method

- **DMRG**: energy change per sweep `ΔE` *and* the **energy variance** `⟨H²⟩−⟨H⟩²` → 0 (the latter is
  the real eigenstate test). Track ε_trunc per sweep.
- **VUMPS / IDMRG**: the **tangent-space gradient norm ‖B‖** (Zauner-Stauber et al. Eq.34) — the
  2-norm of the `D×d×D` tensor `B^{s} = A'_C^{s} − A_L^{s} C'` (= `A'_C^{s} − C' A_R^{s}`), the size of
  the best tangent-space improvement to the current state; `‖B‖→0 ⇔ true variational fixed point`.
  **Stop on ‖B‖, report the energy** — the energy can hit machine precision while ‖B‖ is still far from
  zero (FIG.1: state not yet stationary). For an N-site cell, concatenate the per-site B and take the
  norm. (Equivalently VUMPS uses `ε_prec = max(ε_L, ε_R)`, Eq.24; MPSKit `calc_galerkin`, TeNPy
  `tangent_projector_test`.)
- **iTEBD**: energy plateau at *each* τ stage; never read a small per-step ΔE at small τ as convergence.

---

## 9. Validation / benchmarks

1. **Variational energy bound.** DMRG/VUMPS energies are strict *upper* bounds; energy must decrease
   monotonically with D and with sweep/iteration. A non-monotone energy signals a bug.
2. **Truncation-error extrapolation.** Plot E (or the observable) vs the discarded weight ε_trunc and
   extrapolate `ε_trunc → 0` (equivalently a D-series). **Never report a single D.**
3. **Energy variance.** `⟨H²⟩−⟨H⟩²` small relative to `E²` confirms an eigenstate (cheap with the H-MPO).
4. **Finite-entanglement scaling (gapless/critical).** At criticality, finite D imposes an effective
   correlation length `ξ ~ D^κ`; the entanglement entropy obeys `S ~ (c/6) ln ξ_D`, giving the
   **central charge c** from the slope, and energy/observables are extrapolated in D (not fixed at one D).
5. **Cross-method / exact agreement.** VUMPS, IDMRG, iTEBD must agree on the per-site energy at the
   same D. Harness anchors from FIG.7: spin-1 Haldane chain `e₀ ≈ −1.401484`; critical spin-½ isotropic
   Heisenberg `e₀ = ¼ − ln2 ≈ −0.4431` (where only VUMPS drives ‖B‖→~1e-12). Disagreement at equal D ⇒
   setup error (wrong unit cell, wrong sector, unconverged D).
6. **Symmetry sector.** Total S^z / particle number of the result matches the intended sector.
7. **Limit checks.** Sign convention and trivial limits via `.knowledge/limits.md`; XXZ Δ=1 ↔ isotropic
   Heisenberg, U=0 free-fermion, etc.

**Common failure modes to criticize.** Unit cell too small for the order (silently wrong state);
D too small read as converged (no D-series → biased energy); iTEBD false convergence (small τ → tiny
ΔE regardless of truncation); reading the energy before ‖B‖ converges; claiming a critical value at
fixed D without finite-entanglement scaling; leaving JIT/warm-up in the clock for a wall-time benchmark.

---

## 10. Reproduction-sufficiency assessment

**Verdict: the KB is sufficient to reproduce DMRG, TEBD, VUMPS, and IDMRG end-to-end; TDVP was the
one gap and was filled from the web.**

| Method | KB coverage | Sufficient? |
|---|---|---|
| **Finite DMRG** | Schollwöck §6 — full: MPO H, environments, effective eigenproblem (Eq.210–211), Lanczos/Davidson, single- vs two-site, density-matrix noise mixing (Eq.217), sweep schedule, variance test | **Yes** — reproduction-grade |
| **TEBD** | Schollwöck §7.1 — full: 1st/2nd/4th-order Trotter (Eq.226–232), gate-as-MPO, SVD truncation, imaginary/real time, purification for finite-T; Vidal origin paper present | **Yes** |
| **VUMPS** | Zauner-Stauber et al. — full: A_C/C effective Hamiltonians (Eq.9–11), fixed-point eigenproblems (Eq.23), polar-decomposition re-gauge (Eq.18–22), ε_prec (Eq.24), ‖B‖ gradient (Eq.34), pseudocode (Table II) | **Yes** |
| **IDMRG** | Schollwöck §10.1–10.3 — full: grow-and-translate, state prediction (Eq.218), fixed-point ρ test (Eq.341–342), thermodynamic-limit orthogonalization (§10.5) | **Yes** |
| **iTEBD** | Schollwöck §10.4 — full: Γ-Λ gates, small-λ-safe update, re-orthogonalization | **Yes** |
| **Observables** | Schollwöck §4.2 + Orús — full: transfer operator, correlators, entanglement entropy/spectrum, correlation length ξ = −1/ln|λ₂/λ₁| | **Yes** |
| **TDVP** | KB only *mentions* TDVP (VUMPS paper: gradient-descent precursor, single-site = DMRG in the β→∞ limit). No one-/two-site algorithm, no projector splitting. | **Gap — FILLED from web** |

**What was filled from the web.** The 1TDVP/2TDVP algorithm: the tangent-space projector splitting,
the forward (site, `L·W·R`) and backward (bond, `L·R`) local evolutions, the sweep structure, and the
1- vs 2-site tradeoffs (projection error, fixed vs adaptive D, when to use which). Sources: Haegeman,
Lubich, Oseledets, Vandereycken, Verstraete, *Unifying time evolution and optimization with matrix
product states*, PRB 94, 165116 (2016), arXiv:1408.5056; and the tensornetwork.org TDVP page. This is
the canonical TDVP reference and matches the SKILL.md citation (Haegeman et al. PRL 107 (2011),
PRB 94 (2016)). Recommend ingesting arXiv:1408.5056 into the KB to close the gap natively.

---

## 11. Source links

KB (relative to repo root):
- `.knowledge/literature/mps-based-algorithm/1008.3477_the-density-matrix-renormalization-group-in-the-age-of-matri.md` — Schollwöck 2010
- `.knowledge/literature/mps-based-algorithm/1306.2164_a-practical-introduction-to-tensor-networks-matrix-product-s.md` — Orús 2013
- `.knowledge/literature/mps-based-algorithm/1701.07035_variational-optimization-algorithms-for-uniform-matrix-produ.md` — Zauner-Stauber et al. 2018 (VUMPS)
- `.knowledge/literature/mps-based-algorithm/10-1103-physrevlett-93-040502.md` — Vidal 2003 (TEBD origin)
- `.knowledge/literature/mps-based-algorithm/peschel-1999-density-matrix-renormalization.md` — DMRG book stub (bibliographic)

Web (TDVP fill):
- Haegeman et al. 2016, PRB 94, 165116 — https://arxiv.org/abs/1408.5056
- TDVP overview — https://tensornetwork.org/mps/algorithms/timeevo/tdvp.html
