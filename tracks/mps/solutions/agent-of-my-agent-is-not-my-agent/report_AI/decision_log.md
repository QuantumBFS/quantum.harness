# Decision log

> Status: outline with the decisions that the final archive must substantiate.

## Periodic reference Hamiltonian

- Use the pinned finite-ring Hurwitz-zeta image sum, not an open-chain
  power law.

## Production MPO: K=24

- K=24 passed coupling- and observable-level validation.
- K=32 produced only validation-scale shifts at the accepted σ points and was
  therefore retained as a systematic check rather than a production default.

## Production MPS bond dimension

- χ=64 was accepted for exploratory Rξ scans after selective χ=128 checks.
- χ=128 was used for final long-range gap states.
- χ=256 was reserved for targeted failed excited-state gates and uncertainty
  checks rather than global production.

## Critical-field roles

- Finite-size Rξ crossings provide self-consistent DMRG estimates.
- Published Γc values at σ=7/4, σ=1.8, and σ=2/3 are explicitly external
  benchmark fields used to test gap scaling.
- Published fields are not selected because they produce preferred z values.

## Dynamical-exponent estimator

- DMRG estimates `z` from `Delta(L,Gamma_c) ~ L^(-z)`.
- `z_eff(L1,L2)` is the gap-based pairwise effective dynamical exponent, and
  `L_eff=sqrt(L1*L2)` is its logarithmic midpoint convention.
- Shiratani–Todo obtain a QMC finite-size estimator from tuned imaginary-time
  aspect ratios. Only the power/log correction-analysis strategy is compared;
  the underlying estimators are not identified with one another.

## Susceptibility γ/ν

- Equal-time `S_eq(0)=Σ_r C(r,0)` lacks the imaginary-time integral in
  `S(0,0)=Σ_r ∫dτ C(r,τ)`.
- The former is retained only as an auxiliary diagnostic; no susceptibility
  γ/ν is claimed.

## σ=0.4 exclusion

- K=32 did not reduce finite-ring coupling reconstruction error below the
  preregistered ≈1% qualification level at L=64 or 96.
- The DMRG benchmark was not run, preventing an uncontrolled z claim.

## Local-compute scope

- The cluster/L=256 campaign was replaced by a validated local campaign and
  selected calculations through L=128.
- Finite-size sensitivity is consequently reported as the dominant
  limitation.
- All calculations ran on a 32 GB personal computer. User-observed memory was
  normally below 16 GB; recorded per-cell provenance used a 1.3 GiB
  conservative χ=128 bound and a measured 2.66 GiB χ=256 peak.
- No individual DMRG campaign exceeded eight hours. The complete σ=1.8,
  L=16–128 even/odd gap campaign records 6,325 s = 1.76 h of summed DMRG wall
  time.
- The contrast with Shiratani–Todo's L=362 QMC calculation motivates a
  larger-resource DMRG study, but does not establish that DMRG already exceeds
  L=362 at comparable accuracy.
