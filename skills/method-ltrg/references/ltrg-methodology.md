# LTRG — Linearized Tensor Renormalization Group: reproduction-grade methodology

Finite-temperature thermodynamics of 1D (and quasi-1D / 2D) quantum lattice models by
Trotterizing the thermal density operator e^(−βH) into a classical tensor network, then
contracting it **layer by layer** (linearly, one Trotter slice per step) while truncating the
growing boundary with SVD to bond dimension Dc, in the infinite-time-evolving-block-decimation
(iTEBD) style.

Primary source: Li, Ran, Gong, Zhao, Xi, Ye, Su, *Linearized tensor renormalization group
algorithm for the calculation of thermodynamic properties of quantum lattice models*,
Phys. Rev. Lett. **106**, 127202 (2011), arXiv:1011.0155
(`.knowledge/literature/ltrg/1011.0155_linearized-tensor-renormalization-group-algorithm-for-the-ca.md`).
Extended scheme (bilayer LTRG++, finite + infinite size, TMRG equivalence): Dong, Chen, Han,
Li, Yang, Li, Phys. Rev. B **95**, 144428 (2017), arXiv:1612.01896. Exponential-cooling
successor (XTRG): Chen, Li, et al., Phys. Rev. X **8**, 031082 (2018), arXiv:1801.00142.

Notation throughout: β = inverse temperature; τ = Trotter step; M (a.k.a. K in the PRL) =
number of imaginary-time slices, β = Mτ; Dc = retained SVD bond dimension; q (a.k.a. D in the
PRL) = local Hilbert-space dimension (q = 2 for spin-½); λ = bond singular-value (diagonal)
matrix; Z = partition function; f = free energy per site.

---

## 1. Overview — finite-T from e^(−βH), and why a Trotterized tensor network

All equilibrium thermodynamics of a quantum lattice model follow from the partition function

```
Z(β) = Tr e^(−βH),     β = 1/T   (k_B = 1).
```

From Z one gets:

- **Free energy per site**:  f = −(1/Nβ) ln Z.
- **Internal energy per site**:  u = ⟨H⟩/N = Tr(H e^(−βH)) / (N·Z) = ∂(βf)/∂β.
- **Specific heat per site**:  C = ∂u/∂T = −β² ∂u/∂β = β²(⟨H²⟩ − ⟨H⟩²)/N.
- **Susceptibility** (uniform, to a field coupling operator A, e.g. A = Σᵢ Sᵢᶻ):
  χ = β(⟨A²⟩ − ⟨A⟩²)/N, or χ = −∂²f/∂h² at h → 0.

The obstruction is that e^(−βH) is the exponential of a sum of non-commuting local terms — it
has no closed local form. **Trotter–Suzuki decomposition** turns it into a *product* of local
imaginary-time gates exp(−τ hᵢ). Stacking M = β/τ such layers in the imaginary-time direction
on top of the L-site spatial chain produces a **(d+1)-dimensional classical tensor network**
(d space + 1 imaginary time) whose full contraction equals Z. LTRG is a prescription for
contracting that network *linearly* — absorbing one Trotter layer at a time into a boundary
matrix-product object and re-truncating — rather than by the exponential coarse-graining of the
original real-space TRG. The payoff: only O(Dc) singular values are discarded per step
(vs O(Dcⁿ) in coarse-graining TRG, n = 2 for a honeycomb network), and the scheme is
**sign-problem-free even in 2D**, making it a QMC alternative for frustrated/fermionic
thermodynamics. (arXiv:1011.0155, abstract + ¶"Our strategy"; FIG. 1 caption.)

---

## 2. Density operator → tensor network

### 2.1 Trotter–Suzuki splitting

Take a 1D Hamiltonian of nearest-neighbour terms,
H = Σᵢ hᵢ,ᵢ₊₁ (e.g. XY chain hᵢ,ᵢ₊₁ = −J(SᵢˣSᵢ₊₁ˣ + SᵢʸSᵢ₊₁ʸ)). Split into an even and an odd
bond group, H = H₁ + H₂, where all terms *within* H₁ commute and all within H₂ commute. The
symmetric (second-order) Trotter split of one slice of width τ = β/M is

```
e^(−τH) ≈ e^(−τH₁/2) e^(−τH₂) e^(−τH₁/2) + O(τ³)   per slice,
```

so the global error of Z is O(τ²). The PRL writes the simplest first-order form
Z ≈ Tr[ e^(−βH₁/K) e^(−βH₂/K) ]^K with K = M slices (arXiv:1011.0155 Eq. (2)); use the
symmetric split in practice to get O(τ²) instead of O(τ).

