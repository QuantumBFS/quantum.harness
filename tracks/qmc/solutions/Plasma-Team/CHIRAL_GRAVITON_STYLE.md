# Chiral Graviton Code and Numerical Style

## 1. Language and layout

- Python 3.12, UTF-8, four spaces, maximum line length 100.
- Public functions and dataclasses require type hints and docstrings.
- Physics symbols use explicit names: `two_q`, `two_lz`, `relative_m`, `pair_j`.
- Generated data goes under `tracks/qmc/results/`; source code stays in the team directory.
- Tests mirror module names and use deterministic seeds.

## 2. Units and quantum numbers

- Energies: `e^2/(epsilon*l_B)` unless a function explicitly states otherwise.
- Lengths: `l_B`.
- Store half-integer labels as doubled integers (`two_q`, `two_m`, `two_lz`).
- Convert to floats only at library boundaries.
- Never infer chirality from the sign of `M`; compute a helicity-resolved metric response.
- State whether the neutralizing-background constant is included. It must not affect a same-`N` gap.

## 3. Numerical precision

- Default real/complex precision: float64/complex128.
- Hermiticity tolerance: `1e-12` for dense unit tests, `1e-10` for sparse production checks.
- SU(2) commutator tolerance: `1e-10` relative Frobenius norm.
- Lanczos eigenpair residual target: `1e-10` or better.
- Assign `L` only when `<L^2>` is within `1e-7` of `L(L+1)`.
- Report digits justified by solver and sampling uncertainty only.

## 4. Symmetry rules

- Fermionic signs come from explicit creation/annihilation ordering; do not patch signs empirically.
- SO(3) constraints are hard constraints or exact projections in the accepted model.
- Penalty-only symmetry training is diagnostic and cannot be the final acceptance path.
- Build the `L=2` multiplet from one highest-weight state with lowering operators when possible.
- Rotation tests must include random axes and angles, not just z-axis phases.

## 5. Testing hierarchy

1. algebraic tests: bit signs, basis sizes, CG orthogonality;
2. operator tests: Hermiticity, SU(2), conserved `Lz`;
3. physics tests: Laughlin `V1` zero mode, `L=2` multiplet;
4. solver tests: residual norms and dense/sparse agreement;
5. NQS tests: ED overlap/energy/gap and symmetry checks;
6. reproducibility tests: fixed-seed output and result schema.

Tests must fail with an explanation naming the violated physical invariant.

## 6. Monte Carlo reporting

Every estimate records raw sample count, seed, mean, standard error, and energy
variance. The current enumerated sampler produces independent draws: burn-in is
zero, integrated autocorrelation is one, and effective sample size equals raw
sample count. If a future Markov-chain sampler is added, it must additionally
record chain count, burn-in, autocorrelation, and effective sample size.

Do not call correlated samples independent. Separate-sector samples use separate
seeds and independent-error propagation; a future paired estimator must retain
the covariance or use bootstrap resampling.

## 7. Configuration style

TOML keys use snake case and carry units in comments. Config files are immutable inputs to a run. The result metadata stores the full resolved configuration, package versions, platform, timestamp, and Git commit when available.

## 8. Error handling

- Raise `ValueError` for invalid physical inputs.
- Raise a project-specific exception for convergence or invariant failures.
- Do not catch broad `Exception` in physics kernels.
- CLI commands translate exceptions into documented exit codes and concise messages.
- A failed invariant prevents result publication and marks the autoresearch iteration for discard.

## 9. Documentation

- Equations in docstrings must define phase and index conventions.
- Each result figure points to its CSV/JSON source.
- Each development node appends its command, outcome, and known limitations to `DEV_DOCUMENT.md`.
- Claims about the Liou et al. paper cite arXiv:1904.12231 or the PRL DOI.

## 10. Commit style

Autoresearch experiments use `experiment: <focused change>`. Normal module commits use `chiral-graviton: <description>`. Commits are local only until the user explicitly approves a push or PR.
