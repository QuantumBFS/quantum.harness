<!-- Method-card template. Axis definitions: ../method-property-checklist.md (M1–M14).
     Inverse model→method map: ../method-property-map.md. Cost derivations & citations:
     ../method-survey.md. Cite keys resolve in ./ref.bib. -->

# Coupled Cluster (CC)

Exponential cluster ansatz `e^T|HF⟩` acting on a Hartree–Fock reference; size-extensive, high-accuracy ground-state energetics for weakly-to-moderately correlated systems.

## Method card

### What it is

Coupled cluster theory parameterizes the many-body wavefunction as `|ψ⟩ = e^T |HF⟩`, where `T = T₁ + T₂ + ...` is the cluster operator (sum of single, double, ..., `n`-particle excitations). Truncating at doubles gives CCSD; including a non-iterative perturbative triples correction gives CCSD(T) — the "gold standard" of quantum chemistry. The amplitude equations are solved by a non-Hermitian eigenvalue problem on the projected Schrödinger equation. The method is size-extensive by construction (energy scales correctly with system size). Periodic CCSD/CCSD(T) extends this to solids. EOM-CC (equation-of-motion CC) computes excited states and spectra at higher cost. The accuracy is excellent when the HF reference is a good starting point (weak–moderate dynamic correlation), but collapses for strong static correlation / open-shell degeneracy (single-reference breakdown).

### Properties (M1–M14)

| Axis | Value | Note |
|---|---|---|
| M1 tasks / outputs | Ground-state energies and observables (high accuracy) · EOM-CC for excitations / spectra · ionization potentials and electron affinities (IP/EA-EOM-CC) | High accuracy when single-reference; EOM-CC gives excited states but at `O(N⁶)`–`O(N⁷)` cost. |
| M2 regime | T=0 (ground state and selected excited states) | Finite-T extensions (thermal CC) exist but are non-standard. |
| M3 accuracy class | Controlled (CC hierarchy T₁T₂T₃... → FCI limit); deterministic; excellent for dynamic correlation | Accuracy collapses for strong static correlation (multi-reference breakdown); not variational. |
| M4 dimension fit (A1) | Any dimension (molecular and periodic/solid-state variants) | Periodic CCSD/CCSD(T) for solids (e.g. crystalline materials); EOM-CC for surfaces and defects. |
| M5 statistics & local dim (A3) | Fermions | Local Hilbert dim enters through the number of virtual orbitals `N`; cost scales `O(N⁶)`–`O(N⁷)`. |
| M6 entanglement regime (B5) | Dynamic correlation (moderate entanglement) | Excellent for weakly-entangled systems; breaks down for volume-law / strongly-entangled (multi-reference) states. |
| M7 sign-problem dependence (C12) | Sign-immune (not a Monte Carlo method) | Deterministic algebraic equations; no sign problem. |
| M8 symmetry exploitation (C9/C10) | Point group, spin, and translational symmetry reduce the orbital/amplitude space | Symmetry-adapted CC reduces the number of independent amplitudes and cuts cost. |
| M9 time complexity | **CCSD `O(N⁶)`, CCSD(T) `O(N⁷)`** in the number of orbitals `N` | The "gold standard" scaling of quantum chemistry; `N` here is total orbital count (occupied + virtual). |
| M10 memory | `O(N⁴)` for storing the two-particle amplitudes `T₂` (dominant cost) | The `T₂` tensor with four orbital indices is the memory bottleneck; `O(N_occ² · N_virt²)`. |
| M11 control knob | CC hierarchy level (CCSD → CCSD(T) → CCSDT → ...) + basis set completeness | The CC expansion is systematically improvable toward FCI; basis set extrapolation is also needed. |
| M12 scale frontier | ~100–500 orbitals for CCSD (molecular); ~20–50 k-points for periodic CCSD; fragmentation/local CC extends reach | Explicitly correlated F12-CCSD(T) improves basis convergence; local CC (DLPNO-CCSD(T)) reaches 1000s of atoms. |
| M13 primary approximation / bias | Single-reference assumption (T acts on a single HF determinant) — **fails for strong static correlation / open-shell degeneracy / frustration** | Multi-reference CC (MRCC) extends reach but is much more costly and complex. |
| M14 hard blocker / failure mode | **Strong static correlation / frustration / open-shell degeneracy**: single-reference breakdown — `T₁` diagnostic `> 0.02` signals multi-reference character and unreliable results | Frustrated lattice models (B8), doped Mott insulators, near-degenerate transition states: CC is not the right tool. |

