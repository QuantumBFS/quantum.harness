<!-- Method-card template. Axis definitions: ../method-property-checklist.md (M1–M14).
     Inverse model→method map: ../method-property-map.md. Cost derivations & citations:
     ../method-survey.md. Cite keys resolve in ./ref.bib. -->

# Time-Dependent Variational Principle (TDVP)

Geometric time evolution of an MPS by projecting the Schrödinger equation onto the MPS tangent space, using the W^I/W^II MPO integrators; handles long-range Hamiltonians and conserves energy exactly.

## Method card

### What it is

TDVP evolves an MPS by projecting `−iH|ψ⟩` onto the tangent space of the MPS manifold at each step, yielding a sequence of local differential equations solved by Krylov exponentiation. The Hamiltonian enters as an MPO (matrix product operator), so long-range and quasi-1D interactions are handled naturally without swap gates. Two variants exist: **1-site TDVP** fixes the bond dimension `χ` (the MPS manifold does not grow; error is the projection onto the tangent space) and **2-site TDVP** expands `χ` via a global subspace expansion, mirroring DMRG's 2-site sweep. The method is energy-conserving and symplectic to machine precision for 1-site TDVP.

### Properties (M1–M14)

| Axis | Value | Note |
|---|---|---|
| M1 tasks / outputs | Real-time dynamics · spectral functions `S(q,ω)` (time-evolve + Fourier) · long-time dynamics within fixed-`χ` manifold (1-site) · transport · finite-T (TDVP + purification) | 1-site TDVP ideal for long-time within manifold; 2-site for growing `χ` during quench. |
| M2 regime | Real-time dynamics + imaginary-time (ground state) (D13) | Primarily a dynamics method; imaginary-time TDVP is algebraically equivalent to a DMRG sweep. |
| M3 accuracy class | Controlled, deterministic | Two knobs: `χ` (truncation / projection error) and time step `Δt` (Krylov error, which is very small for the local integrator); 1-site has a projection error absent in 2-site. |
| M4 dimension fit (A1) | 1D + quasi-1D (ladders/cylinders); **handles long-range Hamiltonians via MPO** | Key advantage over TEBD: MPO representation supports long-range (A4) interactions natively; no swap-gate overhead; 2D walls same as TEBD (`χ~e^{cW}`). |
| M5 statistics & local dim (A3) | Spin / hard-core boson / soft-core boson / fermion (parity tensors) / any | Per-site cost `∝w·d·χ³` where `w` is the MPO bond; large `d` or wide-range MPO (large `w`) raises cost. |
| M6 entanglement regime (B5) | Area-law + area+log (1-site within fixed `χ`); volume-law blocks | Same entanglement barrier `χ(t)~e^{S(t)}` as TEBD in 2-site mode; 1-site TDVP fixes `χ` (stays in manifold, no growth) but introduces projection error. |
| M7 sign-problem dependence (C12) | Sign-immune | Tensor-network method; no Monte Carlo. |
| M8 symmetry exploitation (C9/C10) | U(1)/SU(2)/Z₂ quantum-number-conserving tensors; translation symmetry for uniform MPS (TDVP on the infinite MPS) | Symmetry-adapted MPO tensors reduce `w` and effective `χ`; ~10× speedup at fixed accuracy. |
| M9 time complexity | `O(N·w·d·χ³)` per time step (`w` = MPO bond dimension, set by A4 interaction range) | `w` grows with interaction range: nearest-neighbor `w=3`–`5`; power-law decaying `w~15`–`50`; arbitrary long-range `w` can be large. Same `χ(t)` entanglement barrier as TEBD. |
| M10 memory | `O(N·w·d·χ²)` for MPS + MPO environments | MPO environments `O(w·χ²)` per bond; dominant at large `w`. |
| M11 control knob | Bond dim `χ` (projection / truncation error) + time step `Δt` (Krylov integrator error, exponentially small) | 1-site: `χ` fixed → monitor projection error; 2-site: `χ` grows until truncation error converges. |
| M12 scale frontier | 1D `N~500–2000` sites routine at fixed `χ`; reachable time `t*~log(χ_max)/rate` (same barrier as TEBD) | 1-site can reach longer real times at fixed `χ` than TEBD by staying in the manifold; barrier still applies at large `t`. |
| M13 primary approximation / bias | Finite-`χ` MPS manifold projection (controlled) | 1-site: projection onto current MPS tangent space (no `χ` growth — misses orthogonal dynamics); 2-site: SVD truncation. Energy is conserved (1-site) even as `χ` is fixed. |
| M14 hard blocker / failure mode | Entanglement barrier `χ(t)~e^{S(t)}` (same as TEBD for 2-site); 1-site projection error misses dynamics outside current manifold; 2D cylinder wall (`χ~e^{cW}`) | For thermalizing systems at long times, both 1-site and 2-site TDVP eventually fail. |

