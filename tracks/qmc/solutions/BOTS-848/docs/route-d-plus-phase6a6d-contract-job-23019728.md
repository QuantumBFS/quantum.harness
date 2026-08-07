# Route D+ Phase 6A/6D contract: job 23019728

## Outcome

The isolated contract job failed at the Ruff prefix before executing tests.
The only reported defect was `TRY004` in
`route_d_plus/future/verify.py`: a non-object JSON payload used `ValueError`
instead of the required `TypeError`.

The source was clean at revision
`f21342a9d872cd47a8ce4616f3337b23332232c5`. JAX GPU/x64 initialization
passed on an RTX 3080 before Ruff ran. No project test, Phase 6A numerical
certificate, training seed, ED oracle, or ED artifact ran.

## Slurm and log evidence

- Job: `23019728`
- Cluster: `xhcs3`
- Partition: `xhhgnormal`
- Node: `e01r04`
- Allocation: one GPU, four CPUs, 12 GiB
- State and exit: `FAILED`, `1:0`
- Elapsed: 8 seconds
- stdout SHA-256:
  `0cfd8b45deae7fb57d44030ef3bb13820c1181e8593a07ffcf6b03818fd47ef6`
- stderr SHA-256:
  `956c70518ba64f566516d055a51cb9dc8fdc8942ab6340a3660ecd4f57fe8b09`

## Correction and next action

The exception type was corrected to `TypeError`. The retry must use a new
isolated run directory and rerun the complete Ruff/test contract. This failure
does not change any physical protocol or capacity decision.
