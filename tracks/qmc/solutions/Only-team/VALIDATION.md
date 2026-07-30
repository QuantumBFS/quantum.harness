# Small-system reliability record

## Claim

The Julia discrete-imaginary-time cluster Monte Carlo implementation agrees
with exact finite-Trotter calculations for both supported lattices at the
tested small-system parameter point.  This is direct evidence that the
Hamiltonian sign convention, lattice construction, local weight ratio,
ordinary Wolff update, MPI reduction, magnetization moments, and Binder
ratio are mutually consistent.

This establishes reliability at the declared validation point.  It does not
replace the finite-size, finite-temperature, and time-step convergence checks
required for the challenge production calculation.

## Locked validation setup

```text
H = J1 Σ_<i,j> σᶻ_i σᶻ_j − hTrfd Σ_i σˣ_i

J1 = −1
J2 = 0
hTrfd = 4.757
BetaT = 6
Dltau = 0.01
LTrot = 600
periodic spatial and imaginary-time boundaries
```

The triangular calculation used a 3×3 lattice with 9 quantum spins.  The
honeycomb calculation used 2×2 unit cells with 8 quantum spins.  Every QMC
calculation used 28 independent deterministic MPI chains, one local sweep
and five ordinary Wolff updates per update cycle, 6000 warmup cycles, 20
bins, and 2000 measured sweeps per bin.

The reported Binder moment ratio is always

```text
Q = ⟨m²⟩² / ⟨m⁴⟩
```

and was recomputed from the reduced bin moments.

## Exact and QMC results

QMC samples the finite-Trotter ensemble, so its direct correctness target is
the exact finite-Trotter result at the same `Dltau` and `LTrot`.  Quantum ED
is also recorded to expose the remaining Trotter discretization bias.

| Lattice | Method | m² | Binder Q |
|---|---|---:|---:|
| triangular 3×3 | quantum ED | 0.3667170541 | 0.5605049077 |
| triangular 3×3 | exact finite Trotter | 0.3674764417 | 0.5610697506 |
| triangular 3×3 | Julia QMC | 0.3674620811 ± 0.0000848159 | 0.5611331088 ± 0.0000853667 |
| honeycomb 2×2 | quantum ED | 0.1842388365 | 0.3991230054 |
| honeycomb 2×2 | exact finite Trotter | 0.1844172414 | 0.3992335177 |
| honeycomb 2×2 | Julia QMC | 0.1844490874 ± 0.0000497961 | 0.3992679075 ± 0.0000873354 |

Comparison with the exact finite-Trotter values gives:

| Lattice | z(m²) | z(Q) | First/second-half maximum z | Result |
|---|---:|---:|---:|---|
| triangular | 0.169 | 0.742 | 0.887 | Agreement |
| honeycomb | 0.640 | 0.394 | 0.557 | Agreement |

Both observables agree within one standard error on both lattices.  The
first/second-half diagnostics show no resolved drift.

## Trotter bias visible in the exact comparison

| Lattice | Quantity | Exact finite Trotter − quantum ED | Relative shift |
|---|---|---:|---:|
| triangular | m² | +0.0007593876 | +0.20708% |
| triangular | Q | +0.0005648430 | +0.10077% |
| honeycomb | m² | +0.0001784049 | +0.09683% |
| honeycomb | Q | +0.0001105124 | +0.02769% |

The QMC values track the finite-Trotter target rather than accidentally
tracking quantum ED through this nonzero difference.  This is important
evidence that the simulated discrete-time weight is the intended one.

## Verification evidence

- Exact-reference Julia tests: 1677 passing assertions.
- Existing Julia solution tests: 1460 passing assertions, including local
  weight differences, Wolff cluster membership and probabilities,
  measurements, statistics, serial repeatability, and MPI smoke execution.
- Independent validation Python tests: 69 passed.
- Production-integrity audit: 9 saved units, 4 exact rows, eight 20-bin QMC
  outputs, eight sets of 28 distinct rank seeds, and all 9 recorded output
  hashes verified.
- Statistical analysis artifacts reproduced byte-for-byte.

Frozen evidence identifiers:

```text
exact_reference.csv
SHA-256 4ba4d4f8b32adf464b943fbe3fe128f32d5b473092884a9a9229c26e53d7cae7

qmc_summary.csv
SHA-256 7cd6433cbcb6d31ef198b2a60fae6dbd338c555688af24184a15b3e205f0f905

comparison.json
SHA-256 2fd9ab8522b88299867c83fe16c0f7472039353a55af9f8b6495724d0cee7e07
```

## Consequence for challenge production

The validated production path remains:

```text
local Metropolis update
→ ordinary Wolff cluster updates
→ segmented equal-time measurements
→ MPI reduction of m² and m⁴
→ bin-level Binder Q
```

No additional cluster kernel is needed for correctness.  Large-system work
may reuse buffers and remove allocations, provided the update probabilities,
random decisions, measurement definitions, and MPI estimators remain
unchanged and the full validation suite continues to pass.
