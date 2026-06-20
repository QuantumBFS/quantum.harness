# PEPS / iPEPS methodology reference

Reproduction-grade method notes for the **PEPS / iPEPS family**: the 2D
projected-entangled-pair-state ansatz, environment contraction by CTMRG (and
boundary-MPS/VUMPS alternatives), ground-state optimization by imaginary-time
**simple update** / **full update** and by **variational / AD** energy
minimization, and the **classical partition-function** special case. This is the
*method* reference; the PEPSKit software API lives separately in
`skills/using-pepskit/references/pepskit-api.md`.

Notation throughout: physical (site) dimension `d` (= `p` in some sources);
PEPS virtual / bond dimension `D` (= `χB` "bulk" in the Naumann review);
environment / CTM bond dimension `χ` (= `χE`); imaginary-time step `τ`;
bond-weight / Schmidt-spectrum matrices `Λ`. Math is UTF-8 unicode, not LaTeX.

---

## 1. Overview — the PEPS/iPEPS ansatz and why 2D is hard

A **PEPS** (projected entangled-pair state) puts one tensor on every site of a
2D lattice. On the square lattice each tensor `A` carries one physical index of
dimension `d` and four virtual indices of dimension `D` (one per nearest
neighbour):

```
A[s; l, u, r, d]        s = 1..d (physical),   l,u,r,d = 1..D (virtual)
```

The full wavefunction amplitude for a configuration {s_i} is the single scalar
obtained by contracting all virtual indices over the lattice graph:

```
⟨{s_i} | ψ⟩ = Tr ∏_i  A^{s_i}_i      (contract shared virtual bonds)
```

PEPS is the natural 2D (and higher-D) generalization of the matrix product
state (MPS): an MPS contracts a 1D chain of rank-3 tensors; a PEPS contracts a
2D mesh of rank-5 tensors. The ansatz is built to satisfy the **2D area law** —
the entanglement entropy of a region scales with its *boundary* length, not its
volume — which is the property ground states of gapped local 2D Hamiltonians are
believed to obey. `D` controls how much boundary entanglement the state can
carry; the entanglement across a cut of length L is bounded by `L·log D`.

**Why 2D contraction is exponentially hard (unlike MPS).** An MPS has a
*canonical form* and can be contracted exactly in polynomial time because the
network is loop-free (a tree). A 2D PEPS network has loops and no canonical
form, so:

- Exact contraction of a general PEPS is `#P`-hard in the worst case and hard
  even on average (Schuch et al.; Verstraete–Cirac). Contracting an L×L PEPS
  exactly costs memory/time exponential in L (the contraction sweeps a boundary
  whose dimension grows like `D^L`).
- Therefore **all PEPS algorithms approximate the contraction**, controlled by a
  *second* refinement parameter — the environment bond dimension `χ` — distinct
  from the ansatz parameter `D`. PEPS can be contracted in quasi-polynomial time
  with controlled error (Verstraete–Cirac; reviewed in Naumann §1).

This two-parameter structure (`D` for the state, `χ` for the contraction) is the
defining feature of the method and the source of most of its subtleties.

**iPEPS** (infinite PEPS) works directly in the thermodynamic limit: a finite
**unit cell** of distinct tensors (e.g. 1×1 `[A]`, or 2×2 `[A B; B A]` /
`[A B; C D]`) is repeated periodically over the infinite lattice (Jordan et al.;
Naumann §2.1). An iPEPS with N distinct tensors has `N·d·D⁴` real variational
parameters on the square lattice.

---

## 2. The ansatz in detail

### Tensor structure and unit cell
- **Square lattice:** rank-5 site tensor `A[s; l,u,r,d]`. Nearest-neighbour
  bonds carry dimension `D`.
- **Unit cell:** chosen to match the symmetry-broken / ordered pattern of the
  target state. A wrong unit cell can give a poor energy *or* prevent CTMRG from
  converging at all (Naumann §2.1). Néel order on the square lattice needs at
  least a 2-sublattice (`A`/`B`) cell; stripe / plaquette orders need larger
  cells. Common shorthand: a unit cell is a matrix `L` whose entries name the
  tensor at each position, e.g. `L = [A B; B A]`.
- **Other lattices** (honeycomb, kagome, triangular, square-kagome) are handled
  by **coarse-graining** several physical sites into one effective square-lattice
  tensor with enlarged physical dimension (e.g. `d²` for honeycomb x-link
  coarse-graining, `d³` for a kagome up-triangle). The CTMRG backbone then *always*
  runs on the square lattice (Naumann §3). An alternative is the **iPESS**
  (projected entangled simplex state) construction, which keeps simplex tensors
  explicit and has a different (often smaller) variational-parameter count.

