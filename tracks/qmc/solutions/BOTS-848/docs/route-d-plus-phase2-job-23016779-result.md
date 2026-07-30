# Route D+ Phase 2 job 23016779 result

## Outcome

Slurm job `23016779` completed the Route D+ Phase 2 gate on one V100. Ruff
passed, all ten scoped tests passed, the certificate reported `passed: true`,
and an independent remote schema and threshold check succeeded.

## Identity and resources

- Code revision: `e39ed7bd89b3579aafb1630370be6f464d6fe0eb`
- Run ID: `route-d-plus-phase2-20260730-03`
- Cluster and partition: `xhcs3`, `xhhgnormal02`
- Node and accelerator: `v01r03`, one V100 16 GiB
- Allocation: two CPUs, 6 GiB memory
- Slurm state: `COMPLETED`, exit code `0:0`
- Runtime: 43 seconds

The pinned Phase 1 manifest SHA-256 was
`eabc1a4d3fae12e2fbbe7f54813acb83102495bd6004b7ab30b390d9b6cdecc6`.

## Software gates

The remote stdout contained:

```text
All checks passed!
..........                                                               [100%]
10 passed in 24.19s
```

An additional remote validation loaded the committed Phase 2 schema and
certificate with the pinned Python 3.11 environment, ran
`jsonschema.validate`, asserted `passed is True`, and asserted that every
reported error was smaller than the certificate tolerance. It returned:

```text
schema_valid=true errors_below_tolerance=true
```

## Numerical certificate

The fixed instance used `2Q = 15`, 16 orbitals, and a
Gauss-Legendre-times-uniform-Fourier quadrature with 34 polar nodes, 64
azimuthal nodes, and 2176 total points.

| Metric | Maximum error |
| --- | ---: |
| Spinor norm | `4.440892098500626e-16` |
| Orbital overlap | `8.770762097149434e-15` |
| Kernel versus orbital sum | `4.222133058685889e-15` |
| Off-grid orbital reconstruction | `5.3549022725897734e-15` |

Every value is below the fixed strict tolerance of `1e-12`.

## Pinned artifacts

```text
a3c81299666a738b0602e0a3cee94918890cf68adbc7fded09994a00720bec40  phase2-certificate.json
a19cf65ba1f00612d20f90d9f87f238d32d9a0d5a433f681e9fcc1dacfa0447e  phase2.schema.json
49702976583a1113efe6d54e7c9be9cde6e15403e73b65d6d3ac6e136d936341  route-d-plus-phase2-23016779.out
956c70518ba64f566516d055a51cb9dc8fdc8942ab6340a3660ecd4f57fe8b09  route-d-plus-phase2-23016779.err
```

The committed certificate copy is
`docs/route-d-plus-phase2-job-23016779-certificate.json` and has the same
SHA-256 as the remote certificate.

## Gate assessment

Phase 2 is complete for the fixed single-particle LLL layer. This result
certifies the spinor convention, normalized orbital basis, reproducing kernel,
quadrature overlap, and off-grid reconstruction. It does not yet certify the
many-body Coulomb Hamiltonian, exact-diagonalization oracle, neural ansatz,
spin-2 many-body excitation, or the neutral gap.
