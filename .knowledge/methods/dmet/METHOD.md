<!-- Method-card template. Axis definitions: ../method-property-checklist.md (M1–M14).
     Inverse model→method map: ../method-property-map.md. Cost derivations & citations:
     ../method-survey.md. Cite keys resolve in ./ref.bib. -->

# Density Matrix Embedding Theory (DMET)

Embeds a fragment of the lattice into a bath constructed from the Schmidt decomposition of a mean-field reference state; solves the fragment + bath with a high-level impurity solver and matches the 1-RDM self-consistently.

## Method card

### What it is

DMET (Knizia–Chan 2012) partitions the lattice into a fragment of `N_frag` sites and an environment. A mean-field (HF or BCS) state on the full lattice is used to construct the Schmidt basis: the `N_frag` bath orbitals that are entangled with the fragment form an "embedding Hamiltonian" of size `2·N_frag` (fragment + bath). This small system is solved with a high-level impurity solver (FCI, DMRG, or CCSD) to obtain the correlated fragment 1-RDM and energy. The mean-field "correlation potential" (a one-body Hamiltonian additive) is then adjusted self-consistently until the fragment and bath 1-RDMs are consistent. The approach is systematically improvable by increasing `N_frag`.

### Properties (M1–M14)

| Axis | Value | Note |
|---|---|---|
| M1 tasks / outputs | Ground-state energy · local observables (density, magnetization, double occupancy) · phase diagrams | Spectral functions are harder; frequency-dependent DMET extensions exist but are not routine. |
| M2 regime | T=0 (ground state) | Finite-T DMET extensions exist but are less developed. |
| M3 accuracy class | Controlled by fragment size `N_frag` + embedded solver (DMRG/FCI); deterministic | Accuracy improves systematically with `N_frag`; controlled by the embedded solver (FCI is exact within the embedding). |
| M4 dimension fit (A1) | Any dimension | Unlike DMFT, DMET is not restricted to infinite dimension; applicable in 1D, 2D, 3D. |
| M5 statistics & local dim (A3) | Fermions primarily; bosonic DMET extensions exist | Local Hilbert dim enters through the embedded solver (`d^{2N_frag}` for FCI). |
| M6 entanglement regime (B5) | Fragment-bath entanglement captured by the Schmidt basis | The Schmidt bath truncation (exactly `N_frag` bath orbitals) limits long-range entanglement; controlled by `N_frag`. |
| M7 sign-problem dependence (C12) | Sign-problem enters only via the embedded solver | FCI and DMRG embedded solvers are sign-immune; AFQMC embedded solver carries a constraint bias. |
| M8 symmetry exploitation (C9/C10) | Lattice symmetries can be exploited in the embedded problem and to partition the fragment tiling | Translation symmetry of the tiling reduces the number of inequivalent fragments. |
| M9 time complexity | Dominated by the impurity solver on the `2·N_frag`-site embedding: FCI `O(d^{2N_frag})`, DMRG `O(N_frag·χ³)` for 1D fragments, CCSD `O(N_frag⁶)` | Self-consistency loop on the correlation potential is cheap relative to the solver; larger `N_frag` → exponentially harder solver (for FCI). |
| M10 memory | Dominated by the embedded solver: FCI `O(d^{2N_frag})`, DMRG `O(d·χ²)` | Memory wall is the embedded solver; manageable for `N_frag ≲ 10` with FCI, larger with DMRG. |
| M11 control knob | Fragment size `N_frag` — controls spatial resolution and accuracy; embedded solver accuracy (bond dim `χ` for DMRG, or truncation for CCSD) | The two knobs must be jointly converged; FCI gives exact embedding at fixed `N_frag`. |
| M12 scale frontier | Thermodynamic limit by tiling; fragment `N_frag` ~ 2–36 sites in practice; limited by embedded solver | With DMRG embedded solver: `N_frag` ~ 36 (1D strips) accessible; FCI: `N_frag` ~ 8–12. |
| M13 primary approximation / bias | Fragment/bath truncation (Schmidt basis limited to `N_frag` bath orbitals); self-consistency on 1-RDM (not the full wavefunction) | Controlled by `N_frag`; the Schmidt bath exactly captures all fragment-environment entanglement at fixed mean-field reference. |
| M14 hard blocker / failure mode | Embedded solver cost grows exponentially with `N_frag` (FCI); 2D fragments require large `N_frag` for spatial convergence; long-range correlations beyond fragment size not captured | Self-consistency can have convergence issues (multiple solutions); spectral functions not natively accessible. |