### Fermionic PEPS (brief)
Interacting 2D fermions are captured by **fermionic PEPS** without a Jordan–Wigner
string overhead: each virtual and physical index is graded by fermion **parity**,
and every line crossing in the planar tensor diagram is decorated with a **swap
(parity) gate** `S` that supplies the sign for exchanging two odd-parity indices
(`S |a,b⟩ = (−1)^{p(a)p(b)} |b,a⟩`). Because the swap signs are local, the entire
bosonic PEPS code carries over with negligible overhead (Corboz–Orús–Vidal–
Verstraete; Naumann §4.7). Practically this is implemented by graded tensor
libraries (e.g. fermionic `TensorKit.jl` sectors) so the user writes the same
contractions.

---

## 3. Environment contraction — the hard part (CTMRG)

To evaluate `⟨ψ|O|ψ⟩` one needs the **norm network** `⟨ψ|ψ⟩`: stack the PEPS
(ket) on its conjugate (bra), contract the physical indices, and obtain a
**double-layer** tensor `a` per site with four virtual indices each of dimension
`D²` (the "reduced" or sandwiched tensor). The infinite double-layer network is
contracted approximately by **CTMRG** — the *corner transfer matrix
renormalization group* — which represents the infinite environment of one unit
cell by a finite set of boundary tensors (Orús–Vidal 2009; Naumann §2.2).

### Environment tensors
For a 1×1 cell, the environment is **8 tensors**:
- **4 corner tensors** `C₁ C₂ C₃ C₄`, each a χ×χ matrix, approximating an
  infinite quadrant of the lattice.
- **4 edge (transfer) tensors** `T₁ T₂ T₃ T₄`, each χ×χ×D² (two environment legs
  of dimension χ + one double-layer leg of dimension D²), approximating an
  infinite half-row or half-column.

For an `Lx×Ly` unit cell, a full set of 8 environment tensors is stored *per*
distinct site tensor.

### The directional move (insertion → absorption → renormalization)
CTMRG is a directional power method. One **left move** grows the left
environment `{C₄, T₄, C₁}` (Naumann §2.2.1):

1. **Insertion.** Insert one column of the network (a double-layer tensor `a`
   plus the top/bottom edge tensors) next to the current left environment.
2. **Absorption.** Contract the inserted column into `C₁`, `T₄`, `C₄`. Each
   absorption multiplies the environment bond by a factor `D²`, so χ → χ·D².
3. **Renormalization.** Apply isometric **projectors** `P` to truncate the grown
   bond back to χ, keeping the most relevant subspace.

Top, right, bottom moves are analogous (growing the other corner/edge sets).
The four directional moves together = one CTMRG iteration; iterate to a
fixed point.

### Computing the projectors (the truncation)
The standard scheme (Naumann §2.2.2): form the matrix `M = ρ_B · ρ_T` from the
top and bottom halves of a 2×2 patch of the network with its environments
(`ρ_T`, `ρ_B` are the χD²×χD² halves), take the SVD

```
M = U S V†
```

keep the largest χ singular values, define the regularized pseudo-inverse
`S⁺ = inv(√S)` with a small cutoff (typ. drop singular values below ~1e-6 of the
top, i.e. ~1e-12 in S), and build the pair of projectors

```
P_top    = ρ_T · V · S⁺
P_bottom = S⁺ · U† · ρ_B
```

By construction `P_top · P_bottom = 1` if no truncation is made, so the
projectors implement an *optimal* rank-χ approximation of the local environment.
**Full projectors** use the whole 2×2 patch; **half projectors** use a cheaper
2×1 patch and are usually sufficient. A more stable (but costlier)
Fishman-style projector helps when the singular spectrum decays very fast.

### Convergence and the fixed point
CTMRG converges to a fixed point `e* = c(A, e*)` where `c` is one full
iteration. Convergence is monitored by the change in the **corner singular-value
spectrum** between successive iterations (norm difference < threshold).
Important subtlety for AD: ordinary convergence-in-magnitude is *not* enough; the
SVD gauge freedom `M = (UΓ)S(Γ†V†)` lets signs/phases of entries flutter between
iterations. For a true element-wise fixed point one must **fix the gauge** — e.g.
rotate each left singular vector so its largest-magnitude entry is real positive
(Naumann §2.2.3). Element-wise convergence is required before differentiating.

