# Sachdev–Ye–Kitaev (SYK)

`N` Majorana fermions with all-to-all, Gaussian-random four-body couplings and **no lattice geometry whatsoever** — a 0+1-dimensional quantum-mechanical model. It is **solvable in the large-`N` limit** (melonic / Schwinger–Dyson, conformal IR), is a **non-Fermi liquid with no quasiparticles**, is **maximally chaotic** (its Lyapunov exponent saturates the chaos bound `λ_L = 2πk_BT/ℏ`), carries an **extensive zero-temperature entropy**, and is **holographically dual** to near-extremal (AdS₂) black holes / JT gravity. The standard testbed for strange-metal and quantum-gravity physics.

## Physics card

### Hamiltonian

$$ H = \sum_{i<j<k<l} J_{ijkl}\, \chi_i \chi_j \chi_k \chi_l, \qquad \overline{J_{ijkl}} = 0,\quad \overline{J_{ijkl}^2} = \frac{3!\,J^2}{N^3} $$

Conventions: `N` Majorana fermions `χ_i` with `\{\chi_i,\chi_j\} = \delta_{ij}`; the couplings `J_{ijkl}` are independent zero-mean Gaussian random variables with variance `\overline{J_{ijkl}^2} = 3!\,J^2/N^3` (the `1/N^3` scaling makes the large-`N` limit well defined, with `J` the single energy scale). This is the `q = 4` model; the general `q`-body SYK replaces the quartic term with a `q`-fermion coupling. A complex-fermion variant uses Dirac fermions `c_i` with random `c^\dagger c^\dagger c c` couplings (then a U(1) charge appears). **There is no spatial structure** — every fermion couples to every other (all-to-all). See `.knowledge/conventions.md`.

### Properties (A1–D16)

| Axis | Value | Note |
|---|---|---|
| A1 dimension & geometry | **0+1-dimensional (quantum mechanics); no lattice, no geometry** — all-to-all coupling among `N` Majoranas | There is no notion of position, distance, or dimension; "geometry" is the complete graph on `N` sites. |
| A2 boundary conditions | N/A — no lattice, hence no boundary conditions | A single quantum-mechanical degree-of-freedom cluster of `N` Majoranas. |
| A3 statistics & local dim | Majorana fermions (`χ_i`); `N` Majoranas → Hilbert dimension `2^{N/2}` (complex-fermion variant: Dirac fermions, `d = 2` per mode) | Pairs of Majoranas form a qubit, so `N` Majoranas span `2^{N/2}` states — the ED wall. |
| A4 interaction range | **all-to-all (infinite-range), 4-body random** — the opposite extreme of short-range | Every quartet `(i,j,k,l)` interacts; this infinite-range randomness is what enables the melonic large-`N` solution. |
| B5 entanglement scaling | volume-law (eigenstates are highly entangled; the thermofield-double / ground state has near-maximal entanglement) | No spatial area law (no geometry); tensor-network methods do not apply. |
| B6 spectral gap | gapless / **no quasiparticles**; conformal (scale-invariant) IR with a continuum of excitations | The IR is governed by a conformal Green's function, not by particle-like poles — a non-Fermi liquid. |
| B7 ground-state order | **non-Fermi liquid / strange metal**: conformal IR, no quasiparticles, extensive `T→0` entropy; holographically dual to AdS₂ / near-extremal black holes | No symmetry-breaking order parameter; characterized by the conformal exponents, the chaos rate, and the residual entropy. |
| B8 frustration | disorder-induced (the random all-to-all couplings produce a frustrated, glass-free but highly entangled landscape) | The randomness, not geometry, drives the complexity; the model is a non-glassy quantum liquid. |
| C9 global symmetry | Majorana version: fermion parity `Z_2` only (no charge) · complex-fermion version: U(1) charge | Disorder average restores statistical homogeneity; individual realizations have only parity (or U(1)). |
| C10 spatial symmetry | N/A — no lattice; large-`N` replica / `O(N)` structure after disorder averaging | No translation or point group; the relevant structure is the replica-diagonal `G`–`Σ` bilocal field. |
| C11 integrability | **solvable in the large-`N` limit** (melonic dominance → Schwinger–Dyson equations, conformal IR); finite-`N` is non-integrable / chaotic → ED | Large `N`: closed `G`–`Σ` equations. Finite `N`: fully chaotic (random-matrix level statistics), requires exact diagonalization. |
| C12 sign problem | N/A in the large-`N` (analytic) solution; finite-`N` studied by ED (no Monte Carlo). Real-time / many-replica numerics can be sign-ful | The standard route is analytic large-`N` + finite-`N` ED, not QMC. |
| D13 regime | finite temperature (conformal IR, free energy, entropy) and real-time **chaos / dynamics** (OTOC, spectral form factor) are the focus; ground state for the residual entropy | The chaos, scrambling, and thermodynamics — not a ground-state energy — are the headline targets. |
| D14 filling / doping | Majorana version: half-filling fixed by particle–hole structure · complex-fermion version: charge `Q` is a tuning parameter (compressibility) | Filling matters only in the complex-fermion (charged) variant. |
| D15 disorder | **quenched disorder is intrinsic** — the random couplings `J_{ijkl}`; physical quantities are **disorder-averaged** (self-averaging at large `N`) | The disorder average is part of the model definition, not an optional complication; it is what produces the `O(N)`/replica structure. |
| D16 hermiticity | Hermitian / closed | Non-Hermitian and Lindbladian SYK are studied extensions. |

