<!-- Method-card template. Axis definitions: ../method-property-checklist.md (M1–M14).
     Inverse model→method map: ../method-property-map.md. Cost derivations & citations:
     ../method-survey.md. Cite keys resolve in ../ref.bib. -->

# Full Configuration Interaction (FCI)

Exact diagonalization in the many-electron determinant (Slater-determinant) basis; the gold-standard exact solver for quantum chemistry and the orbital-based limit of lattice ED.

## Method card

### What it is

FCI constructs the complete many-electron Hilbert space as all possible Slater determinants formed from `N_e` electrons distributed among `2·N_orb` spin-orbitals (spatial orbitals `×` spin), giving a Hilbert-space dimension `C(2·N_orb, N_e)`. The Hamiltonian (in second-quantized form using one- and two-electron integrals) is diagonalized exactly, yielding numerically-exact energies and wavefunctions within the chosen single-particle basis. FCI is the quantum-chemistry equivalent of lattice ED full (§1.1) but formulated for fermions with `d=4` per spatial orbital (empty, spin-up, spin-down, doubly-occupied). Selected-CI variants (CIPSI, heat-bath CI, FCIQMC) adaptively sample the dominant determinants, achieving near-FCI accuracy at reduced cost; FCIQMC uses a Monte Carlo imaginary-time projection in determinant space to avoid storing the full coefficient vector. All variants share the same exponential wall in the number of orbitals.

### Properties (M1–M14)

| Axis | Value | Note |
|---|---|---|
| M1 tasks / outputs | Exact ground-state energy and wavefunction · few excited states (EOM-FCI / excited-state CI) · one- and two-particle reduced density matrices (1-RDM, 2-RDM) · benchmark for approximate quantum-chemistry methods (CCSD, CASPT2, DMRG-CI) | FCI is the benchmark target; other methods are benchmarked against it. |
| M2 regime | T=0 ground state (primary); few excited states via sector targeting | Finite-T FCI possible (canonical-ensemble ED) but rarely used for chemistry; more relevant in lattice-model context. |
| M3 accuracy class | Numerically exact, deterministic (exact FCI); controlled-bias stochastic (FCIQMC, selected-CI) | Exact FCI = numerically exact within the chosen single-particle basis. FCIQMC = stochastic, error `∝ 1/√N_w·N_steps`; selected-CI = variational upper bound with improvable selection threshold. |
| M4 dimension fit (A1) | Molecules and lattice clusters in any geometry (A1 irrelevant — FCI is basis-set, not lattice, driven) | Applicable to any molecular or cluster geometry; cost set by #orbitals, not spatial dimension. |
| M5 statistics & local dim (A3) | Fermions only; local dimension `d = 4` per spatial orbital (empty/up/down/doubly-occupied) | `d=4` per orbital is a factor of 4 harder than spin-½ per site; `D_H = C(2·N_orb, N_e)` grows exponentially in `N_orb`. |
| M6 entanglement regime (B5) | Volume-law tolerated | No entanglement restriction; exact FCI stores the full coefficient vector of length `D_H`. |
| M7 sign-problem dependence (C12) | Sign-immune (exact FCI, selected-CI) · stochastic with sign (FCIQMC, controlled by annihilation) | Exact FCI: sign-immune (direct matrix diagonalization). FCIQMC: fermionic sign problem controlled by the annihilation step, giving unbiased results in principle [@booth_2009_fermion]. |
| M8 symmetry exploitation (C9/C10) | Sᶻ (N_↑, N_↓) + S² (spin symmetry) + spatial point-group (irreducible representations) reduce `D_H` | Point-group symmetry (C₂v, D₂h, etc.) of the molecule reduces the Hamiltonian block size; key cost lever analogous to translation symmetry in lattice ED. |
| M9 time complexity | Exponential in `N_orb`: `O(D_H³)` for direct dense diagonalization (LAPACK); `O(N_orb² · D_H)` per Davidson/Lanczos iteration (dominant two-electron sigma-vector step) | In practice, the Davidson iterative solver is used (analogous to Lanczos); memory `O(D_H)` per vector. Exponential wall prevents scaling beyond ~20 orbitals for exact FCI. |
| M10 memory | `O(D_H)` for iterative (Davidson/Lanczos FCI); `O(D_H²)` for dense diagonalization | Davidson FCI: stores a few vectors of length `D_H`; dense FCI (LAPACK): stores the full matrix `D_H × D_H`. |
| M11 control knob | `N_orb` (number of active orbitals) — the primary convergence parameter; for selected-CI: selection threshold `ε₁` (controls which determinants are included) | Increasing `N_orb` → exponential cost increase. Selected-CI threshold `ε₁ → 0` → exact FCI. FCIQMC: `N_w` (number of walkers) controls statistical error. |
| M12 scale frontier | ~18–20 spatial orbitals in routine codes (Davidson FCI); **~10¹² determinants** at the distributed-memory frontier (trillion-determinant FCI, JCTC 2024); selected-CI extends effective reach via sparsity | The 10¹² frontier uses specialized bit-string algorithms and distributed memory; routine use is ~`N_orb ≈ 16` (CASSCF active space). |
| M13 primary approximation / bias | Basis-set incompleteness (choice of single-particle orbitals); none within the chosen orbital space — FCI is exact in the given basis | Extrapolation to the complete-basis-set (CBS) limit is the main source of remaining error. For selected-CI: selection threshold bias (variational, controlled). |
| M14 hard blocker / failure mode | Exponential scaling in `N_orb`: `D_H = C(2·N_orb, N_e)` grows as `~4^{N_orb}` (at half-filling) — the `d^N` wall translated to orbital language; standard FCI is limited to active spaces of ~20 orbitals | FCIQMC and selected-CI push the frontier but cannot escape the exponential wall for strongly correlated systems with many active orbitals. |