### Alternatives to CTMRG
- **Boundary-MPS / VUMPS.** Represent the infinite boundary (one row of the
  double-layer network treated as a 1D transfer operator) as a uniform MPS and
  find its fixed point with VUMPS (variational uniform MPS) or with iterative
  boundary-MPS contraction. Competitive accuracy; needs more care when the
  transfer operator is non-Hermitian. CTMRG is preferred for arbitrary unit
  cells and non-Hermitian transfer operators (Naumann §2).
- **Tensor coarse-graining** (TRG, HOTRG, TNR): real-space RG of the whole
  network; mostly used for partition functions and single-layer networks.

### Classical partition functions (single-layer special case)
A 2D classical model `Z = Σ exp(−βH)` maps to a **single-layer** infinite tensor
network: one rank-4 tensor `a[l,u,r,d]` per site encodes local Boltzmann weights
(for the square Ising model, `a` is built from the bond weight matrix
`W = [[√cosh β, √sinh β],[√cosh β, −√sinh β]]` contracted with a δ-tensor at each
vertex). This is *exactly* CTMRG without the double-layer step — the edge tensors
are χ×χ×d (here d=2), not χ×χ×D². Contracting it gives the free energy per site
`f = −(1/β) lim (1/N) ln Z`, read off from the dominant network value with the
chosen normalization. This is the cleanest CTMRG onboarding target: classical,
fast, with the exact Onsager/Yang result as reference (see §7).

### Cost scaling
- CTMRG step (quantum double-layer): dominated by `O(χ³ D⁶)` contractions and a
  `O(χ³ D⁶)` SVD of the χD²×χD² matrix (use an *iterative* truncated SVD, e.g.
  Golub–Kahan–Lanczos, since only χ singular values are needed — Naumann §2.8.1).
- Memory: edge tensors `χ²D²`, corners `χ²`.
- Typical requirement `χ ≳ D²` to resolve the environment; near criticality `χ`
  must grow substantially (large correlation length).

---

## 4. Ground-state optimization

Three routes, in increasing accuracy and cost: **simple update** → **full
update** → **variational/AD**. The first two are imaginary-time evolution; the
third minimizes the energy directly.

### 4.1 Imaginary-time evolution setup (common to simple & full update)
Project onto the ground state with `|ψ_GS⟩ ∝ lim_{β→∞} e^{−βH}|ψ_0⟩`. Trotterize:
split `H = Σ h_b` over bonds, and apply small imaginary-time two-site gates

```
g_b = e^{−τ h_b}        (Trotter–Suzuki, first/second order in τ)
```

bond by bond. Each gate acting on a bond inflates that bond's dimension to `D·d`
(or similar); it must be **truncated back to D**. The two update schemes differ
*only* in what environment they use for that truncation.

### 4.2 Simple update (local / bond environment, `Λ` weights)
The cheapest scheme (Jiang–Weng–Xiang "second renormalization" / canonical
simple update; Jordan et al.). Keep a diagonal **bond-weight matrix `Λ`** on
every virtual bond (the analogue of MPS Schmidt values), giving a "Vidal" /
canonical-like form. To update a bond:

1. Absorb the neighbouring bond weights `Λ` into the two site tensors (this is
   the cheap *mean-field* stand-in for the full environment).
2. Apply the gate `g_b`, group the legs into a matrix, and **SVD**:
   `Θ = U Σ V†`.
3. Truncate to the largest `D` singular values; the new bond weight is
   `Λ' = Σ` (normalized); split `U`, `V` back into the two site tensors after
   dividing out the surrounding `Λ`.

The environment is approximated by the *product* of bond weights (a tree /
mean-field approximation), so simple update **ignores loop correlations**. It is
extremely fast — cost ~`O(D⁵ d ...)` per bond, no χ at all during evolution — and
is excellent for gapped states, frustration-free initialization, and for
*generating an initial state* for full update or AD. It is **not variational**:
the simple-update energy is not a rigorous upper bound. Always recompute the
final energy with a proper CTMRG environment before quoting it.

### 4.3 Full update (full CTMRG environment)
Same imaginary-time gates, but the bond truncation uses the **full effective
environment** computed by CTMRG, not the local `Λ`. After applying `g_b`,
minimize the local fidelity

```
‖ |ψ_gate⟩ − |ψ_trunc(D)⟩ ‖²
```

