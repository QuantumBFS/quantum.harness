---
title: "Challenge 73 Plan (2026-07-30): Resolvent Route to Berry Curvature"
date: 2026-07-30
status: active
supersedes: "Challenge 73 - Final Report.md (production route only; results retained)"
tags:
  - challenge-73
  - berry-curvature
  - tfim
  - performance
---

# Challenge 73 Plan: The Resolvent Route

## 0. One sentence

The Berry curvature this challenge asks for is **exactly** one inverse moment of
one spectral function, so the entire 2D `(θ, Ω)` parameter grid, every Wilson
loop, every state overlap, and all complex arithmetic can be deleted — which
converts the challenge from a compute problem into a linear-algebra problem and
unblocks PEPS, QMC, and larger ED simultaneously.

---

## 1. The identity

### 1.1 Statement

Let

    H(θ, λ) = R(θ) H₀(λ) R(θ)†,        R(θ) = exp(−i (θ/2) Σᵢ Xᵢ) = exp(−i θ G),
    G ≡ ½ Σᵢ Xᵢ,
    H₀(λ) = −J Σ_⟨ij⟩ ZᵢZⱼ − Ω Σᵢ Xᵢ + Δ Σᵢ Zᵢ,      λ ∈ {Ω, Δ, J},

with `H₀` real symmetric in the σᶻ basis and a non-degenerate ground state
`|0(λ)⟩`, chosen real. Then `|ψ(θ,λ)⟩ = R(θ)|0(λ)⟩` is the ground state of
`H(θ,λ)`, and in this gauge

    A_θ = i⟨ψ|∂_θ ψ⟩ = ⟨0|G|0⟩ = ½⟨Σ Xᵢ⟩       (independent of θ, since [R, G] = 0)
    A_λ = i⟨ψ|∂_λ ψ⟩ = i⟨0|∂_λ 0⟩ = 0          (real normalised state)

Therefore

    ┌────────────────────────────────────────────────────────────┐
    │  F_θλ = ∂_θ A_λ − ∂_λ A_θ = −½ ∂_λ ⟨Σ Xᵢ⟩                   │
    │  F_λλ' = 0   for any two non-θ parameters                   │
    └────────────────────────────────────────────────────────────┘

For `λ = Ω`, Hellmann–Feynman gives `⟨ΣX⟩ = −∂E₀/∂Ω`, hence the closed form

    ┌────────────────────────────────────────────────────────────┐
    │  F_θΩ = ½ ∂²E₀/∂Ω²  =  −½ χ_x  =  −⟨b|(H₀−E₀)⁻¹|b⟩ ≤ 0     │
    │  with |b⟩ = Q ΣXᵢ |0⟩,  Q = 1 − |0⟩⟨0|                      │
    └────────────────────────────────────────────────────────────┘

`χ_x ≥ 0` is the static transverse susceptibility, so the curvature is
**negative-definite by construction** — the reported sign is a theorem, not an
observation. `E₀(Ω)` is concave (an infimum of linear functions), and
`E₀ → −ΩN` as `Ω → ∞`, so `F → 0` in the polarised limit: also a theorem.

### 1.2 Corollaries that reproduce the existing report

- **Rydberg `F ≡ 0`**: the Rydberg generator is `G' = ½ΣZ`, so
  `F_φλ = −½ ∂_λ⟨ΣZ⟩ = 0` because `⟨ΣZ⟩ ≡ 0` by ℤ₂ at `Δ = 0`. The "exact
  zero" found in Stage 5 is this corollary.
- **`F_θΔ` at `Δ = 0` vanishes**: `|b_X⟩ = QΣX|0⟩` is ℤ₂-even,
  `|b_Δ⟩ = QΣZ|0⟩` is ℤ₂-odd, so their overlap through the resolvent is zero.
  It turns on only at `Δ ≠ 0`.
- **General mixed component**:
  `F_θλ = ⟨b_X|(H₀−E₀)⁻¹|b_λ⟩` with `|b_λ⟩ = Q (∂_λH₀)|0⟩` — one extra linear
  solve per additional parameter.

### 1.3 Numerical verification (done, cheap, reproducible)

Against the 1D Jordan–Wigner oracle values quoted in the Final Report §3.1
(`J = 1`, PBC chain), predicting `F̄ = (1/2N) ∂²E₀/∂Ω²`:

