---
name: method-ltrg
description: Use when a finite-temperature Linearized Tensor Renormalization Group (LTRG) reproduction needs method-level route and tool selection — Trotterized classical tensor network from a quantum lattice model, layer-by-layer boundary contraction with SVD truncation, thermodynamic observables (free energy, internal energy, specific heat, susceptibility).
---

# Method LTRG

LTRG is the finite-temperature tensor-network method class: map a `d`-dimensional quantum lattice model to a `(d+1)`-dimensional classical tensor network by Trotter-Suzuki decomposition, then contract layer by layer while truncating the growing boundary with SVD to bond dimension `Dc`. This card owns method selection (step 1), software routing (step 2), and method-level setup (step 3, method side). Method internals — including the algorithm — are in `## Details`; software parameter *values* and the ITensors primitives live in `/using-itensors`; paper- and model-specific facts live in `/reproduce-paper` and `.knowledge/models/`.

## Sources

- Tool skill: `/using-itensors`
- Primary literature: Li, Ran, Gong, Zhao, Xi, Ye, Su, *Linearized tensor renormalization group algorithm…* PRL (2011) `.knowledge/literature/ltrg/1011.0155_linearized-tensor-renormalization-group-algorithm-for-the-ca.md`.

## Select method — step 1

### Suited for

- Finite-temperature thermodynamics of low-dimensional quantum lattice models — 1D / quasi-1D chains and 2D lattices (e.g. honeycomb). Observables: free energy per site, internal energy, specific heat, susceptibility.
- Maps `d`-dim quantum → `(d+1)`-dim classical tensor network via Trotter-Suzuki, then decimates iTEBD-style; **sign-problem-free even in 2D**, a promising alternative to QMC for frustrated/fermionic 2D thermodynamics.
- Sizes reached: XY chain to length 2¹⁰⁰ (thermodynamic limit); temperature down to T/J ≈ 0.008 (β = 120); retained dimension Dc ≤ 150; 2D honeycomb Heisenberg benchmarked against QMC.

### Route elsewhere when

- The target is a **ground-state** property → `/method-mps` (DMRG) or `/method-peps`; LTRG is a finite-temperature method.
- An exact/analytic solution exists — use it only as a benchmark *after* the LTRG calculation, never as a substitute.

### Options & trade-offs

| Method | Good at | Weak at | Typical reach |
|---|---|---|---|
| LTRG (this card) | finite-T low-D, 2D sign-free, scalable transfer-network contraction | low-T needs large Dc; Trotter + truncation error to control | T/J ~ 0.008, Dc ≤ 150 |
| TMRG (transfer-matrix DMRG) | finite-T 1D, accurate | scales worse to 2D | 1D |
| coarse-graining TRG | 2D classical networks | discards O(Dcⁿ)/step → costlier | 2D |
| purification / METTS | finite-T via MPS, good low-T in 1D | 2D entanglement cost | 1D / quasi-1D |
| QMC (`/method-qmc`) | finite-T, large sizes | sign problem (frustrated/fermionic) | sign-free only |
| XTRG (later Wei Li work) | reaches lower T (logarithmic-in-β cooling) | more involved bookkeeping | very low T |

## Select software — step 2

### Open-source tools

- No official LTRG package ships with the paper — it is an algorithm-only PRL.
- The harness route is **ITensors.jl** (Julia): typed indices, SVD with truncation to `Dc`, and gate/transfer-tensor contraction, so the algorithm is expressed directly. The same algorithm is expressible in TeNPy or quimb.
- No reusable LTRG library function exists in-repo; the algorithm is in `## Details` below, and `/using-itensors` carries the ITensors **primitives** (typed indices, `svd` to `Dc`, gate exponentiation, incremental writes) to express it.

### Features to confirm

- Typed indices with explicit tags, `svd` with `maxdim`/`cutoff`, gate exponentiation `exp(-τ·h)`, incremental writes of convergence data — owned by `/using-itensors`.

### Options & trade-offs

| Tool | Ecosystem / examples | Efficiency | When |
|---|---|---|---|
| ITensors.jl (this route) | Julia; ITensors primitives in `/using-itensors`, algorithm in `## Details` | native SVD/contraction; core op is the O(D⁶·Dc³) SVD step | default |
| TeNPy / quimb | Python TN ecosystems | comparable; needs a hand-built LTRG loop | if Python-bound |

### Handoff

Invoke **`/using-itensors`** once the LTRG route is fixed — it owns ITensors.jl setup, index mechanics, SVD/truncation keywords, the ITensors primitives that express the algorithm, and runtime troubleshooting. This card owns the Trotter split, contraction order, normalization bookkeeping, and the convergence plan; the model/paper skills own the Hamiltonian and figure facts.