with the environment fixed (an alternating least-squares / "reduced-tensor"
optimization on the two tensors of the bond). This restores loop correlations
that simple update misses, at much higher cost: a CTMRG environment must be
(re)converged as the tensors change. The "fast full update" + gauge-fixing
variant reduces this cost substantially (Phien et al., 2015). Cost per full
update is comparable to one variational step. Like the variational scheme, full
update gives a variational energy when the environment is converged.

### 4.4 Variational / AD optimization (the modern default)
Minimize the energy functional directly over the tensor coefficients
(Corboz 2016; Liao–Liu–Wang–Xiang 2019; Naumann §2.3–2.6):

```
E(A) = ⟨ψ(A)|H|ψ(A)⟩ / ⟨ψ(A)|ψ(A)⟩
```

- **Energy from the environment.** With the converged CTMRG environment, each
  bond energy `⟨ψ|h_b|ψ⟩/⟨ψ|ψ⟩` is a closed network of the two ket+bra site
  tensors, the gate, and the surrounding `C`/`T` tensors (Naumann Fig. 11). Sum
  over all Hamiltonian terms.
- **Gradient by automatic differentiation.** Treat the whole pipeline
  (CTMRG fixed point → energy) as a differentiable program and obtain
  `∂E/∂A` by **reverse-mode AD**. Because the output is a single scalar and the
  input has `N·d·D⁴` components, reverse mode costs `O(1)×O(E)` (one VJP pass),
  vastly cheaper than forward mode `O(N·d·D⁴)×O(E)` (Naumann §2.4).
- **Differentiating through the CTMRG fixed point.** Naively unrolling all CTMRG
  iterations costs memory linear in the iteration count. Instead use the
  **fixed-point / implicit-function trick** (Liao et al.; Naumann §2.5): at the
  converged fixed point `e* = c(A, e*)`, the gradient is

  ```
  dE/dA = ∂E/∂A + (∂E/∂e*) · Σ_{n=0}^{∞} (∂c/∂e*)ⁿ · (∂c/∂A)
  ```

  i.e. one only needs to back-propagate through a *single* converged iteration
  and geometric-sum the linear response (evaluated to finite order until the
  gradient converges). This bounds the AD memory. It requires
  **element-wise (gauge-fixed) CTMRG convergence** (§3) and a **stable SVD
  backward rule** — the SVD adjoint contains terms `F_ij = 1/(s_j² − s_i²)` that
  diverge for (near-)degenerate singular values (Liao et al.; Naumann §2.8.6).
- **Optimizer.** Feed `E`, `∇E` to a standard gradient optimizer:
  **L-BFGS** (quasi-Newton, default for larger D) or **nonlinear conjugate
  gradient** (Hager–Zhang), with a Wolfe-condition line search (Naumann §2.6).
- **Gauge considerations.** The energy depends only on the physical state, not
  on the per-bond gauge of the tensors; this redundancy is harmless for the
  energy but matters for the SVD gauge during AD (must be fixed, §3) and for
  comparing tensors across runs.

**Why AD won.** Earlier variational iPEPS built the gradient by hand from
specialized environments (Corboz 2016). AD makes the gradient automatic, so new
lattices, longer-range terms, and symmetric tensors need almost no extra
derivation — this is why PEPSKit/variPEPS-style AD optimization is the current
default (Liao et al.; Naumann §1).

---

## 5. Observables

From the converged CTMRG environment:

- **Local one-site `⟨O_i⟩`**: close the bra/ket site tensors and the operator
  inside the ring of 4 corners + 4 edges; divide by the norm (same network with
  `O = 1`). Used for magnetization `⟨S^z⟩`, `⟨S^x⟩`, density `⟨n⟩`.
- **Bond / two-site `⟨O_i O_j⟩`**: the two-site network of Naumann Fig. 11; gives
  bond energies, dimer order, spin-spin nearest-neighbour correlators.
- **Distance-r correlators** `⟨O_0 O_r⟩`: insert `r−1` edge/transfer tensors
  between the two operator sites along a row.
- **Correlation length from the CTM transfer matrix.** Build the row-to-row
  transfer matrix from the edge tensors (the χD²×χD² object whose repeated
  application generates a row of the network). Its leading eigenvalues `λ₀ ≥ λ₁ ≥…`
  give

  ```
  ξ = 1 / ln(λ₀ / λ₁)
  ```

  the dominant correlation length at finite (D, χ). `ξ(χ)` grows with χ and
  saturates; near criticality it is cut off by finite χ (finite-entanglement
  scaling), which underlies the `D`/`χ` extrapolation schemes (§6).

