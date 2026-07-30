# Uncertainty budget

> Status: structure and source map only.

## 1. Hamiltonian approximation

- Exact Hurwitz-zeta coupling minus periodized exponential coupling.
- Distance-resolved and maximum relative errors.
- K=24→32 shifts in Γx, Rξ, and gaps.
- Canonical sources:
  `../results/phase2_tail_stable/` and
  `../results/phase6_sigma1.75/validated-local-reproduction/`.

## 2. MPS truncation and optimization

- χ=128→256 shifts, recorded separately for ground and excited sectors.
- Variance, discarded weight, reached χ, sweeps, and energy/gap shifts.
- Phase 8 protocol amendment: discarded-weight acceptance relaxed to 10⁻⁷;
  variance target remained 10⁻¹⁰.
- Retain the L=128 even-sector diagnostic warning and energy-stability
  evidence.

## 3. Finite-size and critical-field sensitivity

- Limited size ranges for each benchmark.
- σ=7/4 self-consistent versus external-field branches.
- Direct gap scaling and 1/L_eff versus 1/log(L_eff) sensitivity of the
  gap-based pairwise effective dynamical exponents.
- `L_eff=sqrt(L1*L2)` is the DMRG analysis's logarithmic midpoint, not a
  convention attributed to Shiratani–Todo.
- Do not combine these deterministic sensitivities into a statistical error
  bar.

## 4. Observable-definition uncertainty

- Equal-time S_eq(0) is not the zero-frequency susceptibility S(0,0).
- No γ/ν result is accepted from this DMRG workflow.

## 5. Scope exclusions

- No L=256, no global χ=256 or K=32 production, and no σ=0.4 DMRG benchmark.
