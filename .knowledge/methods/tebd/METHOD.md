<!-- Method-card template. Axis definitions: ../method-property-checklist.md (M1–M14).
     Inverse model→method map: ../method-property-map.md. Cost derivations & citations:
     ../method-survey.md. Cite keys resolve in ../ref.bib. -->

# Time-Evolving Block Decimation (TEBD)

Trotter-decomposed MPS time evolution: applies nearest-neighbor two-site gates in alternating sweeps to evolve an MPS in real or imaginary time.

## Method card

### What it is

TEBD represents the quantum state as a matrix product state (MPS) and evolves it via a Suzuki–Trotter decomposition of the time-evolution operator `e^{-iHt}` (real time) or `e^{-Hτ}` (imaginary time) into a sequence of nearest-neighbor two-site gates. Each gate is applied to adjacent sites, the bond is contracted and then SVD-truncated to retain only `χ` singular values, keeping the MPS representation compact. The method is exact in the limit `χ→∞` and `Δt→0`; in practice it is controlled by the bond dimension and the Trotter step. The entanglement barrier — linear growth `S(t)∝t` for thermalizing systems — limits reachable real times to `t*~log(χ_max)/rate`, while imaginary-time TEBD converges to the ground state or the finite-T purification.

### Properties (M1–M14)

