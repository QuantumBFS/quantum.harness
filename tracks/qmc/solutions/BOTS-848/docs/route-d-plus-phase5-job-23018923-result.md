# Route D+ Phase 5 job 23018923 result

## Outcome

Slurm job `23018923` completed the Route D+ Phase 5 scalar-generator gate on
one RTX 3080. Ruff passed, all 40 scoped tests passed, the certificate reported
`passed: true`, and an independent remote schema, tolerance, and covariance
rank check succeeded.

## Identity and resources

- Code revision: `7ed0b3f450cef23cfd8393d3b1f65e03eeaf20b9`
- Run ID: `route-d-plus-phase5-20260730-04`
- Cluster and partition: `xhcs3`, `xhhgnormal`
- Node and accelerator: `e09r03`, one RTX 3080
- Allocation: four CPUs, 12 GiB memory
- Slurm state and exit code: `COMPLETED`, `0:0`
- Runtime: 72 seconds
- Phase 4 certificate SHA-256:
  `6c62aa76cbb2fc683df1807d583f3c121f34164c3b5ebe8fb6d780fe3108b0a6`

## Software gates

```text
All checks passed!
........................................                                 [100%]
40 passed in 48.12s
```

The independent remote readback loaded the certificate and committed schema,
validated them with `jsonschema`, checked every measured error against its
named tolerance, and checked that the covariance spectrum retained exactly
the two directions above the relative `1e-12` algebraic cutoff. It returned:

```text
schema_valid=true rank2_cutoff_valid=true errors_below_tolerances=true
```

## Scalar-generator certificate

The proof backend evaluates the symmetrized density-product definition of
normal-ordered `G_2`, `G_3`, and `G_4`. The production backend evaluates the
normal-ordered pair action directly and obtains pair-channel eigenvalues from
the two-particle coupled subspaces. The algebraic certificate uses the first
nontrivial `N=4`, `2Q=9` LLL Fock space while recording the target baseline
`N=6`, `2Q=15`.

| Gate | Maximum error | Tolerance |
| --- | ---: | ---: |
| One-body Casimir residual | `5.551115123125783e-17` | `1e-13` |
| Hermiticity | `5.551115123125783e-17` | `1e-12` |
| Rotational scalarity | `7.771561172376096e-16` | `1e-11` |
| Proof/production agreement | `4.440892098500626e-16` | `1e-10` |
| Coupled-channel spread | `4.440892098500626e-16` | `1e-11` |
| Analytic-mother reconstruction | `1.882053704053365e-15` | `1e-10` |
| Whitening identity | `1.9177992527374954e-12` | `1e-8` |

The sampled covariance eigenvalues were:

```text
[6.0702652861802176e-18, 0.0013469041260756216, 0.7056971431693019]
```

Thus the smallest direction is below `1e-12` times the largest eigenvalue and
is deleted as strictly redundant. The other two directions are retained and
whitened. The centered mixture mean was
`[-0.3511308174241486, 0.12479008553924985, 0.4236890341253063]`.

## Diagnostic corrections

- Job `23018857` failed before execution because its Slurm output parent
  directory had not been created.
- Job `23018862` exposed an invalid `N=3` covariance certificate: all
  eigenvalues were floating-point noise near `1e-30`, so it was rejected even
  though its initial schema passed.
- Job `23018909` verified the corrected `N=4` algebra and showed that exactly
  two rather than three directions survive the prescribed cutoff. The final
  schema records this strict redundancy instead of forcing a noise direction.
- Pending duplicate V100 job `23018848` was cancelled after the RTX 3080
  diagnostic completed.

## Pinned artifacts

```text
5a21cee9ad2cdba4a0c128bd86701fa4fc56aa8d5b7b3b64fc4a79d41c672a1e  phase5-certificate.json
04a19b80eea226bf8aca5d82602d1234ed0ce4c509a87ced6a372549274d3eed  phase5.schema.json
4840672e619cc3df9702fc3c4e3038c9759c0e13149c1b673fc067646814787d  slurm-23018923.out
956c70518ba64f566516d055a51cb9dc8fdc8942ab6340a3660ecd4f57fe8b09  slurm-23018923.err
```

The committed certificate copy has the same SHA-256 as the remote certificate.

## Gate assessment

Phase 5 is complete. The normal-ordered scalar generators preserve the LLL,
are Hermitian rotational scalars, and have matching proof and production
implementations. Centering and whitening are fixed without consulting ED
energies, and only the covariance direction proven redundant by the prescribed
relative threshold is removed. This authorizes Phase 6 D+0 construction but
does not yet certify VMC training, ED comparison, chirality, or the neutral
gap.
