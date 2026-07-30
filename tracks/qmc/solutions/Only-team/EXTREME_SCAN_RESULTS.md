# Challenge extreme-size scan results

This record describes the completed extreme-size scan. It was initially kept
outside Git while verification was in progress and was subsequently included
in verified commit `9048612`. See `CURRENT_STATUS.md` for the latest overall
state.

## Reliability basis

The independent small-system evidence is recorded in `VALIDATION.md`.
For both supported lattices, Julia QMC agreed within one standard error with
the exact finite-Trotter ensemble at the same imaginary-time discretization.
That check covers the Hamiltonian sign, lattice bonds, local and ordinary
Wolff updates, MPI moment reduction, and the definition

```text
Q = <m²>²/<m⁴>.
```

The extreme-size scan below is therefore a production scaling calculation,
not a substitute for the exact small-system check.

## Locked production setup

```text
H = J1 Σ_<i,j> σᶻ_i σᶻ_j − h Σ_i σˣ_i
J1 = −1
J2 = 0
periodic boundaries
BetaT = L/h
FixedDltau = 0.013
nLocal = 1
nWolff = 5
nWarm = 10000
NmBin = 32
NSwep = 2000
NmMeaConfg = 10
32 deterministic MPI chains per cell
```

SCNet jobs:

| Role | Slurm job | Cells | Result |
|---|---:|---:|---|
| minimum sizes | 22988438 | 14 | 14 completed, exit code 0 |
| maximum sizes | 22988447 | 14 | 14 completed, exit code 0 |

The maximum-size cells took 2.00–3.49 hours.  The first eight tasks retained
the original six-hour limit; pending tasks 9–14 were extended to twelve
hours after the first honeycomb timing became available.  No cell approached
either limit.  The largest observed step RSS was about 16.8 GB.

## Minimum-size results

| Lattice | L | h | m² | Binder Q | Wall |
|---|---:|---:|---:|---:|---:|
| triangular | 8 | 4.76511 | 0.158244489 ± 0.000100 | 0.549435837 ± 0.000196 | 1.25 min |
| triangular | 8 | 4.76611 | 0.157718839 ± 0.000081 | 0.548596441 ± 0.000197 | 1.67 min |
| triangular | 8 | 4.76711 | 0.157603536 ± 0.000097 | 0.548286425 ± 0.000197 | 0.97 min |
| triangular | 8 | 4.76811 | 0.157168257 ± 0.000129 | 0.547636634 ± 0.000266 | 1.04 min |
| triangular | 8 | 4.76911 | 0.156807736 ± 0.000110 | 0.547019099 ± 0.000250 | 0.89 min |
| triangular | 8 | 4.77011 | 0.156575998 ± 0.000110 | 0.546604073 ± 0.000240 | 0.90 min |
| triangular | 8 | 4.77111 | 0.156137260 ± 0.000074 | 0.545481498 ± 0.000150 | 0.94 min |
| honeycomb | 10 | 2.12950 | 0.104684454 ± 0.000110 | 0.563947227 ± 0.000370 | 6.80 min |
| honeycomb | 10 | 2.13050 | 0.103324408 ± 0.000110 | 0.560458265 ± 0.000340 | 6.00 min |
| honeycomb | 10 | 2.13150 | 0.101917964 ± 0.000093 | 0.556679690 ± 0.000260 | 5.78 min |
| honeycomb | 10 | 2.13250 | 0.100634017 ± 0.000084 | 0.553593370 ± 0.000250 | 5.62 min |
| honeycomb | 10 | 2.13350 | 0.099492692 ± 0.000086 | 0.550571568 ± 0.000280 | 5.83 min |
| honeycomb | 10 | 2.13450 | 0.098014043 ± 0.000076 | 0.546543936 ± 0.000270 | 5.66 min |
| honeycomb | 10 | 2.13550 | 0.097000279 ± 0.000069 | 0.543904168 ± 0.000240 | 6.20 min |

## Maximum-size results

