# Clean 2D Ising transfer-matrix baseline

## Goal

Compute the dominant row-to-row transfer data of the critical square-lattice
Ising model at circumferences `L = 8, 10, 12, 16, 20` without tensor-network
truncation. Use the dominant eigenvalue and an independent QR/power iteration
to recover the largest Lyapunov exponent and fit the clean-Ising central charge
`c = 1/2`.

This is the exact small-width oracle for the later MPO/MPS and random-bond
calculations in challenge #122. It does not materialize the dense transfer
matrix at large `L`: at `L = 20` that matrix would require about 8 TiB in
float64. Instead, its action on the complete `2^L`-component boundary vector
is evaluated exactly and without SVD truncation.

## Fixed setup

- Model: ferromagnetic nearest-neighbor Ising model on the square lattice,
  `J = 1`, `k_B = 1`, zero magnetic field.
- Coupling: isotropic critical point
  `K_x = K_tau = K_c = ln(1 + sqrt(2))/2`.
- Geometry: circumference `L` with periodic boundary conditions; transfer
  direction `M -> infinity`.
- Widths: `L = 8, 10, 12, 16, 20`.
- Arithmetic: float64.
- No MPS, bond-dimension cutoff, Monte Carlo sampling, or disorder in this
  stage.

"Exact contraction in the M direction" means repeated exact action of one
row transfer operator on the full boundary vector, followed by normalization.
The infinite transfer length is taken through the dominant eigenvalue or
Lyapunov limit rather than by forming a finite `T^M`.

## Transfer operator

For row configurations `sigma` and `sigma_prime`, use the symmetric operator

```text
T(sigma_prime, sigma) = exp{
    K_x [E_x(sigma_prime) + E_x(sigma)] / 2
    + K_tau sum_i sigma_prime_i sigma_i
}

E_x(sigma) = sum_i sigma_i sigma_(i+1),  sigma_(L+1) = sigma_1.
```

Apply it matrix-free as

```text
T = D^(1/2) V D^(1/2)
D(sigma) = exp[K_x E_x(sigma)]
V = tensor_product_i v_i
v_i = [[exp(K_tau), exp(-K_tau)],
       [exp(-K_tau), exp(K_tau)]]
```

Each local `v_i` acts on one bit axis of a shape `(2,)*L` tensor. One
application costs `O(L 2^L)` time and `O(2^L)` storage and performs the full
sum over the old row exactly.

## Numerical paths

1. Primary: expose the exact transfer action as a SciPy `LinearOperator` and
   use the symmetric sparse eigensolver for the leading eigenvalues.
2. Independent check: repeatedly apply the same transfer operator, normalize,
   and accumulate log norms. For multiple exponents, propagate a block and QR
   reorthogonalize after every row.
3. Small-width oracle: explicitly construct the dense transfer matrix only for
   `L <= 8` and compare its action and eigenvalues to both matrix-free paths.

Use the unambiguous conventions

```text
ell_a = growth Lyapunov exponent = ln(lambda_a) in the clean model
epsilon_a = transfer energy = -ell_a
```

The central-charge fit uses

```text
epsilon_0(L) = A L + B/L + C/L^3
c = -6 B / pi
```

because the isotropic lattice has anisotropy factor `alpha = 1`. A stability
fit drops `L = 8`; a second stability fit omits the `L^-3` term. The spread is
reported as a finite-size systematic rather than as Monte Carlo uncertainty.

## Components and artifacts

- `scripts/clean_ising_transfer.py`: transfer action, eigensolver, QR check,
  finite-size fit, CLI, and progress output.
- `scripts/tests/test_clean_ising_transfer.py`: dense-action, eigenvalue, and
  Lyapunov consistency tests at small `L`.
- `results/clean_ising_transfer/values.csv`: one row per circumference with
  eigenvalues, exponents, residuals, and runtime.
- `results/clean_ising_transfer/fit.json`: fit parameters and stability fits.
- `results/clean_ising_transfer/central_charge_fit.png`: reduced free energy
  against `1/L^2`, with the fitted Casimir term.

The runnable command will be

```text
python scripts/clean_ising_transfer.py --sizes 8 10 12 16 20
```

On native Windows the repository environment interpreter is used if present;
otherwise the installed Python/SciPy stack is checked before any run.

## Failure handling and compute budget

- Refuse explicit dense construction above the small-width test limit.
- Estimate the `L = 20` full-vector working set before allocation and abort
  cleanly if available memory is insufficient.
- Check every eigenpair residual and fail the run rather than fit unconverged
  values.
- Normalize every power/QR step and accumulate logarithms to prevent overflow.
- Emit progress after every completed circumference and write `values.csv`
  incrementally so an interruption loses at most one width.
- Expected local footprint is below 1 GB. The expected wall time is below the
  harness's 10-minute local threshold; if a short `L = 20` probe contradicts
  this estimate, stop before the full run and route it to remote compute.

## Verification and acceptance

1. At `L <= 8`, dense and matrix-free transfer actions agree to relative
   tolerance `1e-12`.
2. The leading matrix-free eigenpair has relative residual below `1e-10`.
3. The QR/power estimate of `ell_1` agrees with `ln(lambda_0)` within `1e-8`.
4. The fitted central charge is consistent with `1/2`; the reported precision
   is limited by the variation across the declared finite-size fits.
5. The result includes the plot and exact rerun command required by `/solve`.

## Deferred scope

MPO/MPS compression, bond-dimension extrapolation, random-bond transfer
matrices, Born-rule sampling, Nishimori disorder, and the full random
Lyapunov spectrum are deliberately deferred until this clean exact baseline
passes.
