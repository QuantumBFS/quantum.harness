<!-- Method-card template. Axis definitions: ../method-property-checklist.md (M1–M14).
     Inverse model→method map: ../method-property-map.md. Cost derivations & citations:
     ../method-survey.md. Cite keys resolve in ./ref.bib. -->

# Path-Integral Monte Carlo (PIMC)

Finite-temperature Monte Carlo for bosons (and fermions with sign handling) via the imaginary-time path-integral representation `Z = Tr[e^{−βH}]`.

## Method card

### What it is

PIMC maps the quantum partition function `Z = Tr[e^{−βH}]` to a classical statistical mechanics problem by discretizing imaginary time into `N_τ = β/Δτ` slices and inserting completeness relations, producing a sum over closed worldline paths. For bosons, the paths can permute particle labels (Bose–Einstein statistics), and the **worm algorithm** (Prokof'ev–Svistunov) efficiently samples both diagonal (thermodynamic) and off-diagonal (one-body density matrix, superfluid) configurations. Superfluid density is measured directly from the mean-square winding number of worldlines (Pollock–Ceperley estimator). For fermions the antisymmetry reintroduces the sign problem via odd permutations. The method is exact in the limit `N_τ→∞` (continuum imaginary time) and `N_s→∞` for bosons.

### Properties (M1–M14)

| Axis | Value | Note |
|---|---|---|
| M1 tasks / outputs | Finite-T thermodynamics (energy, specific heat, pressure, compressibility) · superfluid density (winding number) · condensate fraction (off-diagonal density matrix `n(r)`) · structure factors `S(q)` · pair correlations `g(r)` | Spectra require analytic continuation; real-time dynamics inaccessible. |
| M2 regime | Finite-T (primary); T→0 limit feasible but expensive | The natural regime is finite temperature; GS by taking `β→∞`. |
| M3 accuracy class | Numerically exact (bosons, sign-free), stochastic | Statistical error `∝1/√N_s`; Trotter/discretization error `O(Δτ^p)` controlled by `N_τ→∞`; fermion sign problem degrades accuracy. |
| M4 dimension fit (A1) | Any dimension; continuum (⁴He) or lattice | Particularly powerful in 3D continuum for quantum liquids and cold atoms. |
| M5 statistics & local dim (A3) | **Bosons (sign-free)** — the primary regime; fermions reintroduce the sign problem via odd permutations | For fermions, the sign problem returns and cost is exponential; restricted PIMC (fixed-node analog) controls it with bias. |
| M6 entanglement regime (B5) | Volume-law tolerated | Worldline sampling has no entanglement restriction; the sign problem is the gate for fermions. |
| M7 sign-problem dependence (C12) | Sign-free for bosons; fermions reintroduce the sign via odd permutation exchanges | For bosonic systems PIMC is numerically exact; fermion PIMC requires restricted PIMC (nodal-surface bias) analogous to fixed-node DMC. |
| M8 symmetry exploitation (C9/C10) | Continuous translational symmetry handled naturally in the continuum; lattice models use discrete symmetry to reduce sampling space | Permutation symmetry is essential for bosonic exchange statistics; the worm algorithm samples exchange cycles directly. |
| M9 time complexity | `O(N·N_τ)` per sweep; **worm algorithm** for efficient winding/superfluid sampling | `N_τ = β/Δτ`; worm updates propose open/close operations to sample the off-diagonal sector (condensate, superfluid density) efficiently. |
| M10 memory | `O(N·N_τ)` for the worldline configurations | Modest compared to wavefunction methods; total path of all particles stored. |
| M11 control knob | `N_τ` (imaginary-time slices) → discretization error `O(Δτ^p)`; `N_s` (sweeps) → statistical error `∝1/√N_s` | Convergence in `N_τ` tested by comparing `N_τ` and `2N_τ`; standard extrapolation to continuum limit. |
| M12 scale frontier | `N~100`–`10000` particles (continuum bosons); thermodynamic-limit extrapolation via finite-size scaling | State-of-the-art for ⁴He, cold bosonic atoms, hydrogen at high pressure. |
| M13 primary approximation / bias | Trotter/discretization error `O(Δτ^p)` — controlled by `N_τ→∞`; none for bosons in the continuum limit | For fermions, restricted PIMC introduces a nodal-surface bias analogous to fixed-node DMC. |
| M14 hard blocker / failure mode | Fermion sign problem via odd permutation exchanges: cost `∝1/⟨s⟩²` grows exponentially with `βN`; analytic continuation for spectral functions is ill-posed | Even for bosons, very low temperatures require large `N_τ`, raising cost linearly with `β`. |

### Cost & scaling

- Time: `O(N·N_τ)` per sweep; worm algorithm adds efficient off-diagonal sampling
- Memory: `O(N·N_τ)` worldline paths
- Control knob: `N_τ` (discretization error `O(Δτ^p)`); `N_s` (statistical error `∝1/√N_s`)
- Scale frontier: `N~100`–`10000` (continuum bosons); thermodynamic limit via finite-size scaling

### Accuracy & guarantees

- Class: numerically exact (bosons), stochastic
- Primary approximation & its control: Trotter discretization `O(Δτ^p)` → controlled by `N_τ→∞` extrapolation
- Error scaling: statistical `∝1/√N_s`; discretization `O(Δτ^p)` → extrapolated away; fermion sign degrades both

### Tasks it computes

- Finite-temperature thermodynamics: energy, specific heat, pressure, entropy
- Superfluid density from winding-number estimator `ρ_s/ρ = ⟨W²⟩ L² / (2 d λ β N), with λ = ħ²/2m (d = spatial dimension)` (Pollock–Ceperley)
- Condensate fraction and one-body density matrix `n(r,r')` from the open worldline (worm) sector
- Structure factor `S(q)` and pair-correlation function `g(r)`
- For ⁴He: equation of state, lambda transition, superfluid fraction vs temperature

### Recommended for (models / regimes)

- **Bosonic quantum liquids (⁴He, ³He–⁴He mixtures):** the definitive method for finite-T superfluid properties
- **Ultracold bosonic atoms in optical lattices:** Bose-Hubbard phase diagram, superfluid-Mott transition
- **Hydrogen and helium at high pressure:** PIMC with fermion nodal approximation used for planetary-interior equations of state
- **Benchmark for continuum bosons at finite T:** exact alternative to SSE when continuum rather than lattice description is needed
- Per `method-property-map.md`: preferred for sign-free bosonic continuum systems at finite T; blocked by fermion sign problem

### Key reference

[@ceperley_1995_path] — comprehensive review of PIMC for quantum liquids: path-integral formulation, Bose–Einstein statistics and exchange, superfluid density estimator, ⁴He benchmarks; the canonical reference for the method.
Rendered: _(none — bib stub; PDF paywalled, no arXiv preprint available)_.

### Benchmarks

- ⁴He lambda transition: PIMC reproduces the superfluid fraction `ρ_s/ρ` vs T curve, including the transition temperature `T_λ ≈ 2.17 K`, from first principles [@ceperley_1995_path].
- Condensate fraction ⁴He at `T=1 K, P=0`: `n_0 ≈ 7.25%` — experimental value matched by PIMC [@ceperley_1995_path].

## How it is used / Operational

**Owning skill:** `/method-qmc`. No dedicated harness tool skill exists for PIMC — use the ALPS PIMC code, PIMC++ (Ceperley group), or the open-source `pimcpy` package directly.

**Default workflow:**
1. Write the interaction potential (⁴He: Aziz potential; lattice: hopping + on-site terms).
2. Set `β`, `N_τ`, and particle number `N`; initialize worldlines.
3. Run worm-algorithm updates (open/close, insert/remove, advance/recede) to sample both diagonal and off-diagonal configurations.
4. Accumulate thermodynamic estimators (energy via virial or thermodynamic estimator), winding-number distribution, off-diagonal OBDM.
5. Extrapolate `N_τ→∞` (discretization test at `2N_τ`); perform finite-size scaling over `N`.
6. For `S(q,ω)`: feed imaginary-time correlations `G(q,τ)` into analytic continuation (MaxEnt).

**Verification pointers:**
- Superfluid density: compare winding-number estimator `ρ_s/ρ = ⟨W²⟩ L² / (2 d λ β N), with λ = ħ²/2m (d = spatial dimension)` to known ⁴He experimental values at `T<T_λ`.
- Discretization check: energy difference between `N_τ` and `2N_τ` runs should be `<0.1%` for well-chosen `Δτ`.
- For sign-free check: confirm bosonic permutations only (no fermion anti-symmetry needed).

**Cross-links:**
- Survey: `method-survey.md` §4.7 (Path-integral Monte Carlo)
- Model↔method gate: `method-property-map.md` (PIMC profile)
- Complementary methods: SSE (lattice bosons at finite T — sign-free, complements PIMC for lattice models); DMC-GFMC (T=0 bosons — exact, complementary); DQMC (finite-T fermions — auxiliary-field approach)