| Lattice | L | h | m² | Binder Q | Wall |
|---|---:|---:|---:|---:|---:|
| triangular | 48 | 4.76511 | 0.034630966 ± 0.000038 | 0.620894190 ± 0.000387 | 119.94 min |
| triangular | 48 | 4.76611 | 0.033355661 ± 0.000053 | 0.609673202 ± 0.000611 | 162.50 min |
| triangular | 48 | 4.76711 | 0.031927492 ± 0.000053 | 0.596362282 ± 0.000565 | 159.43 min |
| triangular | 48 | 4.76811 | 0.030630874 ± 0.000051 | 0.584485766 ± 0.000550 | 165.20 min |
| triangular | 48 | 4.76911 | 0.029410168 ± 0.000033 | 0.572877782 ± 0.000478 | 162.07 min |
| triangular | 48 | 4.77011 | 0.028122333 ± 0.000046 | 0.560514958 ± 0.000514 | 143.51 min |
| triangular | 48 | 4.77111 | 0.026966931 ± 0.000053 | 0.549451020 ± 0.000596 | 134.73 min |
| honeycomb | 32 | 2.12950 | 0.040115379 ± 0.000060 | 0.617650731 ± 0.000568 | 168.43 min |
| honeycomb | 32 | 2.13050 | 0.037061385 ± 0.000046 | 0.594833433 ± 0.000521 | 192.12 min |
| honeycomb | 32 | 2.13150 | 0.034168008 ± 0.000052 | 0.572243968 ± 0.000576 | 122.47 min |
| honeycomb | 32 | 2.13250 | 0.031515455 ± 0.000060 | 0.551049218 ± 0.000590 | 208.72 min |
| honeycomb | 32 | 2.13350 | 0.028964374 ± 0.000058 | 0.529841516 ± 0.000583 | 134.17 min |
| honeycomb | 32 | 2.13450 | 0.026724188 ± 0.000041 | 0.511311565 ± 0.000428 | 128.55 min |
| honeycomb | 32 | 2.13550 | 0.024536755 ± 0.000042 | 0.492538504 ± 0.000440 | 180.83 min |

## Extreme-size Binder crossings

The diagnostic crossing solves

```text
Q(Lmax,h) − Q(Lmin,h) = 0
```

using a weighted local linear fit.  The quoted uncertainty is only the
statistical covariance of that local fit.

| Lattice | Sizes | Fit fields | Crossing | Fit quality | Interpretation |
|---|---|---|---:|---:|---|
| triangular | 8, 48 | 4.76811–4.77111 | 4.771427 ± 0.000052 | χ²/dof = 2.15/2 | 0.000317 above the scan; mild extrapolation |
| honeycomb | 10, 32 | 2.13050–2.13350 | 2.132363 ± 0.000018 | χ²/dof = 0.32/2 | directly bracketed by 2.13150 and 2.13250 |

These are two-size crossings, not final critical fields.  Finite-size drift,
the fit model across intermediate sizes, and the `Dltau²→0` extrapolation
are not included in the quoted errors.  In particular, the triangular
two-size crossing should not replace the multi-size fit simply because it
lies above the current scan.

## Operational consequence

The current implementation needs no Wolff-buffer or update-rule change to
meet the wall-time constraint: the slowest approved maximum-size cell took
3.49 hours, far below both the original 6-hour first-wave limit and the
30-hour challenge horizon.

The extreme-size data do not yet establish fifth-decimal critical fields.
Their local crossing errors are about `5.2×10⁻⁵` (triangular) and
`1.8×10⁻⁵` (honeycomb), before finite-size and Trotter systematics.  The next
scientific step is the approved intermediate-size grid, followed by the
actual-`Dltau²` extrapolation.  No result is selected because it is closer to
`√5` or because its Binder ratio is closer to `0.5`.

## Integrity evidence and artifacts

- Remote manifests: 14 success, 0 failed.
- Local manifests: 14 success and 14 unique lattice/size/field cells.
- Manifest-declared artifacts: 70/70 SHA-256 hashes verified.
- Final collection: 14 success, 0 failed, 0 missing, 0 pending.
- Slurm maximum-size array: all 14 tasks `COMPLETED`, exit code 0.

Result directories:

```text
tracks/qmc/results/Only-team/challenge-extremes-min-20260729/
tracks/qmc/results/Only-team/challenge-extremes-max-20260729/
```

Key analysis artifacts:

```text
parameter-scan.csv
extreme_size_crossings.csv
extreme_size_crossings.json
extreme_size_crossings.png
extreme_size_crossings.pdf
```

At the scan checkpoint no Git operation was performed. This verified record
was subsequently included in commit `9048612`.