### 2.2 Local imaginary-time gate and the transfer tensor

Insert 2K = 2M complete local bases {|σᵢʲ⟩}, σ = 1…q, between layers (i = site index,
j = Trotter index). Each bond of the resulting network carries a σ index. The elementary object
is the **two-site gate / transfer tensor**, a 4th-order tensor of matrix elements of the local
imaginary-time evolution operator:

```
v_{σ₁σ₄, σ₂σ₃} ≡ ⟨σ₁ σ₄ | exp(−τ hᵢ,ᵢ₊₁) | σ₂ σ₃⟩
```

(arXiv:1011.0155 Eq. (3) and surrounding text; here σ₁σ₄ are the "bra/top" pair and σ₂σ₃ the
"ket/bottom" pair). Computing v requires exponentiating the 2-site (q²×q²) Hamiltonian block —
a small dense matrix exponential.

### 2.3 The (d+1)-D network and the MPO / "superket" picture

Periodic boundary conditions are assumed in *both* the spatial (σ₁ʲ = σ_{N+1}ʲ) and the
imaginary-time (σᵢ¹ = σᵢ^{2K+1}) directions. Laying out all the v-tensors gives a square
**transfer-matrix tensor network** (FIG. 1(a)), each bond = a σ index. Summing over all σ
(= contracting all bonds) yields Z.

Reading the network row by row, one row of gates is a **matrix product operator (MPO)** — a
chain of 4th-order M-tensors, each with two physical legs (top index *t*, bottom index *b*) in
the Trotter direction and two virtual/horizontal legs in the spatial direction. This row is the
discretized density operator at the current β; equivalently a "superket" in the operator
Hilbert space (Zwolak–Vidal). When the bra and ket layers are both kept it is a **matrix
product density operator (MPDO)**, ρ(β) ≈ MPDO with physical dimension q on each of the two legs
per site. (arXiv:1011.0155 ¶"which form a matrix product operator (MPO)"; the MPDO framing is
the bilayer LTRG++ language, arXiv:1612.01896.)

To prepare the gate for absorption, the 4th-order transfer tensor is SVD-factored into two
3rd-order tensors (FIG. 1(b)):

```
v_{σ₁σ₄, σ₂σ₃}  --SVD-->  Σ_x U_{σ₁σ₂, x} λ_x V_{σ₃σ₄, x}
(Ta)_{x,σ₁,σ₂} ≡ U_{σ₁σ₂,x} √λ_x ,   (Tb)_{x,σ₃,σ₄} ≡ V_{σ₃σ₄,x} √λ_x ,
```

where λ here collects up to q² singular values (the *gate* bond, not the truncated boundary
bond). This turns the square network into a hexagonal/brick-wall one with 3rd-order Ta, Tb
(arXiv:1011.0155, the v-SVD step and "two auxiliary tensors ... introduced for convenience").

---

## 3. Linearized contraction (the core of LTRG)

The boundary object is the bottom MPO/MPDO row: 4th-order M-tensors Ma, Mb on alternating
sites, with a diagonal **bond matrix λ₁, λ₂** assigned to each horizontal bond between Ma and
Mb. This is exactly Vidal's Γ–λ canonical form carried into imaginary time: M = Γ dressed by
neighbouring √λ, and the λ's are the singular-value (Schmidt) spectra of the boundary state.
**Carrying λ is what keeps the truncation quasi-optimal** — the SVD that discards small singular
values is performed in the correct (Schmidt) basis only because the λ's from neighbouring bonds
are present.

### 3.1 One projection (absorb one row of gates)

To add one Trotter layer, project a row of gate tensors Ta, Tb onto the boundary Ma, Mb. The
local update (FIG. 2):

1. **Contract** the σ-bonds joining the gate tensors to the boundary M-tensors → a 6th-order
   tensor O (FIG. 2(a)→(b)).
2. **Reshape (matricize)** O into a matrix grouping (left-virtual, top-physical, left-bond) ×
   (right-virtual, bottom-physical, right-bond):
   ```
   O_{yα b₁, zγ b₂}  ≈  Σ_{β'=1}^{Dc}  U_{yα b₁, β'} (λ'₂)_{β'} (V^⊤)_{β', zγ b₂}
   ```
   **SVD** it and **keep only the largest Dc singular values** λ'₂ (truncation). (arXiv:1011.0155
   the O-tensor SVD step.)
