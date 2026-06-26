<!-- Method-card template. Axis definitions: ../method-property-checklist.md (M1–M14).
     Inverse model→method map: ../method-property-map.md. Cost derivations & citations:
     ../method-survey.md. Cite keys resolve in ../ref.bib. -->

# Many-Body Perturbation Theory: GW, RPA, GF2, SEET (MBPT-GW)

Diagrammatic self-energy and correlation-energy approximations based on screened Coulomb interaction and self-consistent Dyson equations; gives quasiparticle band structures (GW), correlation energies (RPA), and — via SEET embedding — spectra of correlated solids.

## Method card

### What it is

Many-body perturbation theory (MBPT) in the GW/RPA family approximates the self-energy `Σ` and Green's function `G` by a selection of Feynman diagrams in terms of the screened Coulomb interaction `W = ε⁻¹v`. The GW approximation `Σ = iGW` (Hedin 1965) sums all ring diagrams and gives the dominant quasiparticle renormalization of band structures. GW is applied one-shot (`G₀W₀`) or self-consistently (sc-GW, qpGW). RPA (random-phase approximation) is the correlation energy analog: `E_c = ½ Tr[ln(1-vχ₀) + vχ₀]`. GF2 (second-order Green's function) includes the second-order self-energy diagram. SEET (self-energy embedding theory) hybridizes GW/GF2 for the weakly-correlated environment with a high-level solver (DMRG/FCI) for a strongly-correlated subspace — extending GW to correlated solids while retaining quasiparticle spectra.

### Properties (M1–M14)

| Axis | Value | Note |
|---|---|---|
| M1 tasks / outputs | Quasiparticle band structures / photoemission spectra (GW) · quasiparticle gaps and ionization potentials · correlation energies (RPA) · screened interactions `W` · optical spectra (BSE on top of GW) · spectra of correlated solids (SEET) | Direct gap: GW; optical gap: BSE/GW; ground-state energy: RPA; strongly-correlated spectra: SEET. |
| M2 regime | T=0 (standard); finite-T Matsubara GW also implemented | Real-frequency GW via analytic continuation or real-axis contour deformation; imaginary-axis for correlation energies. |
| M3 accuracy class | Uncontrolled perturbative approximation (ring/RPA resummation); self-consistent GW is parameter-free but not systematically improvable to exact, and fails at strong coupling (G₀W₀ also carries a starting-point/DFT-functional bias) | GW sums ring diagrams only — not a controlled order-by-order expansion toward exactness; sc-GW removes starting-point dependence but still misses Mott physics; G₀W₀ inherits the DFT-functional bias of the starting point. |
| M4 dimension fit (A1) | Any dimension (molecules and periodic solids) | GW for molecules (PySCF, TURBOMOLE) and periodic solids (VASP, Abinit, BerkeleyGW); no dimensional restriction. |
| M5 statistics & local dim (A3) | Fermions | Fermionic diagrammatic expansion; `N` is orbital/basis count. |
| M6 entanglement regime (B5) | No entanglement gate (diagrammatic / field-theoretic) | Not a wavefunction method; entanglement is not a controlling parameter. |
| M7 sign-problem dependence (C12) | Sign-immune (deterministic diagrammatic resummation) | No stochastic sampling in standard GW/RPA/GF2; diagrammatic MC variants exist but are non-standard. |
| M8 symmetry exploitation (C9/C10) | `k`-point sampling exploits translation symmetry; point-group symmetry reduces the response function | Periodic GW exploits Bloch symmetry; symmetry-adapted `W` reduces cost. |
| M9 time complexity | **GW `O(N⁴)`** (→ `O(N³)` with factorized `W`); **RPA `O(N⁴)`→`O(N³)`**; **GF2 `O(N⁵)`** in orbital count `N` | Factorized GW (`O(N³)`) uses resolution-of-identity (RI) or density fitting; frequency integration adds `N_ω` factor. |
| M10 memory | `O(N³)` for storing `W(r,r',ω)` or its factored form; `O(N²)` for `G` and `Σ` | Memory scales as orbital count cubed for the full polarizability; RI reduces to `O(N² × N_aux)`. |
| M11 control knob | Starting point (DFT functional for `G₀W₀`) · self-consistency level (`G₀W₀` → qpGW → sc-GW) · basis set size · frequency grid `N_ω` | Self-consistent GW eliminates starting-point dependence at higher cost. |
| M12 scale frontier | ~100–1000 orbitals for GW (periodic: 50–500 bands × `k`-points); ~10⁴ orbitals for local GW | Stochastic GW and low-scaling `O(N³)` algorithms extend to large periodic systems. |
| M13 primary approximation / bias | Diagram truncation (GW = ring resummation; GF2 = 2nd order; higher-order diagrams neglected) | Weak-coupling: controlled; strong coupling (Mott): uncontrolled breakdown. SEET corrects by embedding. |
| M14 hard blocker / failure mode | **Strong correlation out of reach**: GW and RPA break down for Mott insulators, strongly-frustrated systems, and near-degenerate open shells (SEET partially fixes this by embedding) | `G₀W₀` starting-point dependence is large for strongly-correlated systems; self-consistent GW still misses Mott physics. |

