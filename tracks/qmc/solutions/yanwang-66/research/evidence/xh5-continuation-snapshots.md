# xh5 continuation snapshot candidates

These snapshots were staged with shell-only file operations on xh5. No Python,
simulation, validator, or analysis ran on a login node. Every candidate derives
its frozen matrix and generated instance database from the accepted
`bundle-analysis-55ffeb1-r2` snapshot, whose manifest SHA-256 is
`b82a909424f3703c50f015fde5590cf180e87cf255c4241ffa17e637fc898e9d`.

## Superseded candidates

`bundle-analysis-f7ce59b` has manifest SHA-256
`66f837c74ea8f756f47687a36de87b50173bc828344ed141e9463615227d1856`.
It introduced eight-policy continuation parallelism and xh5 CPU routing, but
its 45-minute execution projection did not cover the registered 2,000,000-shot
discovery ceiling. It is staged but rejected for execution.

`bundle-analysis-3f4ad4d` has manifest SHA-256
`4aca50f026d70231b7e022425fd0c25b4bb413b48adc7be047fbbe7cc69dbd99`.
It extended the scheduler contract across every reachable increment through
the 2,000,000-shot ceiling. It was superseded before execution because a long
multi-group array element could not safely resume after a partial failure.

`bundle-analysis-7f8808e` has manifest SHA-256
`2b749de57f6786e353d0070515df7ce4ffd1fa571f48b07a93a51df2cdf39c49`.
It added atomic group staging, completed-group validation, and safe same-array
requeue support. It was superseded before execution so the same combined gate
could validate the preregistered cost-sensitivity family and baseline-reuse
invariant.

`bundle-analysis-ea7d712` has manifest SHA-256
`8bd4ae63e8b2249fa52c2134308b6c74b8d9ad9f622c167873d81a2604c6dfb5`.
It integrated the preregistered cost-sensitivity family and baseline-reuse
guard into the combined analysis gate. It was superseded before execution to
make the first discovery analysis emit compact, checksummed per-shot failure
state for storage-bounded continuation analysis.

`bundle-analysis-fe356a8` has manifest SHA-256
`1d5b8694afa318d4892f7a2787a4c4d0a824e471cfa526e0c48aaed6b3106762`.
It emitted compact, checksummed per-cell logical-failure state. It was
superseded before execution so continuation analysis could consume that state
without historical raw results and reject semantic inconsistencies even when
all artifact checksums had been regenerated.

`bundle-analysis-dac5c6d` has manifest SHA-256
`54ae77eddaaaf522c751e1337547785fd4a073c11e7979ef82b7839fcc3915e6`.
It made continuation analysis independent of historical raw results and added
semantic compact-state verification. It was superseded before execution to
freeze the already-preregistered headline confirmation slice and its
domain-separated seed family in the same combined analysis gate.

## Current candidate

`bundle-analysis-9ca2f33` has manifest SHA-256
`4aa22b20a9a657dfaa5e1e1fe1798963d60397f4c70fcd3f263d9db738128428`.
Its source identity is:

```text
commit: 9ca2f3375ea01d6a0d1afe175c5c2473a666c73c
tree:   f0f5643702c2b4e30d60e99f7aa03352c94685b7
```

The snapshot manifest excludes itself and successfully verifies all 43
entries from the final snapshot directory. Its inherited immutable inputs are:

```text
surface_code_instances.jsonl:
25e286b75968232ac04f7ad964f8fd683ec1f237bfbb794f8a1e2cbb5959f751

discovery-matrix-v1.json:
75490cff0949dc128221bf9168138d4d813c07014f26c1c9cacac9b2ec6b9b18

cost_sensitivity_families.json:
ff5fddd9b6019b06a61fe43e59c50fc385ec29921351ff815a2d7d233affa900

confirmation_families.json:
33b4ce05177179be9036a40d5e28b66dd62219a543d391750bb28ef5b4c1635a
```

This candidate is not accepted yet. The Phase-1 import and analysis allocation
must verify its outer manifest hash, run the experiment-core, discovery, and
cost-sensitivity contracts, import the checksummed SCNet archive, and finish
the registered 20,000-resample analysis. Only a successful Slurm result can
change its status to accepted.
