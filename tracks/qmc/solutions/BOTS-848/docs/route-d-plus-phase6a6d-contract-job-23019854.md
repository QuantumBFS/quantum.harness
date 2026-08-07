# Route D+ Phase 6A--6D contract: job 23019854

## Outcome

The unified implementation contract passed at clean revision
`1b086e4cdf467d7d5cf894ddefd266f91ecd6352`. Ruff passed and 68 scoped tests
passed, including the N=6 continuous proof/production backend comparison,
Phase 6A certificate contract, shared-architecture/combined-SR contract, and
Phase 7--11 dependency verifier contracts.

This is an implementation contract, not the Phase 6 exit certificate. It
does not freeze a trained checkpoint or authorize ED reveal.

## Slurm and immutable logs

- Job: `23019854`
- Cluster: `xhcs3`
- Partition: `xhhgnormal`
- Node: `e01r04`
- GPU: NVIDIA GeForce RTX 3080,
  `GPU-37308f53-5d41-5adf-dc15-7dbd169c669f`
- Allocation: one GPU, four CPUs, 12 GiB
- State and exit: `COMPLETED`, `0:0`
- Elapsed: 21 seconds
- Test result: 68 passed in 12.41 seconds
- stdout SHA-256:
  `3b0fbffed952ea1e2c60a33d236b74f166c07a83624ee2f2f432d9fe4641022e`
- stderr SHA-256:
  `956c70518ba64f566516d055a51cb9dc8fdc8942ab6340a3660ecd4f57fe8b09`
- Independent source readback: same revision, clean worktree

## Preceding retry

Job `23019824` stopped at Ruff before tests because
`train_dplus0.py` retained one unused local variable. It ran clean revision
`9c2d88713c6195ded6b5f954951d2b74f5680272`, exited `1:0` after five seconds,
and did not run tests, training, or ED.

- stdout SHA-256:
  `ed0f763200d3ca49bc69aa7ce03d3605aab694613d97c67dd90fd7f171f2618c`
- stderr SHA-256:
  `956c70518ba64f566516d055a51cb9dc8fdc8942ab6340a3660ecd4f57fe8b09`

## Dependency assessment

The implementation is ready for the isolated Phase 6A numerical profile and
independent readback. Phase 6B/6C still require three completed seed runs,
full symmetry readback, statistically adequate stopping gates, frozen
checkpoint/architecture manifests, and a single aggregate certificate.
No ED oracle or ED artifact was read or executed.