3. **Re-form** the canonical M-tensors by dividing out the *old* neighbouring bond matrix λ₁
   (Vidal-style, so the new bond carries the proper Schmidt weights):
   ```
   (Ma')_{α,y,β',b₁} = U_{yα b₁, β'} / (λ₁)_α
   (Mb')_{β',z,γ,b₂} = V_{zγ b₂, β'} / (λ₁)_γ
   ```
   and set the updated horizontal bond matrix to λ'₂. This half-updates the row.
4. **Project the next row** by swapping the roles Ma↔Mb and λ₁↔λ₂ and repeating steps 1–3.

Two successive projections = **one full Trotter step τ** (the system has advanced from β to
β+τ). Each step decimates the network *linearly*, discarding only O(Dc) singular values.
(arXiv:1011.0155 "These two successive projections make up of a full Trotter step τ".)

Cost: the local contract + SVD scales as **O(q⁶ · Dc³)** per step (PRL FIG. 2 caption: "O(D⁶
Dc³)" with D = q). This is the dominant cost.

### 3.2 Normalization and free-energy accumulation

Each SVD's singular-value vector λ is **normalized by its largest element nᵢ at step i** to
prevent the imaginary-time evolution from diverging (the bare singular values shrink
geometrically as β grows). The discarded factors nᵢ are *not thrown away* — they are logged.

After M projections (β = Mτ) the boundary is a matrix-product density operator. Trace out the
Trotter-direction physical legs t, b on each M-tensor (periodic in imaginary time) → a 1D
**matrix product** in the spatial direction, with site matrices c̃Ma, c̃Mb (FIG. 3(c)→(d)).
Assume 2^p such matrices. Contract them **pairwise** (FIG. 3(d)→(g)): 2^p → 2^{p−1} → … → 1 in
p steps (logarithmic in chain length), normalizing each intermediate matrix by the absolute
value of its largest element and logging that factor m_j (j = 1…p). The trace of the final
single matrix completes Z.

**Free energy from the logged factors.** The PRL gives f (per site, β = Kτ) as a sum over the
two families of normalization factors — the per-Trotter-step factors {nⱼ} and the spatial
matrix-RG factors {mⱼ}. Schematically (the explicit Eq. (7) is rendered as a figure in the KB
file; reconstructed from the bookkeeping):

```
ln Z  =  Σ_i (counts_i · ln n_i)  +  Σ_j (counts_j · ln m_j)  +  ln(trace of final matrix)
f  =  −(1/Nβ) ln Z
```

The load-bearing discipline (PRL "all the normalization factors ... need to be collected"):
**every rescaling factor is counted exactly once**, with the correct multiplicity (a factor
pulled out before a pairwise spatial contraction multiplies all the matrices below it). A
divergent or double-counted factor is the single most common LTRG bug — see §5.

---

## 4. Observables

### 4.1 Free energy

f = −(1/Nβ) ln Z directly from §3.2. This is the *primary* output; everything else can be
derived from it.

### 4.2 Internal energy, specific heat, susceptibility — two routes

The PRL states there are "at least two ways", of "similar accuracy" (arXiv:1011.0155
¶"Besides the free energy"):

**(a) Numerical differentiation of f.** Compute f(β) on a β-grid (one LTRG run reaching β
produces f at all intermediate β for free — they are the partial traces), then

```
u(β) = ∂(βf)/∂β ,    C(T) = −β² ∂u/∂β ,    χ(T) = −∂²f/∂h²|_{h→0}.
```

For χ, add a field term −h·A to H (e.g. A = Σ Sᵢᶻ), recompute f(h) for a few small h, and take
the second numerical derivative. Differentiation amplifies noise, so this needs a smooth,
well-converged f (large Dc, small τ).

**(b) Impurity-tensor insertion (direct expectation values).** Replace one (or two) gate
tensor(s) in the network by an "impurity" tensor carrying the operator of interest, e.g. the
local energy term hᵢ,ᵢ₊₁ for u, or Sᵢᶻ for magnetization, then contract the modified network and
divide by Z:

```
⟨A⟩ = Tr(A e^(−βH)) / Z = (contraction of network with A-impurity) / (clean contraction).
```

For C and χ as variances, insert two operators (⟨H²⟩, ⟨A²⟩). Direct insertion avoids the
numerical-derivative noise but requires extra contractions per observable. (This is the iTEBD
"impurity tensor" technique, PRL cites Vidal; FIG. 5(b) and FIG. 6 compare both routes against
the exact XY solution and against ALPS QMC for the honeycomb model.)

---

## 5. Key parameters & convergence