| N | Ω | this identity | report (JW oracle) | diff |
|---|---|---|---|---|
| 4 | 1.0 | −0.298619 | −0.2986 | 1.9e−5 |
| 6 | 1.0 | −0.365112 | −0.3651 | 1.2e−5 |
| 4 | 1.5 | −0.114286 | −0.1143 | 1.4e−5 |
| 6 | 1.5 | −0.110550 | −0.1106 | 5.0e−5 |

All four agree to the rounding level of the published table. On the actual 2D
square lattice, against Final Report Tables 1 and 3:

| L | Ω | this identity | report (FHS) | rel. diff | note |
|---|---|---|---|---|---|
| 3 | 1.000 | −0.130272 | −0.1296 | 0.5% | fine grid (dθ=0.04, dΩ=0.10) |
| 4 | 1.000 | −0.129093 | −0.1282 | 0.7% | |
| 4 | 2.500 | −0.196742 | −0.1914 | 2.8% | coarse grid begins to bite |
| 4 | 3.000 | −0.103777 | −0.1330 | **22.0%** | critical region |
| 4 | 3.044 | −0.094629 | −0.0803 | **17.8%** | critical region |
| 4 | 3.500 | −0.037559 | −0.0479 | **21.6%** | |
| 4 | 4.000 | −0.017192 | −0.0205 | 16.1% | |
| 4 | 5.000 | −0.006083 | −0.0067 | 9.2% | |

