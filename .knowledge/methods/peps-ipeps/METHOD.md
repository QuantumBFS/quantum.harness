<!-- Method-card template. Axis definitions: ../method-property-checklist.md (M1–M14).
     Inverse model→method map: ../method-property-map.md. Cost derivations & citations:
     ../method-survey.md. Cite keys resolve in ../ref.bib. -->

# Projected Entangled Pair States (PEPS / iPEPS)

2D tensor-network variational ansatz that encodes the 2D area law at fixed virtual bond D; the natural extension of MPS to two dimensions.

## Method card

### What it is

PEPS represents a 2D quantum state as a network of rank-5 tensors (one per site, with physical leg d and four virtual legs of bond dimension D). The ansatz is designed so that area-law entanglement is satisfied at any fixed D. Contracting a PEPS network is #P-hard in general, so in practice contraction is done approximately using a corner transfer-matrix RG (CTMRG) or boundary-MPS environment with environment bond χ_env (typically χ_env ∝ D²). For infinite systems iPEPS uses a single unit-cell tensor optimized via full-update / simple-update / automatic differentiation (AD). The variational degrees of freedom (the D⁵-dimensional tensor per site) are optimized to minimize the energy, making iPEPS a controlled-bias variational method whose accuracy improves as D is increased.

### Properties (M1–M14)

| Axis | Value | Note |
|---|---|---|
| M1 tasks / outputs | GS energy & order parameters · correlation functions · correlation length (boundary transfer matrix) · thermodynamic limit directly (iPEPS) · entanglement entropy (approximate; from the finite-χ_env CTMRG environment, not a limitation of the PEPS ansatz) · topological order (representable at fixed D) | Dynamics and finite-T require specialized extensions (thermal-state PEPS, D-doubling); excitations via PEPS tangent space. |
| M2 regime | T=0 ground state (primary); thermodynamic limit via iPEPS | Finite-T harder: thermal-state PEPS or D-doubling approach; real-time dynamics via time-evolved PEPS (much harder). |
| M3 accuracy class | Controlled-bias (finite-D truncation + approximate contraction), deterministic; variational upper bound in the limit D→∞, χ_env→∞; at finite χ_env the approximate (CTMRG/boundary-MPS) contraction can break the strict variational bound | Both D (ansatz) and χ_env (contraction accuracy) must be converged; two independent knobs. |
| M4 dimension fit (A1) | **2D (its home)**; 3D explored but expensive; 1D → use MPS instead | Natural for square, triangular, kagome, honeycomb lattices. Quasi-1D (ladders) → MPS preferred. |
| M5 statistics & local dim (A3) | Spin / hard-core boson / soft-core boson / fermion (fPEPS with parity tensors) | Fermions need parity tensors (fermionic PEPS / fPEPS) to handle the fermionic sign consistently; modest additional overhead. |
| M6 entanglement regime (B5) | 2D area-law at fixed D; B6 criticality and B8 frustration inflate D | Area-law GS at manageable D ~ 4–16; critical / frustrated states need larger D for quantitative accuracy. |
| M7 sign-problem dependence (C12) | Sign-immune | Not a Monte Carlo method; applicable to frustrated magnets and doped fermions without sign problem. |
| M8 symmetry exploitation (C9/C10) | U(1) / SU(2) / Z₂ block-sparse virtual tensors; lattice point-group symmetry via symmetric iPEPS | Symmetric tensors reduce cost and improve convergence; AD-based optimization fully compatible with U(1)/SU(2) symmetry. |
| M9 time complexity | Observable eval O(χ_env³ D⁶) via CTMRG/boundary-MPS; variational full-update / AD optimization O(D¹⁰)–O(D¹²); simple update ~O(D⁵) per step | Contraction bottleneck dominates. χ_env ∝ D² is the standard choice. Simple update is fast but uses a mean-field environment. |
| M10 memory | O(χ_env² D⁴) for the environment tensors; O(D⁵) per site tensor | Environment tensors dominate for large χ_env. |
| M11 control knob | Virtual bond D (ansatz bias) + environment bond χ_env (contraction bias) | Both must be extrapolated: energy vs 1/D and energy vs 1/χ_env. Converged result requires D and χ_env both large. |
| M12 scale frontier | Thermodynamic limit directly (iPEPS, single unit cell); finite PEPS on patches up to ~20×20; practical D ≲ 16 for spin-½ | iPEPS is genuinely a thermodynamic-limit method; finite-size effects absent in principle for translationally invariant systems. |
| M13 primary approximation / bias | (1) Finite-D MPS-ansatz truncation (controlled, → 0 as D → ∞); (2) approximate contraction bias via χ_env (controlled, → 0 as χ_env → ∞) | Two independent biases must both be converged; simple-update environment is a less controlled approximation of the full environment. |
| M14 hard blocker / failure mode | Contraction cost scales as O(D¹⁰⁻¹²) for optimization → accessible D is small (typically D ≤ 16); 3D extremely expensive; real-time dynamics entanglement barrier; non-Hermitian / open system extensions immature | For strongly frustrated 2D magnets, very large D may be needed to resolve competing orders — computationally prohibitive at present. |