## Method setup — step 3 (method side)

Conceptual knobs and the tricks behind them — for each, the **intuition for choosing it** and how it moves the result; the trick is the guidance where there is no fixed default. Concrete ITensors values/code live in `/using-itensors`.

| Knob | Controls | Trick / how it affects results |
|---|---|---|
| `τ` | Trotter step | decomposition error ∝ τ² (symmetric split); paper uses 0.1/0.05/0.02/0.01; smaller τ → more layers |
| `K` | number of imaginary-time steps | fixes `β = Kτ`; more steps reach lower T but accumulate more truncations |
| `Dc` | retained SVD dimension | dominant accuracy/cost lever (like `M` in TMRG); paper uses 50/100/150 |
| `D` (q) | local Hilbert dimension | sets transfer-tensor size; do not confuse with `Dc` |
| contraction direction / gate order | layer-absorption scheme | two equivalent schemes (Trotter-first or spatial-first); alternate the two projections per full Trotter step |
| normalization convention | scale bookkeeping | divide each step by the largest singular value (and each trace matrix by its largest element); collect the log factors to rebuild Z and the free energy |

**Cost**: the local evolution (contract + SVD of the transfer tensor) scales as **O(D⁶·Dc³)** per step — the dominant cost; the spatial trace contracts `2^p` matrices in `p` pairwise steps (logarithmic in chain length); memory is dominated by the `Dc`-bond boundary tensors plus the transient enlarged tensor. Estimate from intended `τ`, target `β`, `q`, geometry, and the `Dc` sweep before a full run.

## Details

LTRG maps a `d`-dimensional quantum lattice model at finite temperature into a `(d+1)`-dimensional classical tensor network by Trotter-Suzuki decomposition, then contracts it layer by layer while truncating the growing boundary with SVD.

This card is generic methodology. Paper-specific Hamiltonian choices, figure protocols, and target claims belong in `/reproduce-paper`; model facts belong in `.knowledge/models/`.

### Notation

- `d` spatial dimension; `β` inverse temperature; `τ` Trotter step; `K` steps with `β = Kτ`.
- `Dc` retained SVD dimension; `q` (a.k.a. `D`) local Hilbert dimension.
- Boundary tensor network: the partially contracted region.
- Log scale factors: accumulated normalizations needed to recover `Z` and the free energy.

### Algorithm

1. Split the local quantum Hamiltonian into Trotter-Suzuki pieces; approximate `Z = Tr e^{−βH}` as a product of imaginary-time gates with `β = Kτ`.
2. Insert complete local bases between layers and read the result as a `(d+1)`-dim classical tensor network.
3. Build local transfer tensors from the gate matrix elements; SVD-factor them if the geometry requires.
4. Initialize the boundary tensor network; absorb one uncontracted layer.
5. Reshape and SVD; keep the largest `Dc` singular values; update the boundary.
6. Normalize, store the log scale factor; repeat layer absorption until the full imaginary-time extent is contracted.
7. Contract the remaining boundary; combine with the log factors to obtain `Z`, the free energy, and derived thermodynamics.

## Verification — implementation stage

### Intermediate (mid-run)

- Per-step normalization factors (largest singular value) stay finite and vary smoothly on a log scale — a divergence means a missing normalization.
- Discarded singular weight per SVD stays small and saturates as `Dc` grows.

### Final verification + expert criticism

- `τ → 0` extrapolation to remove Trotter error (dominant at high T).
- `Dc` convergence: the observable stops moving as `Dc` grows (e.g. Dc = 100 and 150 curves coincide); truncation error dominates at low T.
- Analytic/exact limits: benchmark vs the exact XY-chain solution (δf ≈ 7×10⁻⁶ at β = 120, Dc = 150); high- and low-T limits when the caller supplies them; β → large → ground-state energy e₀.
- Cross-check non-integrable models vs TMRG / QMC where available.
- Confirm every log scale factor is counted exactly once in the final quantity.
- **Criticize:** a single-(τ, Dc) number with no τ→0 and no Dc-convergence study; trusting low-T data at small Dc; no benchmark against an exact / QMC reference; and ignoring that high-T error is Trotter while low-T error is truncation.

## Citations

- `.knowledge/literature/ltrg/1011.0155_linearized-tensor-renormalization-group-algorithm-for-the-ca.md` — Li et al. (2011), original LTRG paper.
- ITensors.jl setup, API primitives, and runtime live in `/using-itensors`.