### Cost & scaling

- Time: **CCSD `O(N⁶)`, CCSD(T) `O(N⁷)`** in orbital count `N`
- Memory: `O(N⁴)` for `T₂` amplitudes (`N_occ² × N_virt²`)
- Control knob: CC hierarchy level (CCSD → CCSD(T) → CCSDT) + basis set size
- Scale frontier: ~100–500 orbitals for CCSD; ~1000s of atoms with local DLPNO-CCSD(T)

### Accuracy & guarantees

- Class: controlled (CC hierarchy toward FCI); not variational; deterministic
- Primary approximation & its control: truncation of `T` at doubles (CCSD) or perturbative triples (CCSD(T)); controlled by CC hierarchy
- Error scaling: CCSD(T) errors typically < 1 kcal/mol for weakly-correlated systems; collapses for multi-reference cases

### Tasks it computes

- Ground-state electronic energies (atomization energies, reaction barriers, binding energies) with sub-kcal/mol accuracy when single-reference
- EOM-CCSD excited states (vertical excitation energies, oscillator strengths)
- IP/EA-EOM-CC for ionization potentials and electron affinities
- Periodic CCSD/CCSD(T) for cohesive energies and band gaps of weakly-correlated solids
- Local CC (DLPNO) for large molecular systems

### Recommended for (models / regimes)

- **Quantum chemistry: molecular energetics** — the gold standard for weakly–moderately correlated molecules (when `T₁ < 0.02`)
- **Periodic CCSD(T) for solids** without strong static correlation (metals with moderate `U/t`, van der Waals solids)
- **Benchmark reference** for DFT, HF, and perturbation theory (MP2) comparisons
- **EOM-CC for excitation spectra** of weakly-correlated systems
- Per `method-property-map.md`: do NOT use for frustrated magnets (B8), doped Mott insulators (B7 strong), or strongly-entangled states

### Key reference

[@bartlett_2007_coupled] — comprehensive review of CC theory in quantum chemistry: amplitude equations, CCSD(T) derivation, EOM-CC, and applications across quantum chemistry.
Rendered: _(none — bib stub; see literature INDEX)_.

### Benchmarks

- CCSD(T)/CBS atomization energies: mean absolute deviation < 0.5 kcal/mol for the W4 thermochemistry benchmark set [@bartlett_2007_coupled].
- `T₁` diagnostic: `T₁ > 0.02` for HF, `T₁ ~ 0.05` for biradicals — signals multi-reference breakdown [@bartlett_2007_coupled].
- Periodic CCSD(T): cohesive energy of solid Ne to < 0.1 meV/atom [method-survey.md §6.5].

## How it is used / Operational

**Harness coverage:** Coupled cluster is a quantum-chemistry / perturbative method **outside the current harness skill set**. No dedicated `/method-cc` skill exists. It is not one of the core harness method skills (ED, MPS, PEPS, QMC, VMC, MF, LTRG, MCRG, QCS, PolyOpt). The embedded-solver use of CCSD within DMET is the closest connection to the harness.

**External tools:** PySCF (Python), ORCA, CFOUR, MRCC (Kállay), VASP-CC / CP2K for periodic CC.

**Standard workflow:**
1. Run HF to obtain a reference determinant and the canonical orbital set (occupied + virtual).
2. Check multi-reference character: `T₁` diagnostic, NOONs (natural occupation numbers).
3. Run CCSD to convergence (typically ~ 50 iterations); extract `T₁`, `T₂` amplitudes.
4. Apply (T) correction: CCSD(T) adds perturbative triples `O(N⁷)`.
5. Extrapolate to complete basis set (CBS) using two-point (TZ/QZ) extrapolation.

**Verification pointers:**
- `T₁` diagnostic < 0.02 (reliable) vs > 0.02 (suspect, multi-reference check needed).
- Energy converged in basis set: compare DZ, TZ, QZ energies; CBS extrapolation.
- Compare CCSD vs CCSD(T): large (T) correction signals strong correlation warning.

**Cross-links:**
- Survey: `method-survey.md` §6.5 (coupled cluster)
- Model↔method gate: `method-property-map.md`
- Complementary: DMET (§6.2, wave-F card — CCSD as embedded solver); MBPT-GW (§6.6, wave-F card — perturbative alternative for solids); `/method-ed` (FCI limit and benchmark for small systems); `/method-mf` (HF reference)
