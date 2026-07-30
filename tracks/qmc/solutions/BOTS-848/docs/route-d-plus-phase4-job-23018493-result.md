# Route D+ Phase 4 job 23018493 result

## Outcome

Slurm job `23018493` completed the Route D+ Phase 4 analytic-mother gate on
one V100. Ruff passed, all 25 scoped tests passed, all five quadrupole tower
components were nonzero, the certificate reported `passed: true`, and an
independent remote schema and threshold check succeeded.

## Identity and resources

- Code revision: `ccd21ee97cf4de9a0c6d55b5351921b7c5fab23b`
- Run ID: `route-d-plus-phase4-20260730-01`
- Cluster and partition: `xhcs3`, `xhhgnormal02`
- Node and accelerator: `v01r08`, one V100 16 GiB
- Allocation: two CPUs, 6 GiB memory
- Slurm state and exit code: `COMPLETED`, `0:0`
- Runtime: 68 seconds
- Phase 3 certificate SHA-256:
  `e8045083c72768eb94bc3ccad56430c2253e5e788fb94c2b199a5bb22c97d0bd`

## Software gates

```text
All checks passed!
.........................                                                [100%]
25 passed in 49.12s
```

The independent remote readback loaded the certificate and committed schema,
validated them with `jsonschema`, asserted that every error was below its
named tolerance, and asserted that the minimum tower-component magnitude was
greater than `1e-14`. It returned:

```text
schema_valid=true tower_nonzero=true errors_below_tolerances=true
```

## Analytic-mother certificate

The fixed instance has six electrons and `2Q = 15`. The smallest magnitude
among the five measured `Phi_(2M)` components was
`4.178450699972481e-09`.

| Gate | Maximum error | Tolerance |
| --- | ---: | ---: |
| Laughlin exchange | `2.0983311102691217e-14` | `1e-12` |
| Laughlin particle degree | `1.2983754843253136e-14` | `1e-12` |
| Laughlin SU(2) rotation | `6.924728093721379e-15` | `1e-12` |
| Tower exchange | `2.2199490264776694e-14` | `1e-10` |
| Tower particle degree | `1.497460215768553e-14` | `1e-10` |
| Rank-two ladder | `4.996003610813204e-16` | `1e-8` |
| Finite SO(3) rotation | `2.221495769046069e-16` | `1e-6` |
| Equal component norm | `0.0` | `1e-12` |

## Pinned artifacts

```text
6c62aa76cbb2fc683df1807d583f3c121f34164c3b5ebe8fb6d780fe3108b0a6  phase4-certificate.json
17e39dabca91c17e3f283c95da546969dac30c7407259ccb77311fdd67d41108  phase4.schema.json
77b39d600d9ad9653e9badd0f114ce27ad9f3ff475c07e82f00b4eeccf06d1fd  route-d-plus-phase4-23018493.out
956c70518ba64f566516d055a51cb9dc8fdc8942ab6340a3660ecd4f57fe8b09  route-d-plus-phase4-23018493.err
```

The committed certificate copy has the same SHA-256 as the remote certificate.

## Gate assessment

Phase 4 is complete. The analytic Laughlin mother preserves exact nodes,
fermionic exchange, degree `2Q`, and SU(2) singlet structure. The calibrated
proof backend produces five nonzero `Phi_(2M)` components with the required
rank-two ladder, finite-rotation, degree, exchange, and equal-norm properties.
This authorizes Phase 5 scalar-generator construction but does not yet certify
those generators, ED, VMC, chirality, or the neutral gap.