### Cost & scaling

- Time: embedded solver on `2·N_frag` sites: FCI `O(d^{2N_frag})`, DMRG `O(N_frag·χ³)`, CCSD `O(N_frag⁶)`; self-consistency loop cheap
- Memory: embedded solver: FCI `O(d^{2N_frag})`, DMRG `O(d·χ²)`
- Control knob: `N_frag` (fragment size, spatial resolution and accuracy) + embedded solver knob (`χ` for DMRG)
- Scale frontier: thermodynamic limit by tiling; `N_frag` ~ 2–36 in practice

### Accuracy & guarantees

- Class: controlled (in `N_frag` and embedded solver accuracy); deterministic
- Primary approximation & its control: Schmidt bath truncation to `N_frag` orbitals; FCI embedding is exact at fixed `N_frag`
- Error scaling: systematic in `N_frag`; convergence rate depends on correlation length relative to fragment size

### Tasks it computes

- Ground-state energy density (thermodynamic limit by tiling + extrapolation)
- Local observables: on-site density, magnetization, double occupancy, nearest-neighbor correlations
- Phase diagrams as function of interaction strength / filling (Mott transition, magnetism, superconductivity)
- Spectral functions via frequency-dependent DMET or GF-DMET extensions (not routine)

### Recommended for (models / regimes)

- **Hubbard model in 2D** where DMRG is expensive (finite width) and QMC has sign problem
- **Correlated electron problems in any dimension** where DMFT spatial correlation neglect is unsatisfactory
- **Strongly-correlated lattice models** (B7 strong correlation OK, unlike perturbation theory)
- **Complement to DMFT**: DMET at small `N_frag` ~ DMFT; growing `N_frag` systematically improves spatial correlations
- Per `method-property-map.md`: applicable when 2D/3D frustration blocks QMC and spatial correlations beyond single-site DMFT are needed

### Key reference

[@knizia_2012_density] — original DMET paper introducing the Schmidt-bath embedding and self-consistency scheme; benchmarks on 1D and 2D Hubbard models.
Rendered: `./1204.5783_density-matrix-embedding-a-simple-alternative-to-dynamical-m.md` _(downloaded)_.

### Benchmarks

- 1D Hubbard at half-filling: DMET energy agrees with Bethe Ansatz to < 0.1% for `N_frag = 2` [@knizia_2012_density].
- 2D Hubbard: DMET with `N_frag = 4–16` matches AFQMC/DMRG benchmark energies to ~0.5% at `U/t = 4–8` [method-survey.md §6.2].
- Mott transition: DMET correctly captures the metal-insulator transition for the half-filled Hubbard model [@knizia_2012_density].

## How it is used / Operational

**Harness coverage:** DMET is a quantum-embedding method **outside the current harness skill set**. No dedicated `/method-dmet` skill exists. The embedded solver may be called via `/method-ed` (FCI) or `/method-mps` (DMRG), but the DMET self-consistency loop and Schmidt-bath construction are not harness-automated.

**External tools:** PySCF-DMET, Libcint-based DMET codes, or research codes from the Chan group.

**Standard workflow:**
1. Run a mean-field (HF/BCS) calculation on the full lattice to obtain the 1-RDM.
2. Partition the lattice into fragments; perform Schmidt decomposition to construct `N_frag` bath orbitals per fragment.
3. Build the embedded Hamiltonian (fragment + bath, size `2·N_frag`).
4. Solve with FCI / DMRG / CCSD; extract fragment 1-RDM and energy.
5. Update the correlation potential (one-body additive) to match bath 1-RDM to mean-field; repeat from step 1 until convergence.

**Verification pointers:**
- Check energy per site against ED or DMRG for 1D Hubbard at accessible `N_frag`.
- Verify fragment 1-RDM self-consistency: residual `‖γ_frag - γ_bath‖ < ε`.
- Converge in `N_frag` (compare `N_frag = 2, 4, 8`).

**Cross-links:**
- Survey: `method-survey.md` §6.2 (DMET)
- Model↔method gate: `method-property-map.md`
- Complementary: DMFT (§6.1, wave-F card — single-site limit); `/method-mps` (DMRG embedded solver); `/method-ed` (FCI embedded solver for small fragments)