| Knob | Symbol | Controls | How it moves the result |
|---|---|---|---|
| Trotter step | τ | slice width, β = Mτ | error O(τ²) (symmetric split); **dominates high-T** (T > 0.2 J). PRL uses τ = 0.1, 0.05, 0.02, 0.01. Smaller τ → more layers → more truncations. |
| # slices | M (=K) | β = Mτ | more slices reach lower T but accumulate more SVD truncations. |
| bond dim | Dc | retained SVD states | dominant accuracy/cost lever (role of M in TMRG); **dominates low-T** truncation error. PRL uses Dc = 50, 100, 150. |
| local dim | q (=D) | transfer-tensor size | fixed by physics (q = 2 spin-½); enters cost as q⁶. Do not confuse with Dc. |
| contraction direction | — | Trotter-first vs spatial-first | two equivalent schemes; the PRL notes you may decimate the spatial direction first and contract Trotter second. |
| normalization | nᵢ, mⱼ | scale bookkeeping | divide each SVD spectrum by its largest singular value; each spatial matrix by its largest element; collect logs for Z/f. |

**Where each error lives (the central convergence insight):**
- **High T (T ≳ 0.2 J): Trotter error.** δf saturates rapidly with Dc — adding bond dimension
  does not help; only τ → 0 does. (PRL FIG. 4: Dc = 100 and 150 curves coincide.)
- **Low T (large β): truncation error.** δf keeps improving with Dc; τ is already small enough.
  (PRL FIG. 5(a): accuracy "remarkably improved by increasing Dc".)

**Convergence protocol (do both, always):**
1. **Dc scaling** — recompute the observable at Dc = 50, 100, 150, …; converged when successive
   curves coincide (PRL: Dc = 100 ≈ 150). Track discarded singular weight per SVD; it should be
   small and shrink as Dc grows.
2. **τ → 0 extrapolation** — recompute at τ = 0.1, 0.05, 0.02, 0.01 and extrapolate linearly in
   τ² (symmetric split). Mandatory at high T.
3. **Intermediate sanity** — per-step normalization nᵢ stays finite and varies smoothly on a log
   scale; a divergence signals a missing/double-counted normalization.

A single (τ, Dc) number with neither study is not a result.

---

## 6. Variants (brief)

- **Bilayer LTRG++** (arXiv:1612.01896, PRB 95, 144428). Single-layer LTRG evolves one layer
  (the "superket"), so the represented density operator is **not manifestly positive** and is
  slightly asymmetric. LTRG++ evolves **bra and ket layers together** (a true MPDO ρ = X†X form),
  restoring positivity and significantly improving accuracy in both finite- and infinite-size
  systems. Key structural result: **infinite-size LTRG++ ≡ TMRG** (transfer-matrix
  renormalization group) re-expressed in tensor-network language. Unlike TMRG, LTRG/LTRG++ treats
  **finite** chains directly. Demonstrated on the extended fermionic Hubbard model (phase
  separation, magnetocaloric effect).
- **2D LTRG.** The same linear-decimation contraction applies to a (2+1)-D network. The PRL's
  scalability demo is the spin-½ Heisenberg antiferromagnet on a **honeycomb** lattice (two-site
  unit cell), H = J Σ_{⟨i,j⟩} Sᵢ·S_j + h_s Σᵢ(−1)^|i| Sᵢᶻ, benchmarked against ALPS QMC (FIG.
  6(b)). The honeycomb's bipartite/two-sublattice structure maps naturally onto the Ma/Mb
  alternating-tensor brick wall; wider 2D geometries are the regime where successor methods
  (XTRG on cylinders, finite-T PEPS, tanTRG) take over.
- **XTRG** (exponential TRG, arXiv:1801.00142, PRX 8, 031082). Replaces *linear* cooling
  (LTRG: add one Trotter layer per step, M = β/τ steps) with **exponential** cooling: square the
  thermal MPO, ρ(2β) ← ρ(β)·ρ(β), reaching β in ≈ log₂(β/τ₀) steps. Far fewer truncations → both
  lower T *and* better accuracy; runs on 2D cylinders. The MPO·MPO product + re-truncation
  replaces the layer-absorption step. Same Z/f bookkeeping, but rescaling factors double per
  step. Trotter-error-free variant: SETTN (series expansion, arXiv:1609.01263).

---

## 7. Validation / benchmarks

From the primary PRL (quantum XY spin-½ chain, J = 1, chain length 2¹⁰⁰ ≈ thermodynamic limit):

- **Free energy vs exact XY solution.** δf = |(f − f_exact)/f_exact| converges rapidly with Dc.
  At high T, LTRG matches TMRG (M = 60, 100) for τ = 0.1, 0.05. At **β = 120 (T/J ≈ 0.008),
  τ = 0.05, Dc = 150: δf ≈ 7×10⁻⁶** (FIG. 5(a)). *(Harness benchmark target.)*