### Cost & scaling

- Time: exponential in `N_orb`; Davidson iterative FCI `≈ O(N_orb² · D_H)` per iteration (dominant two-electron sigma-vector); dense diag `O(D_H³)`
- Memory: `O(D_H)` for iterative (Davidson); `O(D_H^2)` for dense; `D_H = C(2·N_orb, N_e)`
- Control knob: `N_orb` (active orbitals, exponential cost); selected-CI threshold `ε₁` (improvable bias); FCIQMC walker count `N_w` (statistical error `1/√N_w`)
- Scale frontier: ~18–20 orbitals routine; ~10¹² determinants at the distributed-memory frontier (JCTC 2024)

### Accuracy & guarantees

- Class: numerically exact (exact FCI); variational upper bound (selected-CI); controlled-bias stochastic (FCIQMC)
- Primary approximation & its control: single-particle basis choice (basis-set incompleteness); within the basis, exact FCI is numerically exact
- Error scaling: basis-set error → CBS extrapolation; selected-CI threshold bias → `ε₁ → 0` recovers exact FCI; FCIQMC statistical error `∝ 1/√(N_w · N_steps)`

### Tasks it computes

- Exact ground-state energy and wavefunction in a given orbital basis
- 1-RDM and 2-RDM for computing molecular properties (multipole moments, response)
- Few excited states via excited-state FCI / EOM-FCI
- Benchmark reference for CCSD(T), CASPT2, DMRG-CI, AFQMC
- Orbital entanglement entropy (for DMRG-CI active-space selection)

### Recommended for (models / regimes)

- **Quantum chemistry benchmarks:** small molecules (H₂, N₂, F₂, H₂O) in moderately large basis sets; the exact reference for all approximate methods
- **Strongly correlated active spaces:** any system with static correlation (B8 frustration in the molecular sense: degeneracies, open shells) up to `N_orb ≈ 20`
- **Lattice Hubbard / Anderson models in orbital language:** FCI is identical to lattice ED full when the single-particle basis is the site basis (`d=4` Hubbard); selected-CI (FCIQMC, CIPSI) pushes to larger `N_orb`
- **FCIQMC / selected-CI for larger active spaces:** `N_orb ≈ 30–100` with near-FCI accuracy via stochastic sampling of the dominant determinants
- Per `method-property-map.md` (ED profile): FCI is the quantum-chemistry arm of the ED harness; `/method-ed` skill; fermionic, any geometry

### Key reference

[@booth_2009_fermion] — original FCIQMC paper by Booth, Thom, and Alavi; introduces the Monte Carlo imaginary-time projection in determinant space, demonstrating exact FCI-quality results for systems beyond the reach of conventional FCI (C₂ molecule in cc-pVDZ, 10⁸–10¹⁰ determinants); the foundational reference for stochastic approaches to FCI.
Rendered: `./10-1063-1-3193710.md` _(downloaded — abstract only; no open-access PDF available)_.

### Benchmarks

- Routine FCI scale: **~18–20 active orbitals** in codes like PySCF, OpenFCI, Dice (CASSCF active spaces) [method-survey.md §1.5].
- Distributed-memory frontier: **~10¹² determinants** (trillion-determinant FCI) [method-survey.md §1.5, citing JCTC 2024].
- FCIQMC on C₂ (cc-pVDZ, 28 electrons, 28 orbitals): energy converged to within 0.1 mEh of exact FCI using `N_w ≈ 10^8` walkers [@booth_2009_fermion].
- Selected-CI (CIPSI/heat-bath CI): near-FCI accuracy for `N_orb ≈ 30–50` with selected-CI threshold `ε₁ ≈ 10^{-5}` [method-survey.md §1.5].

## How it is used / Operational

**Owning skill:** `/method-ed` (primary), with tool skills `/using-xdiag` (lattice FCI / Hubbard) and `/using-quspin` (fermionic lattice models in the site basis).

For quantum-chemistry FCI (molecular orbital basis), standard codes are PySCF (`pyscf.fci.FCI`), OpenMolcas, or FCIQMC codes (NECI, `dice` for heat-bath CI).

**Default workflow:**
1. Define the active space: select `N_orb` spatial orbitals and `N_e` electrons (CASSCF orbital selection if needed).
2. Compute the one- and two-electron integrals in the chosen basis.
3. Apply symmetry reduction: Sᶻ (N_↑, N_↓), S² (spin), point-group irrep.
4. Run the Davidson (or Lanczos) iterative diagonalization within the selected symmetry block.
5. Compute the 1-RDM and 2-RDM from the FCI wavefunction for property evaluation.

**Verification pointers:**
- Variational principle: FCI energy ≤ CCSD(T) energy for the same basis.
- S² eigenvalue: `⟨S²⟩ = S(S+1)` to machine precision (verify spin purity).
- Orbital entanglement entropy `s_i = -∑_σ λ_σ ln λ_σ` (from 1-RDM): identifies strongly correlated orbitals for DMRG-CI active-space selection.
- For FCIQMC: energy convergence with `N_w`; plateau in walker growth signals the sign problem being controlled.

**Cross-links:**
- Survey: `method-survey.md` §1.5 (Full configuration interaction)
- Model↔method gate: `method-property-map.md` (ED profile — fermionic, A3 = fermion)
- Complementary methods: ED full / ED Lanczos (lattice models in site basis), CCSD(T) (approximate, larger `N_orb`), DMRG-CI (1D orbital entanglement structure, `N_orb ≈ 50–100`), AFQMC/CPMC (stochastic, polynomial cost, phaseless bias)