---

## 6. Key parameters & convergence

| Parameter | Role | Typical handling |
|---|---|---|
| `D` (PEPS bond dim) | accuracy of the *ansatz* | increase until observables converge / extrapolate D→∞ |
| `χ` (CTM env dim) | accuracy of the *contraction* | take `χ ≳ D²`; converge observables in χ at fixed D |
| `τ` (Trotter step) | simple/full update step | decrease in stages (e.g. 1e-1 → 1e-4); extrapolate τ→0 |
| CTMRG threshold | env fixed point | corner-spectrum Δ < ~1e-8…1e-10; element-wise + gauge-fixed for AD |
| trunc. error `ε_T` | discarded CTM weight | keep `ε_T < ~1e-5`; auto-raise χ if exceeded |
| AD stability | SVD adjoint | regularize degenerate singular values; stable SVD backward |

**Two independent extrapolations.** Quote ground-state quantities only after:
1. **χ-convergence** at fixed D — repeat the curve for ≥2 values of χ; near
   criticality use several. Finite χ artificially rounds sharp features.
2. **D-extrapolation** — run a ladder of D (e.g. D = 2,3,4,5,6,…) and extrapolate
   energy / order parameter to D→∞. Correlation-length-based schemes
   (finite-correlation-length / finite-χ scaling) give controlled extrapolations
   and error bars (Corboz; Rader–Läuchli; Naumann §2.8.5).

**Common failure modes (Naumann §2.8):**
- χ too small → CTMRG inaccurate → AD *exploits* the inaccuracy and finds a false
  "ground state" with artificially low energy. Watch `ε_T`.
- Local minima → seed from simple/full update + add ~1e-2 relative noise; or
  restart from multiple random states and keep the best.
- Degenerate CTM singular values → SVD-adjoint divergence; regularize with a tiny
  random diagonal `X X⁻¹` on environment links, or use a symmetric/gauge-fixed
  scheme.
- Recycle environments between optimization steps once the gradient is small
  (tensors barely change) to cut CTMRG iterations.

---

## 7. Validation / benchmarks

**(a) 2D classical Ising as a partition-function check.** Square-lattice Ising
via CTMRG: sweep temperature, contract the single-layer network, and compare
against the exact results — critical temperature
`T_c = 2 / ln(1+√2) ≈ 2.269185` (`β_c = ½ ln(1+√2)`), the Onsager free energy,
and the Yang spontaneous magnetization `m = (1 − sinh⁻⁴(2β))^{1/8}` for `T<T_c`.
Show χ-convergence; finite χ rounds the transition (finite-entanglement scaling).
This validates the CTMRG contraction itself, independent of any PEPS optimization.

**(b) 2D square-lattice spin-½ Heisenberg energy per site vs QMC.** The standard
quantum benchmark. Reference (stochastic series expansion QMC, Sandvik):

```
e₀ = −0.669437(5)     (some refs: −0.6694421(4))   [J = 1, per site]
```

iPEPS/AD reproduces this closely: Liao–Liu–Wang–Xiang (2019) report PEPS at
**D=10** giving `e ≈ −0.66948(42)`, "state-of-the-art variational energy and
magnetization." Protocol: 2-sublattice (`[A B; B A]`) unit cell, increase D, take
`χ ≳ D²`, converge in χ, then extrapolate D→∞ and compare to the QMC value and to
the QMC sublattice magnetization `m ≈ 0.307`. Simple update slightly overshoots
(no loop correlations); CTMRG-based variational/full update is the variational,
upper-bound comparison.

Other published anchors (Naumann §4, all spin-½ AFM Heisenberg, energy/site, J=1):
honeycomb, kagome (`e ≈ −0.4365` at D=8 SU / VU range), triangular — useful for
frustrated-lattice cross-checks via the coarse-graining mappings of §2.

**Verification ladder for any iPEPS result** (matches the harness verification
practice): (1) trivial-parameter limit (e.g. decoupled bonds, classical limit);
(2) symmetry / expected sector and order pattern; (3) χ-convergence at fixed D;
(4) D-extrapolation with error bar; (5) cross-method — compare variational/full
update against simple update, or against QMC/DMRG where available; (6) literature
range for contested regimes (e.g. kagome spin liquid).

---

