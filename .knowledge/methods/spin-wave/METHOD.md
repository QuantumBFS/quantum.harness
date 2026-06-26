<!-- Method-card template. Axis definitions: ../method-property-checklist.md (M1–M14).
     Inverse model→method map: ../method-property-map.md. Cost derivations & citations:
     ../method-survey.md. Cite keys resolve in ../ref.bib. -->

# Linear Spin-Wave Theory (1/S) & Large-N / Large-S (spin-wave)

Semiclassical expansion around a magnetically ordered classical ground state in powers of `1/S`; diagonalizes a Bogoliubov–de Gennes problem to obtain magnon dispersions, dynamical structure factors, and thermodynamic corrections.

## Method card

### What it is

Spin-wave theory (SWT) expands spin operators about a classical ordered state using the Holstein–Primakoff transformation: `S^z = S − a†a`, `S^+ ≈ √(2S) a`, etc. Truncating at quadratic order (linear spin-wave theory, LSWT) yields a Bogoliubov–de Gennes Hamiltonian of size `m×m` (where `m` = number of magnetic sublattices/bands) that is diagonalized at each k-point via a Bogoliubov transformation to obtain magnon frequencies `ω(k)`. Beyond linear order (`1/S` corrections) magnon–magnon interactions and quantum renormalization of order parameters are included. Large-N (Schwinger boson mean field) is the bosonic variant that can access disordered regimes at the saddle-point level. The SpinW Matlab toolbox [@toth_2015_linear] provides a general implementation for arbitrary magnetic structures including incommensurate single-Q order.

### Properties (M1–M14)

| Axis | Value | Note |
|---|---|---|
| M1 tasks / outputs | Magnon dispersions · dynamical structure factor `S(q,ω)` at the harmonic level · sublattice-magnetization `1/S` corrections · thermodynamic quantities (magnon heat capacity, entropy) · neutron scattering cross-sections | `S(q,ω)` from LSWT is directly comparable to neutron scattering data; main experimental touchpoint. |
| M2 regime | T=0 (LSWT); finite-T via Bose–Einstein magnon occupations | Low-T thermodynamics reliable; near `T_N` perturbation theory breaks down. |
| M3 accuracy class | Controlled in `1/S` (semiclassical); deterministic | Large-`S` (A3) is the control parameter; corrections are `O(1/S)` and can be computed systematically. |
| M4 dimension fit (A1) | 2D and 3D ordered magnets; 1D requires caution (strong quantum fluctuations) | In 1D, `1/S` corrections diverge → DMRG/QMC preferred; Mermin–Wagner forbids 2D order at `T>0`. |
| M5 statistics & local dim (A3) | Spins with large `S` (A3); bosons via Holstein–Primakoff | Accuracy improves with `S`; `S=1/2` is borderline (large corrections); `S≥1` reliable at leading order. |
| M6 entanglement regime (B5) | Product-like (ordered classical background + small Gaussian fluctuations) | LSWT wavefunction is a product coherent state with Bogoliubov squeezed-vacuum corrections. |
| M7 sign-problem dependence (C12) | Sign-immune | Deterministic eigenvalue problem; no Monte Carlo. |
| M8 symmetry exploitation (C9/C10) | Magnetic space group (C9) block-diagonalizes the `m×m` BdG matrix; translation (C10) gives k-space formulation | Symmetry reduces the `m×m` problem and labels magnon bands. |
| M9 time complexity | **`O(m³)` per k-point × #k-points** (diagonalization of the `m×m` BdG Hamiltonian) | Cheap — entire magnon band structure computed in seconds to minutes even for large magnetic unit cells. |
| M10 memory | `O(m²)` per k-point (BdG matrix storage) | Negligible. |
| M11 control knob | `1/S` expansion order; `S` magnitude | Higher orders (`1/S²`) give magnon–magnon scattering, lifetime broadening, and order-parameter renormalization. |
| M12 scale frontier | Magnetic unit cells with hundreds of spins feasible (SpinW); no thermodynamic-size wall | Cost grows only as `O(m³×N_k)`; arbitrary system size accessible for ordered phases. |
| M13 primary approximation / bias | **Requires magnetic order** (expands around an ordered classical state); large `S` (A3) is the control parameter | Uncontrolled at `S=1/2` in frustrated systems; `1/S` corrections blow up → signal of disorder / spin liquid. |
| M14 hard blocker / failure mode | B8 frustration / small `S` → `1/S` corrections blow up (breakdown is itself the diagnostic signal of a spin-liquid or disordered ground state); method inapplicable to Mott insulators without order; real-time dynamics require additional approximations | Near quantum-critical points, corrections to LSWT diverge. |

