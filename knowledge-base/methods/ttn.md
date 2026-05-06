# TTN (Tree Tensor Network)

Variational tensor network with a binary-tree (loopless) structure. Used here for ground-state search and as the wavefunction backbone for Pauli-string sampling, where the tree structure gives `O(χ⁴ log N)` per-update cost on Pauli flips — the key efficiency feature for many-body magic estimators (`knowledge-base/methods/pauli-markov.md`).

One algorithm class per the method-card-per-algorithm rule. `methods/dmrg.md` (MPS) and this card are the two tensor-network ground-state cards.

## Setup

```
make install julia
make install itensors
```

The harness's installed Julia stack (ITensors.jl, ITensorMPS.jl, KrylovKit.jl, MPSKit.jl) provides the tensor primitives. TTN-specific helpers may need an additional package (e.g., `ITensorNetworks.jl`); the skill driving the calculation declares the dependency before the calculation runs.

## Notation

- Layer index `l` (0 at the root) and intra-layer index `n`. Tensor at the binary tree is `[l, n]`.
- Bond dimension `χ`: link size on virtual edges. For 1D periodic ring or 2D periodic torus, the same parameter controls accuracy on both geometries.
- Link operators `O[l,n]`: coarse-grained operators that live on virtual links during the Pauli-flip update.
- Sweeping algorithm: variational ground-state search by local tensor optimization across the tree.

## Code shape (Julia / ITensorNetworks-style)

```julia
using ITensors, ITensorNetworks, ITensorMPS

# 1. Build site indices for the target Hilbert space (qubit / qudit / spin-1)
sites = siteinds("S=1/2", N; conserve_qns=true)   # or "Qudit", dim=d for d-state

# 2. Construct the binary-tree TTN with bond dimension chi
psi = random_ttn(sites; link_space=chi)           # placeholder API

# 3. Build the Hamiltonian as an MPO/TTN-MPO via OpSum (same as DMRG)
ampo = OpSum()
for term in hamiltonian_terms(...)
    ampo += term
end
H = TTN(ampo, sites)                              # placeholder API

# 4. Sweep schedule
nsweeps = 20
maxdim = [10, 20, 50, 100, 200, 200]
cutoff = [1e-10]

# 5. Variational sweep
energy, psi = dmrg_ttn(H, psi; nsweeps, maxdim, cutoff, outputlevel=1)

# 6. Bring TTN into central canonical form for Pauli-flip sampling
psi_canon = canonicalize_root!(psi)
```

API names are stack-dependent; the calling skill verifies the package and adjusts call signatures. For 2D `L×L` torus geometry the binary tree is built so each leaf maps to a site of the dual lattice; the periodic wrap is supported natively by the tree.

## Knobs

| Knob | Effect | Starting point |
|---|---|---|
| `χ` (bond dimension) | Drives accuracy and cost. `O(χ⁴)` per local update. | Grow gently from `~10`; targets `30–60` for entry-level magic-density work; raise as the result drifts. |
| `cutoff` | SVD truncation on virtual links. | `1e-10` default; tighten near criticality. |
| `nsweeps` | Variational sweeps. | 10–30; stop when energy stops moving within accuracy goal. |
| Tree geometry | Binary tree topology — 1D ring, 2D torus, or custom. | Match the lattice's natural locality so coarse-graining preserves correlations. |
| Sampling proposal class | Single-site or two-site Pauli flip. | Two-site whenever symmetry constraints require (see `methods/pauli-markov.md`). |

## Stages (multi-stage orchestration)

### Stage 0 — TTN ground-state search

| Input | Output |
|---|---|
| Hamiltonian, sites, target sector, sweep schedule | TTN file (`results/<run>/ttn.h5`), energy, energy-variance log, bond-dim trajectory. |

### Stage 1 — central-canonical preparation

| Input | Output |
|---|---|
| Stage-0 TTN | TTN with the root tensor as orthogonality center; coarse-grained link operators initialized for the starting Pauli string. |

### Stage 2 — Pauli-flip sampling support

| Input | Output |
|---|---|
| Canonical TTN, current Pauli string `P`, proposed `P'` | Updated link operators on the path from the modified site(s) to the root, and `⟨ψ|P'|ψ⟩`. |

This stage is consumed by `methods/pauli-markov.md` Stage 1; the cost per call is `O(χ⁴ log N)` because only the `O(log N)` links on the path from the modified site to the root need re-coarse-graining.

## Pitfalls

- **Stuck in local minimum** — TTN sweeping has the same metastability as DMRG; restart with different seed or with a structured initial state.
- **Periodic geometry trade-off** — TTN supports PBC at the same cost as OBC, *but* the achievable `χ` for a given physical-correlation-length target is larger than MPS-OBC. Document both.
- **Tree mismatch** — choosing a tree that crosses physical correlations badly (e.g., bisecting an entangled cluster) inflates `χ` requirements. Match topology to lattice connectivity.
- **2D geometry** — the binary tree on `L×L` torus is one of several valid choices; document the chosen tree and verify the Pauli-flip update path-length is `~ log(L²)`.
- **Symmetry quantum numbers** — when conserving Z_n symmetries (e.g., Z_2 in TFIM, Z_3 in Potts/Clock, U(1) in spin-1 XXZ), the tree must respect the conservation; check by computing total `S^z` (or analogue) on the optimized state.