## 8. Reproduction-sufficiency assessment

**The harness KB folder `.knowledge/literature/peps-based-algorithm/` was EMPTY**
(only a stub `INDEX.md`) at the time of writing. This methodology was therefore
built from:

- **Web-fetched primary sources** (arXiv): Verstraete–Cirac cond-mat/0407066
  (PEPS ansatz), Orús–Vidal 0905.3225 (CTMRG for iPEPS contraction), Jordan–
  Orús–Vidal–Verstraete–Cirac cond-mat/0703788 (iPEPS + imaginary-time update),
  Corboz 1605.03006 (variational iPEPS), Liao–Liu–Wang–Xiang 1903.09650
  (differentiable-programming / AD iPEPS). For Verstraete–Cirac, Jordan et al.,
  and Corboz only the abstract/summary was retrievable via WebFetch; their
  detailed algorithmic content here is corroborated by the rendered review below.
- **One locally rendered review** read in full:
  `.knowledge/literature/software/2308.12358_an-introduction-to-infinite-projected-entangled-pair-state-m.md`
  (Naumann–Weerda–Rizzi–Eisert–Schmoll, SciPost Lect. Notes 2023) — the gold-
  standard methods reference for the CTMRG backbone, AD gradient at the fixed
  point, optimizers, pitfalls, and benchmarks. Section pointers (§2.2 CTMRG, §2.5
  AD-at-fixed-point, §2.6 optimization, §2.8 pitfalls, §4 benchmarks) are cited
  inline above.
- **Targeted web searches** for benchmark numbers (Sandvik QMC `e₀`, Liao et al.
  D=10 PEPS energy) and cost scaling.

**Sufficiency verdict.** This document is **reproduction-grade for the standard
workflows**: classical-Ising CTMRG (fully specified, exact-result validated),
simple/full-update imaginary-time optimization, and variational/AD ground-state
search with the χ/D convergence and verification discipline. The original CTMRG
and simple/full-update *equations at full diagrammatic detail* live in the cited
primary papers — for an exact-figure reproduction of any one of those papers,
ingest it under `.knowledge/literature/peps-based-algorithm/` (via
`download-ref`) and drive `/reproduce-paper` from the primary source, as the
method-PEPS card requires.

---

## 9. Source links

Primary methodology papers (to ingest into the KB — see INGEST block):

- Verstraete & Cirac, *Renormalization algorithms for quantum many-body systems
  in two and higher dimensions*, arXiv:cond-mat/0407066 (2004).
  https://arxiv.org/abs/cond-mat/0407066
- Orús & Vidal, *Simulation of two-dimensional quantum systems on an infinite
  lattice revisited: corner transfer matrix for tensor contraction*,
  Phys. Rev. B 80, 094403 (2009), arXiv:0905.3225.
  https://arxiv.org/abs/0905.3225
- Jordan, Orús, Vidal, Verstraete & Cirac, *Classical simulation of infinite-size
  quantum lattice systems in two spatial dimensions*, Phys. Rev. Lett. 101,
  250602 (2008), arXiv:cond-mat/0703788. https://arxiv.org/abs/cond-mat/0703788
- Corboz, *Variational optimization with infinite projected entangled-pair
  states*, Phys. Rev. B 94, 035133 (2016), arXiv:1605.03006.
  https://arxiv.org/abs/1605.03006
- Liao, Liu, Wang & Xiang, *Differentiable Programming Tensor Networks*,
  Phys. Rev. X 9, 031041 (2019), arXiv:1903.09650.
  https://arxiv.org/abs/1903.09650
- Phien, Bengua, Tuan, Corboz & Orús, *Infinite projected entangled pair states
  algorithm improved: fast full update and gauge fixing*, Phys. Rev. B 92,
  035142 (2015), arXiv:1503.05345. https://arxiv.org/abs/1503.05345

Benchmark reference:
- Sandvik, square-lattice spin-½ Heisenberg QMC, `e₀ = −0.669437(5)`
  (Phys. Rev. B 56, 11678 (1997) and later high-precision SSE updates).

Local rendered review (read in full):
- `.knowledge/literature/software/2308.12358_an-introduction-to-infinite-projected-entangled-pair-state-m.md`
  — Naumann et al., SciPost Phys. Lect. Notes 86 (2023), arXiv:2308.12358,
  DOI 10.21468/SciPostPhysLectNotes.86.

Software API (separate, not method): `skills/using-pepskit/references/pepskit-api.md`.