- **Internal energy.** (e − e₀)/e₀ ≈ 10⁻⁴ at β = 120, Dc = 150 — i.e. β → large recovers the
  ground-state energy e₀. LTRG and TMRG (up to M = 200) agree to the same order down to β = 120
  (FIG. 5(b)).
- **Specific heat C.** Agrees with the exact solution at high and low T; for Dc = 150 the LTRG
  curve coincides with exact down to T/J ≈ 0.008 (FIG. 6(a)).
- **2D scalability.** Honeycomb Heisenberg energy per site vs staggered field h_s shows
  "pronounced agreement" with ALPS QMC (FIG. 6(b)).

Reproduction recipe: XY chain, J = 1, q = 2; sweep (τ, Dc) ∈ {0.1, 0.05, 0.02, 0.01} ×
{50, 100, 150}; compute f, u, C on a β-grid up to β = 120; compare to the closed-form XY free
energy f_exact(T) = −(T/π) ∫₀^π ln[2 cosh(βε_k/2)] dk with ε_k = J cos k (Jordan–Wigner /
free-fermion solution). Confirm δf hits ~7×10⁻⁶ at β = 120, Dc = 150.

---

## 8. Reproduction-sufficiency assessment

**Verdict: reproduction-sufficient for the 1D linear-cooling algorithm; the single KB PRL alone
is borderline and was supplemented from the web for two gaps.**

What the single PRL (arXiv:1011.0155) covers well enough to reimplement the 1D method:
the Trotter split, the transfer/gate tensor v, the gate SVD into Ta/Tb, the Γ–λ boundary, the
per-row projection (contract → 6th-order O → SVD → re-form M with λ-division → swap and repeat),
the linear decimation discarding O(Dc) per step, the nᵢ/mⱼ normalization scheme, the pairwise
spatial matrix-RG trace, the O(q⁶Dc³) cost, the two observable routes, and the XY/honeycomb
benchmarks with concrete (τ, Dc) and error numbers.

Gaps in the single PRL, and how they were filled:
1. **Explicit free-energy equation.** PRL Eq. (7) (the f-from-{nⱼ},{mⱼ} formula) is an OCR'd
   *image* in the KB markdown, so the exact closed form is not machine-readable. §3.2 reconstructs
   the bookkeeping (each factor counted once, with multiplicity) from the surrounding text; the
   structural form f = −(1/Nβ)ln Z with ln Z = Σ logs + ln(final trace) is unambiguous, but a
   reimplementer should cross-check signs/multiplicities against a known analytic limit (the §7
   XY benchmark is exactly this check).
2. **Bilayer / positivity & 2D extension depth.** The PRL gives only a single-paragraph 2D demo
   and no bilayer treatment. Filled from arXiv:1612.01896 (LTRG++ = bra+ket layers, manifest
   positivity, ≡ TMRG at infinite size, finite-size capable) and arXiv:1801.00142 (XTRG
   exponential-cooling contrast) — abstract-level confirmation only (the PDFs did not decode for
   full-text extraction), which is enough to state *what* each variant changes and *why*, but a
   full LTRG++/XTRG *reimplementation* would need the respective full papers.

Net: enough to build, run, and validate the canonical 1D LTRG (the harness's primary use) end to
end against the exact XY benchmark. For the bilayer or low-T exponential-cooling variants, pull
the successor full texts before coding.

---

## 9. Source links

KB (relative to repo root):
- `.knowledge/literature/ltrg/1011.0155_linearized-tensor-renormalization-group-algorithm-for-the-ca.md` — Li et al. 2011, the primary LTRG PRL.
- `.knowledge/literature/ltrg/INDEX.md`

Skill card:
- `skills/method-ltrg/SKILL.md` (this reference is its `references/` companion).

Web (consulted for the extended scheme; abstract-level):
- LTRG PRL: https://arxiv.org/abs/1011.0155 — DOI 10.1103/PhysRevLett.106.127202
- Bilayer LTRG++: https://arxiv.org/abs/1612.01896 — PRB 95, 144428 (2017)
- XTRG (exponential cooling): https://arxiv.org/abs/1801.00142 — PRX 8, 031082 (2018)
- SETTN (Trotter-error-free): https://arxiv.org/abs/1609.01263 — PRB 95, 161104(R) (2017)
- tanTRG (finite-T 2D Hubbard): https://arxiv.org/abs/2212.11973 — PRL 130, 226502 (2023)

Tool/runtime: `/using-itensors` (ITensors.jl primitives — typed indices, gate exponentiation,
`svd` to maxdim = Dc, incremental writes) expresses every step above.