### Cost & scaling

- Time: O(χ_env³ D⁶) for observable evaluation; O(D¹⁰)–O(D¹²) for variational full-update/AD optimization; ~O(D⁵) for simple update per step
- Memory: O(χ_env² D⁴) environment + O(D⁵) per site tensor
- Control knob: virtual bond D (ansatz accuracy) and environment bond χ_env (contraction accuracy) — both must be converged
- Scale frontier: thermodynamic limit (iPEPS); practical D ≲ 16 for spin-½ on standard hardware

### Accuracy & guarantees

- Class: controlled-bias, deterministic; variational upper bound on energy
- Primary approximation & its control: finite-D MPS-ansatz bias + approximate-contraction bias; both → 0 as D, χ_env → ∞
- Error scaling: energy error ~ O(1/D^α) + O(1/χ_env^β) (empirical, model-dependent; not a rigorous bound); exponents α, β model-dependent; convergence checked by joint D/χ_env extrapolation

### Tasks it computes

- Ground-state energy and local observables (magnetization, density, bond energy) for 2D systems in the thermodynamic limit
- Correlation functions and correlation lengths (from transfer matrix of the boundary MPS)
- Phase boundaries and order parameters in 2D phase diagrams
- Entanglement entropy (approximately, from CTMRG environment)
- Topological order (representable in PEPS at finite D; TEE from PEPS tangent space or minimal-entangled states)

### Recommended for (models / regimes)

- **Primary GS solver for 2D lattice models**: 2D Heisenberg on square/triangular/kagome, 2D Hubbard model at half-filling and doped, frustrated J₁-J₂ models
- **Sign-ful 2D regimes** (frustrated magnets, doped fermions): sign-immune alternative to QMC
- **Thermodynamic-limit observables** without finite-size extrapolation (iPEPS)
- Per `method-property-map.md`: optimal when A1=2D, B5=2D-area-law, C12=sign-ful; disfavored for A1=3D, D13=real-time, or D=very large (cost prohibitive)

### Key reference

[@naumann_2023_introduction] — pedagogical introduction to iPEPS with AD-based optimization; covers CTMRG environment, variational algorithms, and modern AD workflow; most accessible entry point for practitioners.
Rendered: `../../literature/peps-based-algorithm/2308.12358_an-introduction-to-infinite-projected-entangled-pair-state-m.md` _(reused)_.

[@ors_2013_practical] — broader TN introduction covering both MPS and PEPS with practical computational details; useful complement for the CTMRG and environment formalism.
Rendered: `../../literature/mps-based-algorithm/1306.2164_a-practical-introduction-to-tensor-networks-matrix-product-s.md` _(reused)_.

### Benchmarks

- 2D Heisenberg square lattice (iPEPS, D=10, χ_env=100): e₀ = −0.66934(4) J/site, consistent with QMC benchmark −0.66934(4) [Corboz 2016; survey §3.2].
- 2D Hubbard (iPEPS, D=8, half-filling): double occupancy and energy vs doping in good agreement with diagrammatic QMC at moderate U/t [survey §3.2].
- Simple-update D=8 vs full-update D=8: full-update lowers energy by ~0.5–1% and is more accurate for frustrated models [survey §3.2].

## How it is used / Operational

**Owning skill:** `/method-peps` (primary); tool skill `/using-pepskit`.

**Default workflow:**
1. Set up the iPEPS unit cell (single site or multi-site for broken symmetry phases); choose initial random or product-state tensors with bond D_init = 2–4.
2. Run simple-update imaginary-time evolution to get a good starting point (cheap, ~O(D⁵)).
3. Switch to full-update or AD gradient optimization (more accurate CTMRG environment, χ_env ∝ D²); increase D in steps (D = 4 → 8 → 12 → 16).
4. For each (D, χ_env), converge energy to < 10⁻⁶ per optimization step.
5. Extrapolate energy vs 1/χ_env at fixed D to remove contraction bias; then extrapolate vs 1/D.
6. Extract observables (magnetization, bond energy, correlation length) from the converged CTMRG environment.

**Verification pointers:**
- For sign-free models, cross-check against QMC (the gold standard for 2D without frustration).
- Verify that the CTMRG environment has converged (energy stable vs χ_env).
- Compare simple-update vs full-update energies to bound the environment-approximation error.
- For topological phases, check TEE or topological degeneracy on a torus.

**Cross-links:**
- Survey: `method-survey.md` §3.2 (PEPS / iPEPS — 2D)
- Model↔method gate: `method-property-map.md` (iPEPS profile)
- Complementary methods: DMRG (1D/quasi-1D and cylinder benchmarks), VMC/NQS (sign-immune alternative), QMC (sign-free 2D benchmark)
