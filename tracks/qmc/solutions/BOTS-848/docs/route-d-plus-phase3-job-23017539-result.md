# Route D+ Phase 3 job 23017539 result

## Outcome

Slurm job `23017539` completed the Route D+ Phase 3 tensor-algebra gate on one
V100. Ruff passed, all 18 scoped tests passed, the machine-readable
certificate reported `passed: true`, and an independent remote schema and
threshold check succeeded.

## Identity and resources

- Code revision: `ae9648a91fc4ec35d2c85ebbd9029f234fc296ab`
- Run ID: `route-d-plus-phase3-20260730-02`
- Cluster and partition: `xhcs3`, `xhhgnormal02`
- Node and accelerator: `v01r01`, one V100 16 GiB
- Allocation: two CPUs, 6 GiB memory
- Slurm state and exit code: `COMPLETED`, `0:0`
- Runtime: 87 seconds
- Phase 2 certificate SHA-256:
  `a3c81299666a738b0602e0a3cee94918890cf68adbc7fded09994a00720bec40`

## Software gates

The remote stdout contained:

```text
All checks passed!
..................                                                       [100%]
18 passed in 58.03s
```

An additional remote validation loaded the Phase 3 certificate and committed
schema, ran `jsonschema.validate`, asserted `passed is True`, and compared
every named maximum error with its corresponding tolerance. It returned:

```text
schema_valid=true errors_below_tolerances=true
```

## Tensor-algebra certificate

The certificate covers the complete set of 256 canonical tensors for
`2Q = 15`.

| Gate | Maximum error | Tolerance |
| --- | ---: | ---: |
| Hilbert--Schmidt orthonormality | `4.440892098500626e-16` | `1e-12` |
| Spherical Hermiticity | `0.0` | `1e-12` |
| Finite SO(3) rotation | `4.965068306494546e-16` | `1e-6` |
| Quadrature reconstruction | `9.848028687179946e-15` | `1e-12` |
| One-body kernel | `0.0` | `1e-12` |
| One-body action | `1.7802556885132077e-15` | `1e-12` |

## Pinned artifacts

```text
e8045083c72768eb94bc3ccad56430c2253e5e788fb94c2b199a5bb22c97d0bd  phase3-certificate.json
101c349f912378405601160da099321e55ae06e547be0b757a99d9e39bc8d2d7  phase3.schema.json
0758258a3a690017caef79e0e59313543f3eb353230ff9b8c980bfd3db00d2b0  route-d-plus-phase3-23017539.out
956c70518ba64f566516d055a51cb9dc8fdc8942ab6340a3660ecd4f57fe8b09  route-d-plus-phase3-23017539.err
```

The committed certificate copy has the same SHA-256 as the remote certificate.

## Gate assessment

Phase 3 is complete. The result certifies canonical Hilbert--Schmidt
normalization, spherical Hermiticity, finite-rotation covariance, the
continuous-coordinate tensor kernel, and the generic quadrature-based
one-body tensor action for the fixed LLL instance. It authorizes Phase 4
construction of the Laughlin mother and the five-component `L=2` tower, but
does not yet certify those many-body states or any energy gap.
