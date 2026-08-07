# Seed-free public final-audit preparation

Status: code snapshot and fail-closed entry contract validated on xh5. The
actual public audit has not run because discovery, confirmation, cost
sensitivity, and the report are not final.

The audit accepts only checksum-verified final summaries with the exact frozen
matrix sizes and stopping states. It also verifies the accepted candidate tree,
all five v2 negative controls, independent-implementation evidence, a
placeholder-free report, the science-gate table, and absence of a holdout spend
record. Its output contains no seed, private parameter tuple, request, label, or
oracle value.

```text
orchestration commit:
e19428e

orchestration tree:
b6ee9437840ac2041886b85c82ddb28b13b9f10b

orchestration archive SHA-256:
6cdd977c810a203764ae1f271cc45a3598d85e3bd565ffdddbb5e2e0459ee060

snapshot:
bundle-final-audit-e19428e

snapshot manifest SHA-256:
de684e2b2948de126360267e6b776529b52afe98c860c7c5e5a5779f3d525ee2

snapshot files covered:
160
```

xh5 job `23007248` ran only
`test_public_final_audit_requires_slurm`. It completed with exit `0:0`; the
contract passed and confirmed that the public audit refuses to run outside an
identified Slurm allocation. The 63-second pytest time was cold import time for
the existing scientific stack. No simulation, result analysis, report
mutation, private fixture, spend record, or holdout query was produced.
