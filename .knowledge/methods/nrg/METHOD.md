<!-- Method-card template. Axis definitions: ../method-property-checklist.md (M1–M14).
     Inverse model→method map: ../method-property-map.md. Cost derivations & citations:
     ../method-survey.md. Cite keys resolve in ./ref.bib. -->

# Numerical Renormalization Group (NRG)

Wilson's iterative scheme that logarithmically discretizes the conduction-bath, maps the impurity to a semi-infinite chain, and diagonalizes shell by shell, yielding exponentially resolved low-energy physics for quantum impurity problems.

## Method card

### What it is

NRG (Wilson 1975) starts from a quantum impurity (Anderson or Kondo model) coupled to a continuous bath. The bath spectrum is logarithmically discretized with parameter `Λ > 1`, mapped to a semi-infinite tight-binding chain with exponentially decaying hoppings `t_n ∝ Λ^{-n/2}`, and diagonalized shell by shell. At each NRG iteration, a new bath site is added, the Hamiltonian is diagonalized exactly, and only the `N_kept` lowest-lying states are retained (energy truncation). The exponential separation of energy scales in the bath hopping `t_n` means each shell probes a factor `Λ` lower energy than the previous, giving access to the Kondo scale `T_K` and all low-energy fixed points. Spectral functions are reconstructed from the full density-matrix NRG (fdm-NRG) or traditional "patching" approach.

### Properties (M1–M14)

| Axis | Value | Note |
|---|---|---|
| M1 tasks / outputs | Kondo scale `T_K` · impurity spectral function `A(ω)` at all `T` · thermodynamics (entropy, specific heat, susceptibility as function of `T`) · fixed-point flow diagrams · real-frequency self-energy `Σ(ω)` as a DMFT solver | NRG gives real-frequency quantities directly without analytic continuation — its key advantage over CT-QMC. |
| M2 regime | All `T` (T=0 to high-T crossovers) and real-frequency | The logarithmic bath discretization gives exponential energy resolution; no imaginary-time or analytic continuation needed. |
| M3 accuracy class | Controlled (convergence in `N_kept` and `Λ→1`); deterministic | Energy truncation at `N_kept` introduces a controlled systematic error; `Λ→1` is the continuum limit but raises cost. |
| M4 dimension fit (A1) | Impurity / quantum-dot problems (0D impurity + bath) — not a bulk lattice method | Designed for impurity models (Anderson, Kondo, multi-channel, SU(N) Kondo); used as the DMFT impurity solver to access real-frequency self-energies. |
| M5 statistics & local dim (A3) | Fermions (and bosons via bosonic NRG); **`N_kept` must grow exponentially with #bands/channels** | Limited to ~1–3 channels; multi-channel NRG requires exponentially larger `N_kept` → rapidly intractable. |
| M6 entanglement regime (B5) | No entanglement wall for impurity problems (the bath is sequentially integrated out) | Wilson chain geometry makes the entanglement growth manageable by construction. |
| M7 sign-problem dependence (C12) | Sign-immune | Not a Monte Carlo method; exact iterative diagonalization with energy truncation. |
| M8 symmetry exploitation (C9/C10) | U(1), SU(2), Z₂, and non-Abelian symmetries exploited at each iteration to block-diagonalize and reduce `N_kept` required | Symmetry is crucial: SU(2) spin + U(1) charge reduce cost by an order of magnitude; non-Abelian NRG (Weichselbaum) extends reach to multi-channel. |
| M9 time complexity | `O(N_kept³)` per NRG iteration (diagonalize a `≈ d·N_kept` matrix, truncate to `N_kept`); `N_kept` must grow **exponentially with #bands/channels** | Typically ~50–100 iterations for Λ~2–3; total cost `~N_iter × (d·N_kept)³`. |
| M10 memory | `O(N_kept²)` per shell for the density matrix and kept states | Memory manageable for 1–2 channel problems; grows quickly with #channels. |
| M11 control knob | `N_kept` (retained states per shell) — controls energy truncation error; `Λ` (discretization parameter) — controls bath discretization error (`Λ→1` is continuum) | Both knobs must be converged; typical `Λ~2–4`, `N_kept~500–3000` with full symmetry. |
| M12 scale frontier | 1–3 channel impurity problems; single- and two-impurity systems; multi-orbital impurities with symmetry | At 3+ channels without high symmetry: `N_kept` requirement becomes exponentially prohibitive. |
| M13 primary approximation / bias | Energy truncation at `N_kept` (controlled); logarithmic bath discretization with Λ (controlled, `Λ→1` limit) | Both errors are systematically reducible; the truncation error is the leading one at fixed `Λ`. |
| M14 hard blocker / failure mode | **#channels/bands is the wall**: `N_kept` must grow **exponentially with #bands/channels** — NRG limited to ~1–3 channels; not applicable to bulk lattice problems | Bosonic baths with sub-ohmic spectral density can cause issues; high-frequency resolution limited by `Λ`. |

