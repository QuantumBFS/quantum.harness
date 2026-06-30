<!-- Method-card template. Axis definitions: ../method-property-checklist.md (M1–M14).
     Inverse model→method map: ../method-property-map.md. Cost derivations & citations:
     ../method-survey.md. Cite keys resolve in ../ref.bib. -->

# Cluster Mean Field / Variational Cluster Approximation (Potthoff SFT) (VCA / cluster-MF)

Treats short-range correlations exactly inside small clusters via an exact diagonalization solver, couples clusters by a mean field (cluster MF) or by Potthoff's self-energy functional theory (VCA), and recovers spectral functions and symmetry-breaking order parameters in 2D correlated systems.

## Method card

### What it is

Cluster mean field (CMF) and the variational cluster approximation (VCA) partition the lattice into identical finite clusters, solve each cluster exactly (ED), and couple the clusters together. In the simpler CMF, inter-cluster hopping is decoupled at mean-field level. In VCA (Potthoff's self-energy functional theory, SFT), the inter-cluster coupling is handled via a variational principle for the grand potential expressed as a functional of the cluster self-energy; optimizing over cluster parameters (Weiss fields, chemical potential) yields the best approximation to the lattice self-energy at no additional cost beyond ED. The method returns the lattice Green's function, spectral functions, and phase boundaries in 2D correlated models; the approximation is controlled by cluster size.

### Properties (M1–M14)

| Axis | Value | Note |
|---|---|---|
| M1 tasks / outputs | Spectral functions `A(k,ω)` / `A(ω)` · phase boundaries (Mott transition, magnetic / superconducting order) · symmetry-breaking order parameters · single-particle Green's function | VCA gives the full lattice spectral function via the periodized cluster self-energy; CMF gives order parameters and phase diagrams. |
| M2 regime | T=0 (finite-T via thermal cluster Green's function straightforward) | The cluster ED solver is zero-temperature by default; finite-T extensions use finite-T ED (FTLM/TPQ) inside the cluster. |
| M3 accuracy class | Controlled by cluster size `N_c` (systematic improvement) | Adding sites to the cluster systematically reduces the inter-cluster mean-field error; exact in the limit `N_c → ∞`. |
| M4 dimension fit (A1) | 2D (primary target); quasi-1D ladders | Designed for 2D correlated lattice models (Hubbard, t-J, periodic Anderson); inter-cluster MF less accurate in 1D where fluctuations dominate. |
| M5 statistics & local dim (A3) | Fermions, spins, hard-core bosons; local dim `d` enters through the ED cluster cost `d^{N_c}` | Same `d^N` exponential wall as ED, restricted to the cluster; typical `d=2–4` (spin-½ to Hubbard). |
| M6 entanglement regime (B5) | Within-cluster entanglement: exact (full ED Hilbert space); inter-cluster entanglement: mean-field / neglected | Short-range entanglement captured exactly; long-range inter-cluster entanglement suppressed by the MF decoupling. |
| M7 sign-problem dependence (C12) | Sign-immune (ED cluster solver, no Monte Carlo) | Deterministic; no sign problem regardless of frustration or doping level. |
| M8 symmetry exploitation (C9/C10) | Cluster point-group and translation symmetry block-diagonalize the ED step; lattice translation used to periodize the self-energy (`k`-resolved spectral functions) | C9 symmetry reduces cluster ED cost significantly; periodization of the cluster self-energy restores approximate lattice momentum resolution. |
| M9 time complexity | Dominated by exact cluster ED: `O(d^{3N_c})` (full diagonalization) or `O(n_iter · N · d^{N_c})` (Lanczos); inter-cluster coupling `O(N_c²)` per self-consistency step — cheap | Cost is exponential in cluster size `N_c`; the inter-cluster part adds negligible overhead. Typical cluster sizes `N_c = 4–16` sites. |
| M10 memory | `O(d^{2N_c})` for cluster ED (full) or `O(d^{N_c})` for Lanczos; lattice Green's function `O(N_c² · N_ω)` | Memory limit set by cluster ED, not the lattice size. |
| M11 control knob | Cluster size `N_c` — larger clusters reduce inter-cluster MF error systematically | No statistical error; convergence checked by increasing `N_c` (e.g. 2×2 → 2×3 → 2×4 tiling). |
| M12 scale frontier | Cluster: up to `N_c ~ 12–20` sites (ED wall); lattice: thermodynamic limit reached by the mean-field coupling of an infinite tiling | The lattice itself can be infinite (thermodynamic limit); only the cluster is size-limited. |
| M13 primary approximation / bias | Neglect of inter-cluster quantum fluctuations / entanglement (replaced by MF or the VCA self-energy functional saddle point) | Controlled: bias decreases systematically with `N_c`. For small clusters, inter-cluster fluctuations can be large (especially near quantum criticality). |
| M14 hard blocker / failure mode | Exponential ED cost limits clusters to `N_c ≲ 20` sites; inter-cluster MF becomes unreliable near quantum critical points where correlations are long-ranged; 3D is impractical (too many inequivalent bonds to tile) | Not a thermodynamic-limit method for the cluster solver; accuracy plateau at small `N_c` if cluster geometry cannot capture the relevant correlations. |

### Cost & scaling

- Time: `O(d^{3N_c})` (full ED) or `O(n_iter · N · d^{N_c})` (Lanczos) per cluster; inter-cluster steps negligible
- Memory: `O(d^{2N_c})` (full ED) or `O(d^{N_c})` (Lanczos)
- Control knob: cluster size `N_c`; systematic improvement, no error bar (deterministic)
- Scale frontier: cluster `N_c ≲ 20`; lattice thermodynamic limit

### Accuracy & guarantees

- Class: controlled by `N_c` (deterministic, no statistical error)
- Primary approximation & its control: inter-cluster mean-field decoupling; bias decreases monotonically with `N_c` → exact as `N_c → ∞`
- Error scaling: no closed-form formula; empirically `O(1/N_c)` for smooth observables; convergence verified by increasing `N_c`

### Tasks it computes

- Single-particle spectral function `A(k,ω)` and local density of states `A(ω)` (VCA periodization)
- Mott metal-insulator phase boundary as a function of `U/t` and filling
- Symmetry-breaking order parameters: antiferromagnetic moment, d-wave superconducting order parameter, CDW amplitude
- Phase diagrams in the `U`–`T`, `U`–`n` plane for Hubbard-type models
- Self-energy `Σ(k,ω)` reconstructed from the cluster (VCA/SFT)

### Recommended for (models / regimes)

- **2D Hubbard model:** Mott transition, pseudogap, antiferromagnetic and d-wave superconducting phases — primary target
- **Frustrated 2D magnets:** kagome / triangular Heisenberg with sign-immune solver; resolves short-range order
- **Doped Mott insulators:** `t`-`J` model, correlated electron systems at finite hole doping where DQMC has a sign problem
- **Spectral properties:** spectral functions and quasiparticle weights inaccessible to plain MF or QMC (analytic continuation issues)
- Per `method-property-map.md`: preferred when A1 = 2D, B7 Mott physics, C12 sign-ful (doped / frustrated), and spectral resolution is needed

### Key reference

[@maier_2004_quantum] — comprehensive review of quantum cluster approaches (DCA, CDMFT, VCA) covering the theoretical foundations, self-energy functional theory, cluster-size convergence, and applications to correlated electron models; the authoritative all-details source.
Rendered: `./cond-mat-0404055_quantum-cluster-theories.md` _(downloaded)_.

### Benchmarks

- VCA d-wave order parameter in the 2D Hubbard model (`U=8t`, `n=0.875`): `Δ_d ≈ 0.05–0.08t` for `N_c = 4`–`8` clusters, consistent with CDMFT and DCA [@maier_2004_quantum].
- Mott transition `U_c/t ≈ 6–8` (2D square lattice, half filling) converges with cluster size; `N_c = 4` gives `U_c ≈ 6.5t`, approaching the DCA/CDMFT consensus [@maier_2004_quantum].
- Cluster-size convergence verified in `method-survey.md` §7.4.

## How it is used / Operational

**Owning skill:** `/method-mf` (cluster mean-field route; note the cluster solver is ED).

**Default workflow:**
1. Choose the cluster geometry and size `N_c` (e.g. 2×2, 2×3, or 4-site plaquette) consistent with the expected order (d-wave SC → 4-site; AF → 2×2 or larger).
2. Set up the cluster Hamiltonian with Weiss fields (CMF) or variational cluster parameters (VCA/SFT).
3. Solve the cluster exactly by ED (full or Lanczos); compute the cluster Green's function `G_c(ω)` and self-energy `Σ_c(ω)`.
4. VCA: minimize the SFT grand potential `Ω[Σ_c]` over the Weiss-field / cluster-parameter space to determine the optimal cluster parameters.
5. CMF: update the inter-cluster mean fields self-consistently until convergence.
6. Extract the lattice spectral function via periodization of `Σ_c(k,ω)` → `A(k,ω)` and order parameters.
7. Repeat for `N_c → N_c + \delta` (e.g. increase cluster by 2–4 sites) to check convergence.

**Verification pointers:**
- Check convergence of the order parameter and spectral gap with `N_c`.
- Compare phase boundaries against DQMC (sign-free points: half-filling, particle-hole symmetric) or CDMFT (DMFT cluster limit).
- Verify the self-energy sum rule: `∫ dω A(k,ω) = 1` for each `k`.

**Cross-links:**
- Survey: `method-survey.md` §7.4 (Cluster mean field / VCA)
- Model↔method gate: `method-property-map.md` (VCA/cluster-MF profile, 2D / B7 / C12 rows)
- Complementary methods: DMFT/CDMFT (dynamical correlations, all-k self-energy; cluster limit equivalent to CDMFT at `N_c → ∞`), DQMC (sign-free benchmark at half-filling), DMRG (1D / narrow cylinder benchmarks for spectral functions)