### Cost & scaling

- Time: `O(m³)` per k-point × #k-points (BdG diagonalization); seconds to minutes for any magnetic supercell
- Memory: `O(m²)` per k-point — negligible
- Control knob: `1/S` expansion order; larger `S` → smaller corrections → better controlled
- Scale frontier: no thermodynamic-size wall; arbitrary `N` for ordered phases; `m` (sublattice count) is the only cost driver

### Accuracy & guarantees

- Class: controlled in `1/S`; deterministic
- Primary approximation & its control: harmonic (LSWT) leading order; `1/S` corrections systematically improvable
- Error scaling: LSWT error `~O(1/S)`; exact as `S→∞`; breaks down for `S=1/2` in frustrated (B8) systems

### Tasks it computes

- Magnon dispersion relations `ω(k)` for all branches
- Dynamical structure factor `S(q,ω)` (directly comparable to neutron scattering)
- Sublattice magnetization and its `1/S` quantum corrections
- Magnon density of states and thermodynamic quantities at low T
- Magnon–phonon coupling (extensions)

### Recommended for (models / regimes)

- **Ordered magnets (B7):** Heisenberg model on bipartite or weakly frustrated lattices with `S≥1` — the method of choice
- **Neutron scattering interpretation:** incommensurate magnetic structures, single-Q order, complex magnetic unit cells (SpinW) [@toth_2015_linear]
- **Baseline for frustrated systems:** run LSWT first; if `1/S` corrections are large → suspect spin-liquid ground state → switch to ED/DMRG
- Per `method-property-map.md`: use whenever B7 magnetic order is established and `S` is not too small

### Key reference

[@toth_2015_linear] — SpinW paper: general LSWT algorithm for arbitrary magnetic structures including single-Q incommensurate order; the authoritative implementation reference for neutron scattering applications.
Rendered: `./1402.6069_linear-spin-wave-theory-for-single-q-incommensurate-magnetic-structures.md` _(downloaded)_.

### Benchmarks

- KCuF₃ (S=1/2, 3D AF): LSWT magnon dispersion matches INS to ~5%; `1/S` corrections ~20% of zone-boundary gap.
- MnF₂ (S=5/2, 3D AF): LSWT `<1%` error in magnon frequencies (large-S limit verified).
- `S(q,ω)` from SpinW for incommensurate langasite — verified against neutron data in [@toth_2015_linear].
- Breakdown signal: kagome S=1/2 Heisenberg → `1/S` corrections diverge → confirms spin-liquid candidate (consistent with `method-survey.md` §7.2).

## How it is used / Operational

**Owning skill:** `/method-mf`.

**Default workflow:**
1. Define the magnetic Hamiltonian (exchange tensors `J_ij`, single-ion anisotropy `D`, DM interaction `D_ij`).
2. Minimize the classical energy to find the ordering wave vector `Q` and spin configuration.
3. Apply Holstein–Primakoff + Fourier transform to get the `m×m` BdG Hamiltonian at each `k`.
4. Diagonalize via Bogoliubov transformation (Colpa's algorithm for general BdG matrices).
5. Compute `S(q,ω)` via the dynamical structure factor formula; convolve with instrumental resolution.
6. Compare with neutron scattering or ED benchmarks.

**With SpinW (Matlab):** `spinw` object → `sw_model` / manual spin configuration → `sw.spinwave` → `sw.spinwavestat` → `sw.powspec` for powder averaging.

**Verification pointers:**
- Sum rule: `(1/N) ∑_k ω_k = ⟨S⟩ J_eff` (classical energy sum rule).
- Goldstone check: acoustic magnon branch `ω(Q)→0` for the ordering wavevector.
- Compare sublattice magnetization `⟨S^z⟩ = S − ⟨a†a⟩` with QMC at small S.

**Cross-links:**
- Survey: `method-survey.md` §7.2 (Linear spin-wave theory)
- Model↔method gate: `method-property-map.md` (spin-wave profile)
- Complementary methods: DMRG/ED (exact, for small S and frustrated systems), VMC (variational, can capture spin-liquid physics), slave-particle methods (fractionalized excitations beyond magnons)