| Axis | Value | Note |
|---|---|---|
| M1 tasks / outputs | Quench dynamics · real-time correlations · spectral functions `S(q,ω)` (time-evolve + Fourier) · transport coefficients · ground-state energy & wavefunction (imaginary-time) · finite-T thermodynamics (purification) | Spectral functions require Fourier transform of the time-domain correlator; max frequency resolution set by reachable `t*`. |
| M2 regime | Real-time dynamics + imaginary-time (ground state & finite-T) | Both regimes use the same SVD-truncation engine; imaginary-time entanglement saturates (GS) or grows slowly (thermal). |
| M3 accuracy class | Controlled, deterministic | Two controllable knobs: bond dim `χ` (truncation error) and Trotter step `Δτ` (Trotter error `O(Δτ^p)`); both can be converged independently. |
| M4 dimension fit (A1) | 1D native; quasi-1D (ladders) with swap gates; **walls in 2D** | Nearest-neighbor (A4 = short-range interaction range) gates only — long-range interactions require swap-gate sequences (expensive); 2D walls due to `χ~e^{cW}` cylinder area law. |
| M5 statistics & local dim (A3) | Spin / hard-core boson / soft-core boson / fermion (Jordan–Wigner) / any | Per-site cost `∝d·χ³`; large `d` (Hubbard `d=4`, soft-core bosons) raises cost; fermions need parity tensors or JW strings. |
| M6 entanglement regime (B5) | Area-law + area+log tolerated; volume-law blocks real-time | Real-time entanglement grows linearly `S(t)∝t` for thermalizing systems → **`χ(t)~e^{S(t)}`** caps reachable time `t*~log(χ_max)/rate`; MBL (D15) and integrable (C11) systems grow more slowly. |
| M7 sign-problem dependence (C12) | Sign-immune | Tensor-network method; no Monte Carlo sampling; no sign problem. |
| M8 symmetry exploitation (C9/C10) | U(1)/SU(2)/Z₂ quantum-number-conserving tensors; translation symmetry for iMPS (infinite systems) | Symmetry reduces effective `χ` by ~10× at fixed accuracy; iMPS with translation gives direct thermodynamic-limit access. |
| M9 time complexity | `O(N·d·χ(t)³)` per Trotter step; Trotter error `O(Δτ^p)` | `p=2` standard; `p=4` higher-order Suzuki–Trotter. Total cost scales with number of steps and growth of `χ(t)`. No MPO `w` factor because TEBD applies nearest-neighbor gates directly (contrast TDVP's `O(N·w·d·χ³)`). |
| M10 memory | `O(N·d·χ²)` for the MPS; environment/orthogonality center storage `O(d·χ²)` per bond | Manageable for `χ~1000`; the dominant memory is the MPS itself. |
| M11 control knob | Bond dim `χ` (SVD truncation error) + Trotter step `Δτ` (Trotter error `O(Δτ^p)`) | Both must be converged; truncation error accumulates over time steps. |
| M12 scale frontier | 1D chains `N~1000` sites routine (fixed `χ`); reachable time `t*~log(χ_max)/rate` | At `χ=512` and rate~1 (Heisenberg chain), `t*J~6`; longer for MBL/integrable (D15/C11). |
| M13 primary approximation / bias | Finite-`χ` SVD truncation (controlled) + Trotter discretization `O(Δτ^p)` (controlled) | Both biases are systematically improvable; truncation accumulates in time. |
| M14 hard blocker / failure mode | Entanglement barrier: **`χ(t)~e^{S(t)}`** — for thermalizing (B6 gapless, B8 frustrated) systems `S(t)∝t` caps reachable `t*`; long-range interactions (A4) require expensive swap-gate sequences; 2D walls (`χ~e^{cW}`) | Rate set by C11 integrability / D15 MBL / B6 gap; thermal systems hit the barrier fastest. |

### Cost & scaling

- Time: `O(N·d·χ(t)³)` per Trotter step; total cost grows with reachable time as `χ(t)` increases; no MPO `w` factor because TEBD applies nearest-neighbor gates directly (contrast TDVP's `O(N·w·d·χ³)`)
- Memory: `O(N·d·χ²)` for the MPS
- Control knob: `χ` (truncation) + `Δτ` (Trotter error `O(Δτ^p)`)
- Scale frontier: `N~1000` sites in 1D; reachable real time `t*~log(χ_max)/rate`

### Accuracy & guarantees

- Class: controlled, deterministic
- Primary approximation & its control: SVD truncation at bond `χ` (truncation error measurable from discarded weight) + Trotter decomposition error `O(Δτ^p)` (`p=2` standard, `p=4` higher-order)
- Error scaling: truncation error ~ discarded singular value weight per step, accumulated over `N_steps`; Trotter error `O(Δτ^p · t)` total; converge both independently

### Tasks it computes

- Quench dynamics: evolve `|ψ₀⟩` under `H` and measure observables `⟨O(t)⟩`
- Real-time correlations and spectral functions `S(q,ω)` via time-evolve + Fourier transform
- Transport coefficients (linear-response Green–Kubo integrals)
- Ground-state energy & wavefunction via imaginary-time evolution `τ→∞`
- Finite-T thermodynamics via imaginary-time purification (ancilla TEBD)

### Recommended for (models / regimes)

- **Primary real-time dynamics solver for 1D:** Heisenberg chains, Hubbard chains, XXZ chains, Bose–Hubbard chains (A1 = 1D, A4 short-range)
- **Imaginary-time GS for short-range 1D models** when DMRG is unavailable
- **MBL systems (D15):** slow entanglement growth extends reachable `t*`; TEBD is the standard tool for probing l-bit dynamics
- **Integrable systems (C11):** slower-than-linear `S(t)` growth (logarithmic for MBL, subdiffusive for integrable) allows long-time evolution
- Per `method-property-map.md` (TEBD profile): preferred over TDVP when `H` is strictly nearest-neighbor (A4 = short-range) and swap-gate sequences are not needed

### Key reference

[@vidal_2003_efficient] — original TEBD paper introducing the SVD-based Trotter time evolution for MPS; defines the algorithm and complexity.
Rendered: `../../literature/mps-based-algorithm/10-1103-physrevlett-93-040502.md` _(reused: `../../literature/mps-based-algorithm/10-1103-physrevlett-93-040502.md`)_.

### Benchmarks

- Entanglement growth after a global quench in the XX chain: entanglement grows **linearly**, `S(t) ≃ (π c /3) v_F t` (c=1 for the XX chain), until finite-χ truncation caps it — this linear growth is the entanglement barrier [@vidal_2003_efficient; @calabrese_2005_evolution]. Saturation at `S~log(χ)` sets the reachable time `t*∝log(χ)/rate`.
- Heisenberg chain quench at `χ=512`: reachable `tJ≈6` before truncation error exceeds `10⁻³` (method-survey.md §5.1).
- MBL phase (D15, W/J=5): `S(t)~log(t)`, `χ` grows logarithmically → reachable `tJ~100` at `χ=512` (method-survey.md §5.1).

## How it is used / Operational

**Owning skill:** `/method-mps` (primary); tool skills `/using-tenpy`, `/using-itensors`, `/using-mpskit`.

**Default workflow:**
1. Prepare initial MPS `|ψ₀⟩` (product state or GS from DMRG).
2. Build Trotter gates from nearest-neighbor `H` terms; choose order `p=2` or `p=4` and step `Δτ`.
3. Apply sweeping gate sequence (TEBD sweep), SVD-truncate each bond to `χ`.
4. Monitor truncation error (discarded weight per step) and energy (imaginary-time) or norm (real-time).
5. Converge in `χ` and `Δτ`; compute observables at each time step.
6. For `S(q,ω)`: Fourier transform `⟨O(t)⟩`; resolve peaks at frequencies up to `π/Δτ`.

**Verification pointers:**
- Real-time: norm `⟨ψ(t)|ψ(t)⟩=1` and energy `⟨H⟩=const` (up to truncation).
- Imaginary-time: energy must decrease monotonically; overlap with GS increases.
- Compare `S(t)` entanglement growth to CFT predictions for integrable systems.

**Cross-links:**
- Survey: `method-survey.md` §5.1 (TEBD — Trotter MPS time evolution)
- Model↔method gate: `method-property-map.md` (TEBD profile)
- Complementary methods: TDVP (long-range `H`, energy-conserving), mps-finite-t (finite-T purification), DMRG-X (excited eigenstates in MBL)