**This is a finding, not just a validation.** The exact values are smooth and
monotone through the critical region; the published `L = 4` FHS values are not
(they jump 40% between Ω = 3.000 and Ω = 3.044, where the exact answer moves
9%). The `L = 4` production grid (`dθ = 0.10`, `dΩ = 0.25`, 54 plaquettes) has
16–22% discretisation error exactly where the challenge asks for the answer
(quantity #4, critical-region behaviour). The `L = 2, 3` fine grids are sound.

Reproduction script: §8.

### 1.4 What the existing code already knew, and what it missed

`src/berry.cpp:727` already carries the comment *"F_{θΩ} is independent of θ by
the unitary-rotation argument"* and already builds the real symmetric `H₀`.
The sum-over-states expression implemented there,
`F = −Σ_{n≠0} |⟨n|ΣX|0⟩|²/(Eₙ−E₀)`, **is** the identity above.

What was missed is purely computational, and it is where all the cost went:

1. it is evaluated by **full dense diagonalisation** (`jacobi_eigen`) with a
   hard cap `checked_dimension(lattice, 64, ...)` → `N ≤ 6`;
2. the sum over all `n` is unnecessary — it is one resolvent applied to one
   vector, i.e. **one linear solve**, matrix-free, no spectrum;
3. consequently the routine was used only as a ≤6-site validation oracle,
   while the **production** route stayed the FHS Wilson loop on the full 2D
   `(θ, Ω)` grid with complex Lanczos (450 plaquettes at `L = 2, 3`; 54 at
   `L = 4`).

Promoting the response formula from oracle to production route, and evaluating
it by CG instead of full diagonalisation, is the whole plan.

---

## 2. Performance ledger

| axis | current production route | resolvent route | factor |
|---|---|---|---|
| parameter grid | 2D `(θ,Ω)`, 450 plaquettes × 4 ground states | 1D `Ω` scan, ~40 points | ~10–50× fewer solves |
| per-point solver | complex Hermitian Lanczos | real symmetric Lanczos + CG | ~2–4× flops, 2× memory |
| spectrum needed | full (`jacobi_eigen`) in the oracle | none — one linear solve | O(dim²) → O(dim) memory |
| `θ` discretisation error | 0.5% (fine grid) → 22% (`L=4` grid) | **identically zero** | removes dominant systematic |
| `Ω` derivative | finite difference on the scan grid | CG resolvent, machine precision | removes the grid-resolution limit on quantity #4 |
| symmetry | none | ℤ₂ spin-flip (×2), `k=0` momentum (×N) | `N ≤ 16` → `N = 25` |
| iPEPS | needs Zygote AD **and** mixed-state overlaps + FHS plaquette | SimpleUpdate/FullUpdate + CTMRG `⟨σˣ⟩`, no AD, no overlaps | unblocks `D ≥ 3` |
| QMC | QAQMC, not implemented | operator-count fluctuation in existing SSE | `L = 8…20` |

Matvec accounting at fixed `N`: FHS route ≈ 450 plaquettes × 4 Lanczos × ~200
matvecs ≈ 3.6e5 **complex** matvecs. Resolvent route ≈ 40 points × (Lanczos +
CG + chain ≈ 500) ≈ 2.0e4 **real** matvecs. Estimated **~40–70× total**, before
symmetry. Treat as an estimate until measured; the exactness claims in rows 4–5
are not estimates.

ED reach (double precision, one vector = 8·dim bytes):

| L | N | dim | ℤ₂ sector | vector | peak (≈6 vectors) | verdict |
|---|---|---|---|---|---|---|
| 4 | 16 | 6.6e4 | 3.3e4 | 0.3 MB | trivial | seconds |
| 5 | 25 | 3.4e7 | 1.7e7 | 134 MB | ~0.8 GB | **new size, fits this workstation** |
| 5 | 25 | + `k=0` | ~6.7e5 | 5 MB | trivial | seconds, if momentum implemented |
| 6 | 36 | 6.9e10 | — | — | — | out of ED reach; QMC/iPEPS |

Tilted clusters (`N = 18, 20, 26`) are also available and give the ≥5 lattice
sizes the Final Report §9 says 3D-Ising scaling needs.

---

## 3. Architecture

### 3.1 Layout

Home: `tracks/qmc/solutions/LlmNewtonGaussTuring/` (where `berry.*`, `ed.*`,
`lattice.*`, `sse.*` already live) plus
`tracks/peps/solutions/LlmNewtonGaussTuring/` for Julia.

```
core/
  lattice.{hpp,cpp}     KEEP unchanged — square/chain/tilted geometry
  hilbert.{hpp,cpp}     NEW  basis + Z2 spin-flip sector (+ optional k=0)
  matfree.{hpp,cpp}     NEW  matrix-free H0 and ΣX apply, O(dim) memory
  lanczos_real.{hpp,cpp} NEW real symmetric ground state + continued fraction
  cg.{hpp,cpp}          NEW  projected conjugate gradient
routes/
  exact/scan_curvature.cpp   NEW  ← the new production tool
  fhs/berry.{hpp,cpp}        KEEP — demoted to oracle + Δ-general route
  qmc/sse_chi.{hpp,cpp}      NEW  ← extends existing sse.cpp
  ipeps/ipeps_mx.jl          NEW  ← replaces the blocked overlap/FHS path
tools/
  analyze_berry_scaling.py   KEEP, extended to more sizes
tests/
  test_identity.cpp     NEW  resolvent vs FHS vs dense response, N ≤ 10
  test_jw.cpp           KEEP 1D analytic
```

### 3.2 Matrix-free operator

```cpp
// core/matfree.hpp
struct TFIMOperator {
    const Lattice& lat;
    double J, Omega, Delta;
    std::size_t dim;
    std::vector<double> diag;          // −J ΣZZ + Δ ΣZ, precomputed once, O(dim)

    void apply(const double* x, double* y) const;              // y = H0 x
    void apply_shifted(const double* x, double* y, double s) const;  // y = (H0 − s) x
};

void apply_sum_sx(const Lattice&, const double* x, double* y);       // y = (Σᵢ Xᵢ) x
void apply_sum_sz(const Lattice&, const double* x, double* y);       // y = (Σᵢ Zᵢ) x
```

Cost per `apply`: `O(dim)` diagonal + `O(N·dim)` bit-flip gathers. Memory:
one `O(dim)` diagonal array. No matrix is ever stored — this is the single
change that lifts `N ≤ 6` to `N = 25`. Parallelise the `X` loop with OpenMP
over state index; the flip `st ^ (1<<i)` is a scatter-free gather.

### 3.3 Solvers

```cpp
// core/lanczos_real.hpp
struct GroundStateReal { double energy; std::vector<double> vec; int iters; double resid; };
GroundStateReal lanczos_ground_state(const TFIMOperator&, int max_iter,
                                     double tol, std::uint64_t seed);

// Continued fraction from a seed vector: ALL inverse moments in one run.
struct LanczosChain { std::vector<double> alpha, beta; double norm2; };
LanczosChain lanczos_chain(const TFIMOperator&, const std::vector<double>& seed, int m);
double inverse_moment(const LanczosChain&, double E0, int p);   // ∫ S(ω) ω^{−p} dω
```

```cpp
// core/cg.hpp
// Solve (H0 − E0) φ = b restricted to the complement of ψ0. (H0−E0) ⪰ 0 and is
// positive definite on Q, so CG is the right method; reproject every iteration.
int projected_cg(const TFIMOperator& H, const std::vector<double>& psi0,
                 const std::vector<double>& b, std::vector<double>& phi,
                 int max_iter, double tol);
```

### 3.4 The production tool

```cpp
// routes/exact/scan_curvature.cpp
for (double Omega : grid) {
    TFIMOperator H{lat, J, Omega, Delta};
    auto gs   = lanczos_ground_state(H, ...);           // E0, |0⟩
    double sx = dot(gs.vec, apply_sum_sx(gs.vec));      // ⟨ΣX⟩
    auto b    = apply_sum_sx(gs.vec) - sx * gs.vec;     // |b⟩ = Q ΣX |0⟩
    projected_cg(H, gs.vec, b, phi, ...);               // (H0−E0) φ = b
    double F  = -dot(b, phi);                           // F_θΩ   EXACT
    auto ch   = lanczos_chain(H, b, m);                 // spectral function of ΣX
    // p = 1 → F (cross-check against CG); p = 2 → χ_F; p ≥ 3 → rate corrections
    emit(Omega, gs.energy, sx / N, F / N,
         inverse_moment(ch, gs.energy, 2), inverse_moment(ch, gs.energy, 3));
}
```

One Lanczos + one CG + one chain per `Ω` point. The chain and the CG compute
`F` by two independent algorithms — a free internal consistency check on every
data point.

### 3.5 QMC route (reuses the existing SSE)

For `H ⊃ −Ω Σᵢ σˣᵢ`, the SSE weight carries `Ω^{n_x}` where `n_x` is the number
of off-diagonal single-site operators. Then `∂ln Z/∂Ω = ⟨n_x⟩/Ω`, and

    ⟨Σ σˣ⟩ = ⟨n_x⟩ / (β Ω)
    F_θΩ   = ½ ∂²E₀/∂Ω² = − ( ⟨n_x²⟩ − ⟨n_x⟩² − ⟨n_x⟩ ) / (2 β Ω²)

A pure **operator-counting** estimator: no correlation function, no
imaginary-time integration, essentially free to add to the existing
square-lattice SSE in `src/sse.cpp` (already validated at the square-lattice
critical point `h_c = 3.04438` in Stage 3). Requires `βΔ_gap ≫ 1` for the
ground-state limit; use `β = 2L` with `z = 1` as in Challenge 148, and check
`β`-convergence at one size. Valid for `Ω > Ω_c`; below `Ω_c` the finite-size
ground doublet must be handled explicitly (see §6).

This is direct reuse of Challenge 148 infrastructure — same model, same lattice
builder, same binning.

### 3.6 iPEPS route (the unblock)

`F̄ = −½ ∂m_x/∂Ω` where `m_x = ⟨σˣ⟩` per site. Therefore iPEPS needs only a
**single-site expectation value**, not mixed-state overlaps and not a Wilson
loop:

```
for Ω in grid:
    SimpleUpdate (imaginary time, no AD)      # ~30 s at D=2 per Final Report
    → FullUpdate refinement (no AD)           # optional, variational quality
    → CTMRG environment (no AD)
    → measure ⟨σˣ⟩  →  m_x(Ω)
F̄ = −½ dm_x/dΩ   (finite difference, ΔΩ ≈ 0.05)
```

This removes all three blockers at once: no Zygote AD (so the >90 min JIT
timeout that killed `D ≥ 3` is irrelevant), no mixed-iPEPS overlap contraction
(the open software task), no FHS plaquette assembly. First derivative of a
measured quantity is far better conditioned than second derivative of an
energy: `m_x` to 1e−6 over `ΔΩ = 0.05` gives `∂m_x/∂Ω` to ~1e−4.

Convergence study becomes the honest `D`-and-`χ` extrapolation the challenge
actually asks for (quantity #3), now reachable at `D = 2,3,4,5,6`.

---

## 4. Requirement coverage

| # | Issue requirement | before | after this plan |
|---|---|---|---|
| 1 | Berry phase along closed loops | Yes (FHS) | Yes, and **exact**: `φ = Δθ·[A_θ(λ₁) − A_θ(λ₂)]` with `A_θ = ½⟨ΣX⟩` |
| 2 | Local curvature density over the manifold | Yes | Yes, exact, no `Δθ` error, arbitrary `Ω` resolution |
| 3 | iPEPS convergence in `D`, `χ`, discretisation | Partial (`D=2` only) | **Unblocked** — AD-free path to `D ≥ 3`; discretisation error is now zero in `θ` |
| 4 | Behaviour near the 2D Ising critical region | Partial (grid-limited; now shown to carry 16–22% error at `L=4`) | Exact derivative at every `Ω`; ED to `L=5`, QMC to `L≈20` |
| 5 | Finite-rate correction under slow evolution | **Not attempted** | Leading orders delivered: inverse moments `M_p` give `χ_F` (`p=2`) and the adiabaticity threshold `v* ∼ χ_F^{−1/2}`; full non-perturbative dynamics still needs TDVP/QAQMC (see §6) |
| A | Kolodrubetz parameterisation | Yes | Yes (this is the parameterisation the identity applies to) |
| B | Rydberg parameterisation | Yes (`F ≡ 0`) | Yes, now as a corollary of the general theorem |
| C | Longitudinal field `Δ ≠ 0` | Not done | One extra CG solve per point: `F_θΔ = ⟨b_X|(H₀−E₀)⁻¹|b_Δ⟩` |
| — | PEPS as *primary prescribed* method | Partial | Primary route becomes genuinely runnable at production `D` |

---

## 5. Phased implementation

| phase | work | output | est. effort |
|---|---|---|---|
| **P0** | `matfree` + `lanczos_real` + `projected_cg`; `test_identity.cpp` against existing dense `compute_berry_curvature_response_ed` and FHS at `N ≤ 10` | exact route validated | 0.5 day |
| **P1** | `scan_curvature.cpp`; rerun `L = 2,3,4` on a dense `Ω` grid | corrected `L=4` critical-region table, replacing the 16–22%-error data | 0.5 day |
| **P2** | ℤ₂ sector in `hilbert.*`; run `L = 5` (`N = 25`) | 4th lattice size; `1/L` fit on 4 points | 0.5 day |
| **P3** | `lanczos_chain` + `inverse_moment`; emit `χ_F` and rate coefficients | quantity #5 leading orders, adiabaticity criterion | 0.5 day |
| **P4** | `sse_chi` in existing SSE; `L = 6, 8, 12, 16, 20` | QMC route complete; ≥5 sizes for 3D-Ising scaling | 1 day |
| **P5** | `ipeps_mx.jl`: SimpleUpdate → CTMRG `⟨σˣ⟩` at `D = 2…6` | quantity #3 unblocked, PEPS as primary method | 1 day |
| **P6** | `Δ ≠ 0`: second CG solve; `k=0` momentum sector if `L=5` proves too slow | quantity C; ED headroom | 0.5 day |

P0–P2 alone already replace the weakest published numbers and add a lattice
size. P4 and P5 are what close the two "partial" requirement rows.

Cross-validation matrix to maintain throughout — every entry must agree:

|  | dense response (`N≤6`) | FHS Wilson loop | resolvent CG | Lanczos chain | SSE | iPEPS |
|---|---|---|---|---|---|---|
| 1D chain `N=6` | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| square `L=3` | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| square `L=4` | — | ✓ | ✓ | ✓ | ✓ | — |
| square `L=5` | — | — | ✓ | ✓ | ✓ | — |
| thermodynamic | — | — | — | — | ✓ | ✓ |

---

## 6. Risks and honest caveats

| risk | assessment / mitigation |
|---|---|
| **Ground-state degeneracy for `Ω < Ω_c`** | The FM phase has an exponentially small finite-size gap; `F` is only defined for a non-degenerate state. CG will be ill-conditioned there. Mitigation: work in the ℤ₂-even sector (the true finite-`N` ground state is unique there), report the gap alongside every point, and flag points where `E₁−E₀` is below tolerance. The published thermodynamic-limit extrapolation lives at `Ω ≥ 3.5`, safely paramagnetic. |
| CG convergence near `Ω_c` | The gap closes as `L^{−z}`, so CG iterations grow like `√κ`. Still far cheaper than 450 ground-state solves. Mitigation: Jacobi (diagonal) preconditioner; the Lanczos-chain evaluation of the same quantity is gap-robust and serves as a fallback and cross-check. |
| Identity assumes the rotation acts on **all** of `H₀` | If the issue intends `Δ` outside the rotation, `A_θ = ½⟨ΣX⟩` still holds but `A_λ = 0` may not. Mitigation: the FHS route is retained precisely for parameterisations that are not of the form `R(θ)H₀(λ)R(θ)†`, and `test_identity.cpp` will detect any mismatch. |
| Quantity #5 is only solved to leading orders | Stated plainly: the moment expansion gives the adiabatic-response coefficients and the breakdown rate, not the full finite-rate dynamics. A genuine finite-rate simulation still requires TDVP or QAQMC. Do not claim #5 is "complete". |
| SSE `β → ∞` control | `F` is a ground-state quantity; the estimator is a finite-`T` susceptibility. Requires an explicit `β`-convergence check at one `(L, Ω)`, as in Challenge 148. |
| iPEPS SimpleUpdate is not variational | `m_x` from a SimpleUpdate state is biased. Mitigation: FullUpdate refinement, and `D`-convergence is the actual deliverable — report `m_x(D)` and extrapolate rather than quoting one `D`. |
| Re-deriving results already reported | The `L = 2, 3` numbers stand and are reproduced to 0.5%. Only the `L = 4` critical-region grid is superseded, and the reason is documented and quantified. Frame it as a correction with evidence, not as a retraction. |

---

## 7. What to reuse versus retire

**Keep unchanged**: `lattice.{hpp,cpp}` (geometry, tilted clusters),
`ed.{hpp,cpp}` (dense Jacobi as the `N ≤ 6` oracle), the 1D JW analytic
formula, `analyze_berry_scaling.py`, all Stage 0–5 reports.

**Keep, demoted in role**: `berry.{hpp,cpp}` FHS Wilson-loop machinery — now
the oracle for the identity, the route for parameterisations outside the
theorem's scope, and the `Δ ≠ 0` cross-check. Its complex Lanczos is no longer
on the hot path.

**Retire from the hot path**: the 2D `(θ, Ω)` production grid in
`scan_berry_square.cpp`; the `checked_dimension(..., 64, ...)` cap on the
response route; the blocked mixed-iPEPS-overlap + FHS-plaquette task
(no longer needed for `Δ = 0`).

**Do not rerun**: the cluster jobs that produced `berry_square_L{2,3,4}.csv` —
`L = 2, 3` remain valid, and `L = 4` is cheaper to recompute exactly than to
re-measure.

---

## 8. Reproduction of §1.3

```python
import numpy as np, scipy.sparse as sp, scipy.sparse.linalg as spla

def build(L, Om, J=1.0):                       # 2D square TFIM, PBC
    N, dim = L*L, 1 << (L*L)
    sid = lambda x, y: (x % L) + (y % L) * L
    bonds = [(sid(x,y), sid(x+1,y)) for y in range(L) for x in range(L)] + \
            [(sid(x,y), sid(x,y+1)) for y in range(L) for x in range(L)]
    diag = np.zeros(dim)
    for st in range(dim):
        diag[st] = sum(-J*(2*((st>>a)&1)-1)*(2*((st>>b)&1)-1) for a, b in bonds)
    H, idx = sp.diags(diag).tocsr(), np.arange(dim)
    for i in range(N):
        H = H + sp.csr_matrix((np.full(dim,-Om), (idx, idx ^ (1<<i))), shape=(dim,dim))
    return H

def E0(L, Om):
    H = build(L, Om)
    return (np.linalg.eigvalsh(H.toarray())[0] if H.shape[0] <= 1024
            else spla.eigsh(H, k=1, which="SA", tol=0, maxiter=5000)[0][0])

def Fbar(L, Om, h=2e-3):                       # F_θΩ / N = (1/2N) d²E₀/dΩ²
    d2 = (-E0(L,Om+2*h) + 16*E0(L,Om+h) - 30*E0(L,Om)
          + 16*E0(L,Om-h) - E0(L,Om-2*h)) / (12*h*h)
    return d2 / (2*L*L)

for L, Om in [(3,1.0), (4,1.0), (4,3.044), (4,5.0)]:
    print(L, Om, Fbar(L, Om))
```

Replace `build` with the 1D chain (`bonds = [(i,(i+1)%N)]`) to reproduce the
Jordan–Wigner rows. Runtime: seconds for `L ≤ 3`, ~1 min for `L = 4`,
single-threaded. This script is the P0 acceptance test in Python form; the
C++ `test_identity.cpp` must reproduce it.