### Cost & scaling

- Time: **GW `O(N⁴)`** (→ `O(N³)` factorized); **RPA `O(N⁴)`→`O(N³)`**; **GF2 `O(N⁵)`** in orbital count `N`
- Memory: `O(N³)` for full polarizability; `O(N² × N_aux)` for RI-approximated `W`
- Control knob: self-consistency level (G₀W₀ → sc-GW); basis set; frequency grid `N_ω`
- Scale frontier: ~100–1000 orbitals for GW; periodic GW with 50–500 bands

### Accuracy & guarantees

- Class: uncontrolled perturbative approximation (GW = ring/RPA resummation, not systematically improvable to exact); deterministic; starting-point dependent for `G₀W₀`
- Primary approximation & its control: diagram truncation (GW ring sum); self-consistency removes starting-point bias
- Error scaling: `G₀W₀` band gap errors ~0.1–0.3 eV for semiconductors; larger for correlated materials

### Tasks it computes

- Quasiparticle band structures and photoemission spectra (GW); comparison with ARPES
- Fundamental band gaps (GW; systematically better than DFT-LDA/GGA Kohn-Sham gaps)
- Correlation energies and van der Waals interactions (RPA)
- Second-order correlation effects beyond HF (GF2) for molecular systems
- Optical excitation spectra via Bethe–Salpeter equation (BSE) on top of GW
- Spectra of correlated solids with a correlated subspace (SEET)

### Recommended for (models / regimes)

- **Semiconductor and insulator band gaps** (GW is the method of choice for photoemission spectra)
- **van der Waals and dispersion-dominated systems** where RPA correlation energies are essential
- **Quasiparticle renormalization in metals** and correlated metals (beyond DFT)
- **GF2 for molecular quasiparticle spectra** at moderate correlation
- **SEET for correlated solids** where GW fails but pure DFT+U is insufficient
- Per `method-property-map.md`: preferred over DFT (higher accuracy for gaps); restricted to weak–intermediate coupling (strong correlation → DMFT or DMET)

### Key reference

[@golze_2019_gw] — comprehensive practical guide to GW approximation: theory, algorithms (G₀W₀, qpGW, sc-GW), implementations, and benchmarks for molecules and solids.
Rendered: `./10-3389-fchem-2019-00377.md` _(downloaded)_.

### Benchmarks

- GW band gaps of semiconductors: mean absolute error ~0.1 eV (G₀W₀@PBE0) vs ~0.7 eV (DFT-LDA) for the GW100 benchmark set [@golze_2019_gw].
- RPA correlation energies: accurate van der Waals coefficients for rare-gas dimers to < 5% [method-survey.md §6.6].
- G₀W₀@PBE ionization potentials: mean absolute error ≈ 0.3 eV on the GW100 molecular benchmark set (van Setten et al., JCTC 2015) [@golze_2019_gw].

## How it is used / Operational

**Harness coverage:** GW/RPA/MBPT is a quantum-chemistry / condensed-matter perturbative method **outside the current harness skill set**. No dedicated `/method-gw` skill exists. It is not one of the core harness method skills (ED, MPS, PEPS, QMC, VMC, MF, LTRG, MCRG, QCS, PolyOpt).

**External tools:** BerkeleyGW, Abinit, VASP (periodic GW); PySCF, TURBOMOLE, FHI-aims (molecular GW); WEST (stochastic GW).

**Standard workflow (G₀W₀):**
1. Run a DFT calculation (LDA/PBE or hybrid PBE0) to obtain KS orbitals and eigenvalues.
2. Compute the non-interacting response function `χ₀(q,ω)` from the KS orbitals.
3. Build the screened Coulomb interaction `W = (1 - vχ₀)⁻¹ v`.
4. Compute the GW self-energy `Σ(r,r',ω) = iG(r,r',ω)W(r,r',ω)`.
5. Solve the quasiparticle equation `[H_KS + Σ(E_n) - V_xc] ψ_n = E_n ψ_n`.

**Verification pointers:**
- Check band gap convergence with `k`-point sampling and basis size.
- Compare `G₀W₀@PBE` vs `G₀W₀@PBE0` for starting-point sensitivity.
- Verify quasiparticle sum rule: `∫ A(ω) dω = N` (total orbital occupation).

**Cross-links:**
- Survey: `method-survey.md` §6.6 (GW, RPA, GF2, SEET)
- Model↔method gate: `method-property-map.md`
- Complementary: DMFT (§6.1, wave-F card — local self-energy for strongly-correlated solids); coupled-cluster (§6.5, wave-F card — higher-accuracy ground-state energetics); `/method-mf` (HF/DFT starting point)