### Cost & scaling

- Time: `O(N_kept³)` per NRG iteration; `N_kept` grows **exponentially with #channels**; ~50–100 iterations total
- Memory: `O(N_kept²)` per shell; manageable for 1–2 channels with symmetry
- Control knob: `N_kept` (truncation error) and `Λ` (discretization error, `Λ→1` is the continuum limit)
- Scale frontier: 1–3 channel impurity problems; quantum dots; DMFT impurity solver for real-frequency self-energies

### Accuracy & guarantees

- Class: controlled, deterministic (in `N_kept` and `Λ`)
- Primary approximation & its control: energy truncation at `N_kept` (systematic); logarithmic bath discretization `Λ` (systematic, `Λ→1`)
- Error scaling: truncation error decreases with `N_kept`; discretization error `∝(Λ-1)` in the `Λ→1` limit

### Tasks it computes

- Kondo temperature `T_K` and Kondo crossover physics
- Impurity spectral function `A(ω)` at all temperatures, real-frequency (no analytic continuation)
- Thermodynamic properties as function of `T`: entropy `S(T)`, specific heat `C(T)`, magnetic susceptibility `χ(T)`
- Fixed-point flow diagrams and crossover between RG fixed points
- Real-frequency self-energy `Σ(ω)` for use as DMFT impurity solver (real-frequency DMFT)

### Recommended for (models / regimes)

- **Anderson and Kondo impurity models** — the definitive solver for all `T` and real-frequency
- **Quantum-dot transport** where Kondo resonance and real-frequency spectral features matter
- **DMFT impurity solver** when real-frequency self-energies are needed without analytic continuation
- **Multi-channel Kondo** up to ~2–3 channels with non-Abelian symmetry
- Per `method-property-map.md`: the method of choice for 0D impurity problems (A1=0D) whenever real-frequency or all-T data is required

### Key reference

[@bulla_2007_numerical] — comprehensive review of NRG theory, algorithms (including fdm-NRG), thermodynamics, spectral functions, and applications to Anderson/Kondo models.
Rendered: `../../literature/anderson-impurity/cond-mat-0701105_numerical-renormalization-group-method-for-quantum-impurity.md` _(reused: `../../literature/anderson-impurity/cond-mat-0701105_numerical-renormalization-group-method-for-quantum-impurity.md`)_.

### Benchmarks

- Kondo scale: `T_K/D ~ exp(-π U / 8Γ)` for symmetric Anderson model; reproduced to < 1% with `N_kept~1000`, `Λ~2` [@bulla_2007_numerical].
- Spectral function sum rule: `∫ A(ω) dω = 1`; satisfied to `< 0.1%` in fdm-NRG [method-survey.md §6.3].
- Channel limit: `N_kept` required scales `~d^{N_ch}` with #channels `N_ch`; 3-channel NRG requires `N_kept~10⁴` even with symmetry [method-survey.md §6.3].

## How it is used / Operational

**Harness coverage:** NRG has **no dedicated harness `/method-*` skill**. It is the canonical impurity solver and DMFT back-end for real-frequency self-energies. External codes: NRG Ljubljana (Žitko), SNEG library, QSpace (Weichselbaum) for non-Abelian symmetry.

**Standard workflow:**
1. Set up the impurity model: local levels, Coulomb `U`, hybridization function `Δ(ω)`.
2. Log-discretize `Δ(ω)` with parameter `Λ` (typically 2–4); map to Wilson chain hoppings `t_n`.
3. Iteratively diagonalize shell by shell, keeping `N_kept` lowest states; exploit all available symmetries.
4. Reconstruct spectral function via fdm-NRG (full density matrix at each shell).
5. For DMFT: extract `Σ(ω)` from `A(ω)` via Dyson equation; feed back to DMFT loop.

**Verification pointers:**
- Check `T_K` against analytical formula for the symmetric Anderson model.
- Verify spectral sum rule `∫ A(ω) dω = 1`.
- Converge in both `N_kept` and `Λ` (compare `Λ=2` vs `Λ=3`).

**Cross-links:**
- Survey: `method-survey.md` §6.3 (NRG)
- Model↔method gate: `method-property-map.md`
- Complementary: DMFT (§6.1, wave-F card — NRG as its real-frequency solver); ED-bath solver (§6.1); `/method-ed` for small impurity problems