## TTN vs MPS (when to choose)

| Situation | Choose | Why |
|---|---|---|
| 1D chain, OBC, ground-state energy + standard observables | MPS / DMRG (`methods/dmrg.md`) | Simpler, faster, sufficient. |
| 1D ring (PBC) with same observables | MPS-PBC or TTN | TTN avoids the `~2× χ` PBC overhead of MPS; choose if `χ` budget matters. |
| Pauli-string sampling at large `N` | TTN | Pauli-flip cost `O(χ⁴ log N)` vs `O(N χ³)` per MPS perfect-sampling step. Crossover when `N/log N ≳ χ`. |
| 2D torus or `L×L` cluster, modest sizes | TTN | Native PBC; avoids long-range MPS bonds. |
| 2D wide cylinder, ground-state energy | DMRG cylinder | DMRG-cylinder lore is mature; TTN is competitive but less standardized. |
| Bell magic / stabilizer nullity (Pauli-basis MPS) | MPS deterministic Pauli-basis lift (`methods/pauli-markov.md` variant) | The Pauli-basis lift is MPS-native. |

### Numerical break-even for Pauli-string sampling

For Pauli-string Markov-chain sampling, the per-update cost is the dominant cost factor (the chain takes `N_S ~ 10⁵–10⁷` updates per estimate). The three relevant cost formulas:

| Algorithm | Per-update cost | Scaling driver |
|---|---|---|
| TTN Pauli-flip | `O(χ⁴ log N)` | Re-coarse-grain the `O(log N)` links from the modified site to the root. |
| MPS DMRG sweep (ground-state) | `O(N χ³)` | Standard left-right sweep cost; one full sweep per energy update. |
| MPS perfect-sampling (Pauli-MPS) | `O(N χ⁶)` | Bond dimension squared per site (Pauli index) times the standard `O(N χ³)` MPS contraction; limited to `χ ≲ 12` in practice. |

**TTN-vs-MPS-perfect-sampling crossover** for Pauli-string Markov chains: TTN beats MPS perfect sampling when `χ⁴ log N ≲ N χ⁶`, i.e., when `N / log N ≳ χ⁻²`. Since `χ⁻² ≪ 1` for any practical bond dim, the crossover for sampling cost is essentially `N / log N ≳ 1` (TTN always cheaper at the per-update level). The *binding* constraint is that MPS perfect sampling at `χ ≳ 12` becomes prohibitive on its own (the `χ⁶` scaling), so TTN is the standard route at any `(N, χ)` where `χ ≳ 12` is required.

**TTN-vs-MPS DMRG crossover** for the *ground-state stage* (independent of sampling): TTN wins when `χ log N ≲ N`, i.e., when `N / log N ≳ χ`. Worked points:

| `N` | `log₂ N` | `N / log₂ N` | TTN wins for `χ ≲` |
|---|---|---|---|
| 16 | 4 | 4 | 4 (rarely useful) |
| 32 | 5 | 6.4 | 6 |
| 64 | 6 | 10.7 | 10 |
| 128 | 7 | 18.3 | 18 |
| 256 | 8 | 32 | 32 |

**Practical guidance**: for `N ≳ 32` and `χ ≳ 30`, TTN is preferred for any Pauli-string-sampling workload (the sampling cost dominates and the TTN per-update advantage is decisive). For ground-state energy alone at `χ ≲ 30`, MPS-DMRG remains competitive; the TTN advantage is in the *sampling* phase that follows. The break-even is not a knife edge — both methods work in a wide overlapping band — but the asymptotic scaling makes TTN the clear default for entry-level magic-density work at the bond-dim range cited in `magic-benchmarks.md` (`χ ∈ {30, 36, 60}`).

## Verification (per-method, complements skill-level verification)

- **Energy convergence as `χ` grows** — `E(χ)` monotonically decreasing and asymptoting; report the curve.
- **Energy variance** `⟨H²⟩ − ⟨H⟩²` — small at convergence; same role as in DMRG.
- **Symmetry checks** — verify the imposed Z_n / U(1) sector on the optimized state.
- **Cross-check at small `N`** — TTN energy must agree with ED on small clusters within the truncation budget; agreement gates downstream Pauli-flip sampling.
- **Pauli-flip update path-length scan** — verify the implementation actually scales as `log N` per update (not as `N`); otherwise the efficiency advantage is lost.

## Citations

- See `knowledge-base/literature/magic/INDEX.md` for the TTN-coupled Pauli-Markov-sampling methodology reference (the source of the `O(χ⁴ log N)` per-update construction and the binary-tree coarse-graining recipe used in 2D Z_2 gauge / 2D Ising via Wegner duality).