### Phases & order parameters

- Non-Fermi-liquid / conformal "strange metal" phase : no order parameter. Diagnostics are the conformal fermion dimension `Δ = 1/q` (`= 1/4` for `q = 4`), the maximal Lyapunov exponent, and the extensive residual entropy.
- (Coupled-SYK / complex-SYK extensions) : a low-temperature crossover to a Fermi-liquid or a wormhole/gapped phase, diagnosed by the same conformal-vs-gapped Green's function.

### Canonical observables

- Disorder-averaged two-point function `G(τ) = \overline{⟨T\chi_i(τ)\chi_i(0)⟩}` and its conformal IR form (fermion dimension `Δ = 1/q`).
- Free energy, entropy, and the **extensive zero-temperature entropy** `S_0 = N s_0`.
- Out-of-time-order correlator (OTOC) → Lyapunov exponent `λ_L` (chaos / scrambling).
- Spectral form factor and level statistics (random-matrix / ramp-plateau structure) at finite `N`.

### Recommended methods

- Primary: **large-`N` Schwinger–Dyson (melonic) equations** — the disorder-averaged `G`–`Σ` self-consistent equations solved numerically (iteration on the imaginary-time grid) give the Green's function, free energy, entropy, and conformal exponents. Analytic / numerical-saddle, not a harness lattice solver.
- Cross-check: **ED** at finite `N` (build the `2^{N/2}` Majorana Hamiltonian for one or many disorder realizations, diagonalize, average) — gives the spectral form factor, level statistics, OTOC, and entropy, and tests the approach to the large-`N` predictions, per `method-property-map.md` ED row (volume-law, small `N`).

### Key reference

[@chowdhury_2021_sachdev] — Chowdhury, Georges, Parcollet & Sachdev, "Sachdev-Ye-Kitaev models and beyond: Window into non-Fermi liquids" (RMP 94, 035004, 2022): the authoritative downloadable all-details review covering the model definition, the large-`N` melonic / Schwinger–Dyson solution, the conformal IR, maximal chaos, the residual entropy, finite-`N` numerics, the holographic dual, and the connections to strange metals.
Rendered: `./2109.05037_sachdev-ye-kitaev-models-and-beyond-window-into-non-fermi-li.md`.

### Benchmarks

- Maximal chaos: the Lyapunov exponent saturates the chaos bound, `λ_L = 2πk_BT/ℏ` (Eq. 12.52 of the review; the bound `λ_L ≤ 2πk_BT/ℏ` is conjectured for all strongly-interacting systems) — [@chowdhury_2021_sachdev].
- Conformal fermion dimension: `Δ = 1/q = 1/4` for the `q = 4` model (the IR Green's function `G(τ) ∝ \mathrm{sgn}(τ)/|τ|^{2Δ}`) — [@chowdhury_2021_sachdev].
- Extensive zero-temperature entropy: `S_0/N = s_0 ≈ 0.2324\,k_B` per fermion for the `q = 4` Majorana model (Kitaev; Maldacena–Stanford) — a non-Fermi-liquid hallmark, reviewed in [@chowdhury_2021_sachdev].

## How it is studied

SYK is not run as a harness lattice solver — it is a **0+1-dimensional, all-to-all, disordered quantum-mechanical model** analyzed by a combination of large-`N` field theory and finite-`N` exact diagonalization with disorder averaging.

- **Large-`N` melonic / Schwinger–Dyson.** After averaging over the Gaussian couplings, the `1/N^3` variance makes only the "melon" Feynman diagrams survive at large `N`. The theory closes into a pair of self-consistent equations for the disorder-averaged Green's function `G(τ)` and self-energy `Σ(τ)`: `Σ(τ) = J^2 G(τ)^{q-1}` together with the Dyson equation. Solving these (analytically in the conformal IR, numerically by iteration on the imaginary-time grid) gives the non-Fermi-liquid Green's function, the conformal fermion dimension `Δ = 1/q`, the free energy, and the extensive `T→0` entropy.
- **Conformal IR and holography.** At low energies the equations have an emergent (re)parameterization symmetry softly broken to `SL(2,R)`; the resulting Schwarzian effective action is identical to that of JT gravity on AdS₂, making SYK holographically dual to a near-extremal black hole. The residual entropy `S_0` is the lattice analog of the Bekenstein–Hawking entropy.
- **Maximal chaos.** The out-of-time-order correlator grows as `e^{λ_L t}` with `λ_L = 2πk_BT/ℏ` — saturating the universal chaos bound. This (and the linear-in-`T` specific heat) is what makes SYK a controlled model of a strange metal.
- **Finite-`N` exact diagonalization.** Because there is no large-`N` simplification at finite `N`, the model is studied by constructing the `2^{N/2}`-dimensional Majorana Hamiltonian for many random realizations of `J_{ijkl}`, diagonalizing, and **averaging over disorder**. This yields the spectral form factor (the random-matrix "ramp" and "plateau"), level-spacing statistics (matching GOE/GUE/GSE depending on `N mod 8`), the OTOC, and the entropy — and tests the approach to the large-`N` conformal results as `N` grows.

When SYK appears inside a calculation it is usually as (i) a solvable model of a non-Fermi liquid / strange metal, (ii) a tractable holographic dual for studying black-hole thermodynamics and scrambling, or (iii) a maximally-chaotic benchmark for spectral-form-factor and OTOC diagnostics.
