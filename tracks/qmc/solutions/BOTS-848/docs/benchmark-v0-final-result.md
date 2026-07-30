# Benchmark v0 final submission run

## Outcome

The clean GPU Slurm reproduction at source revision
`557cb896ba55def10c1b34bf9eba122ca30eddb7` passed all 31 focused tests and
all eight Benchmark v0 gates. The `N=6`, `2Q=15` projected NQS gives

`Delta_2 = 0.13168841196509184 +/- 1.414213564891033e-12`

in `e^2/(epsilon*l_B)`. The exact-diagonalization value under the same
pair-only chord convention is `0.13168841196509895`, an absolute discrepancy
of `7.105427357601002e-15`.

## Physics and ansatz

- six fully polarized fermions on the Haldane sphere at `nu=1/3`;
- strict lowest Landau level, `Q=7.5`, `2Q=15`;
- pair interaction `1/(sqrt(Q) * |Omega_i-Omega_j|)`;
- raw total energies omit the uniform background, which cancels in the
  same-`N`, same-`Q` neutral gap;
- one shared width-128 `tanh` random-feature trunk on strict-LLL occupation
  bitstrings;
- exact `L^2` projection with linear `L=0,M=0` and `L=2,M=0` heads;
- the complete `L=2` tower is generated from the shared `M=0` head by
  angular-momentum ladder operators.

## Energies and statistical errors

Every reported component uses 20,000 independent categorical determinant
samples. The total uncertainty is the quadrature sum of the measured MC
standard error and the declared `1e-12` numerical projection floor.

| Quantity | NQS/VMC mean | MC standard error | Total uncertainty | ED |
| --- | ---: | ---: | ---: | ---: |
| `E0` | `3.871634914021250` | `5.0332e-17` | `1.0000000013e-12` | `3.871634914021243` |
| combined `E2` | `4.003323325986342` | `6.7738e-17` | `1.0000000023e-12` | `4.003323325986342` |
| `Delta_2` | `0.13168841196509184` | `8.4391e-17` | `1.4142135649e-12` | `0.13168841196509895` |

Fivefold tower:

| `M` | NQS/VMC energy | MC standard error | Total uncertainty | `<L^2>` |
| ---: | ---: | ---: | ---: | ---: |
| -2 | `4.003323325986342` | `2.2400e-16` | `1.0000000251e-12` | `5.999999999999999` |
| -1 | `4.003323325986341` | `5.5624e-17` | `1.0000000015e-12` | `6.000000000000003` |
| 0 | `4.003323325986340` | `6.1664e-17` | `1.0000000019e-12` | `5.999999999999998` |
| 1 | `4.003323325986342` | `5.9765e-17` | `1.0000000018e-12` | `5.999999999999998` |
| 2 | `4.003323325986343` | `2.3252e-16` | `1.0000000270e-12` | `5.999999999999998` |

## Symmetry and correctness certificate

| Check | Measured value |
| --- | ---: |
| Strict-LLL projection residual | `2.0640e-15` |
| Particle-swap residual | `0` |
| `L=2` ladder residual | `8.8782e-13` |
| Finite random SO(3) rotation residual | `2.8894e-14` |
| Fivefold multiplet splitting | `2.6645e-15` |
| Maximum `L^2` error | `4.3761e-15` |
| Maximum `Var(L^2)` | `4.6879e-26` |
| Maximum imaginary local energy | `3.2296e-17` |

All gates passed: strict LLL, antisymmetry, SO(3) equivariance, spin-2
Casimir, fivefold multiplet, MC error, ED cross-check, and reproducibility.

## Reproduction and provenance

Successful producer job:

- Slurm job `23033264`, `COMPLETED 0:0`;
- `xhcs3/xhhgnormal`, node `e05r03`, one RTX 3080;
- four CPUs, 12 GiB, 46 seconds allocation wall time;
- benchmark runtime `4.331991117447615 s`;
- Python `3.11.15`, NumPy `2.0.2`, SciPy `1.16.3`;
- clean source revision
  `557cb896ba55def10c1b34bf9eba122ca30eddb7`;
- `31 passed in 34.14s`;
- `run.json` SHA-256:
  `62a6d0eec15b34f12563076d9f18b055a6831856009cee1fadfa2c4b7be8298d`;
- stdout SHA-256:
  `8774646815cbe19740c07cc59614526aef6f534d93d8b84b7e211f12347f6192`;
- stderr SHA-256:
  `956c70518ba64f566516d055a51cb9dc8fdc8942ab6340a3660ecd4f57fe8b09`;
- Slurm accounting SHA-256:
  `4b32eda0486cff0ba48f6518fa4c5b903d61b0e5e93907be3a41ae305e611d3f`;
- clean-status SHA-256:
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

The preceding job `23033183` failed in three seconds before tests or physics
because the cluster's old Git rejected `--porcelain=v1`. Revision `557cb89`
replaced it with the compatible `--porcelain`; the failed attempt is not used
as scientific evidence.

The challenge report was rendered independently on Slurm job `23033430`
(`COMPLETED 0:0`, one second) and retrieved to
`tracks/qmc/results/BOTS-848-benchmark-v0-final/report.html`. The offline HTML
SHA-256 is
`cb97ce0b030d79d7a696a9e200b2e20d08166355ad518c445bd34001416d5501`;
the corresponding `report.json` SHA-256 is
`01bd8fd479f53366ad2d82a921a0224c21a481375f6f077da244e1288cc5e39d`.
Both remain in the gitignored results directory as required by the competition
repository convention.

## Claim boundary

This run completes the small-`N` acceptance benchmark and validates the full
symmetry/statistics/reporting pipeline. Exact angular-momentum projection and
Rayleigh-Ritz optimization span the ED-sized target sectors, so this result is
not evidence of beyond-ED scaling. The separate Route D+ implementation is the
scalable research route and is reported with its current optimization-failure
diagnosis rather than promoted as a passing accuracy result.