### Cost & scaling

- Time: `O(N·w·d·χ³)` per time step; `w` = MPO bond dim (set by interaction range A4)
- Memory: `O(N·w·d·χ²)` for MPS + MPO environments
- Control knob: `χ` (projection/truncation error) + `Δt` (Krylov error, negligible)
- Scale frontier: `N~500–2000` sites in 1D; reachable time `t*~log(χ_max)/rate`

### Accuracy & guarantees

- Class: controlled, deterministic
- Primary approximation & its control: MPS manifold projection at bond `χ`; 1-site has projection error (no `χ` growth); 2-site has SVD truncation error
- Error scaling: 1-site projection error `~O((1−P_χ)H|ψ⟩)` (measurable from local Krylov residual); 2-site truncation error from discarded singular values; both converge as `χ→∞`

### Tasks it computes

- Real-time quench dynamics under long-range or quasi-1D Hamiltonians
- Spectral functions `S(q,ω)` via time-evolve + Fourier (longer reach than TEBD for same `χ` in 1-site mode)
- Transport (energy, spin, charge) in systems with structured long-range couplings
- Variational imaginary-time (TDVP = DMRG-like) for ground-state optimization

### Recommended for (models / regimes)

- **Long-range interacting 1D models (A4 long-range):** power-law spin chains, trapped-ion chains, Rydberg arrays — TEBD is infeasible here; TDVP handles via MPO natively
- **Energy-conserving dynamics:** microcanonical quenches, ETH studies where energy conservation matters
- **1-site long-time dynamics at fixed `χ`:** when you want the best approximation within a fixed MPS space (e.g., non-integrable systems at moderate `t`)
- **Ladder / cylinder geometries (quasi-1D):** same advantage over TEBD in handling the MPO for rung interactions
- Per `method-property-map.md` (TDVP profile): preferred over TEBD when `H` has long-range or multi-site terms (A4 non-nearest-neighbor)

### Key reference

[@haegeman_2016_unifying] — defines the 1-site and 2-site TDVP integrators for MPS, proves energy conservation, and provides the W^I/W^II MPO time evolution; the standard algorithmic reference.
Rendered: `../../literature/mps-based-algorithm/1408.5056_unifying-time-evolution-and-optimization-with-matrix-product.md` _(reused: `../../literature/mps-based-algorithm/1408.5056_unifying-time-evolution-and-optimization-with-matrix-product.md`)_.

### Benchmarks

- 1-site TDVP energy conservation: `|ΔE/E| < 10⁻¹²` per step for Heisenberg chain `N=100`, `χ=64` [@haegeman_2016_unifying].
- Spectral function convergence: comparable accuracy to TEBD but reachable `t*` longer at fixed `χ` (1-site, non-thermalizing) — method-survey.md §5.2.
- MPO bond dimension for Coulomb-like `1/r` interaction: `w~20–30` giving cost `O(N·30·d·χ³)` vs TEBD swap-gate `O(N²)` per step — method-survey.md §5.2.

## How it is used / Operational

**Owning skill:** `/method-mps` (primary); tool skills `/using-tenpy`, `/using-itensors`, `/using-mpskit`.

**Default workflow:**
1. Construct the Hamiltonian MPO (use tenpy's `NearestNeighborModel` for short-range or `CouplingModel` for long-range).
2. Prepare initial MPS `|ψ₀⟩` (product state or DMRG ground state).
3. Choose 1-site TDVP (fixed `χ`) or 2-site TDVP (growing `χ`): use 2-site for quench onset, switch to 1-site for long-time.
4. Set time step `Δt` (typically `Δt J ~ 0.01–0.05`); run Krylov exponentiation at each site.
5. Monitor energy conservation (1-site: should be machine-precision), truncation error (2-site), and entanglement growth.
6. Converge in `χ` by running at multiple bond dimensions; compare observables.

**Verification pointers:**
- 1-site: energy `⟨H⟩(t)=const` to machine precision; compare against exact (ED) for small systems.
- 2-site: truncation error per step < `10⁻⁷`; discarded weight summed over run < `10⁻⁴`.
- Cross-check short-time dynamics against TEBD (where applicable) for consistency.

**Cross-links:**
- Survey: `method-survey.md` §5.2 (TDVP & W^I/W^II MPO evolution)
- Model↔method gate: `method-property-map.md` (TDVP profile)
- Complementary methods: TEBD (nearest-neighbor only, no MPO overhead), mps-finite-t (finite-T), DMRG (imaginary-time limit of TDVP)
