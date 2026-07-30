# Route D+ Phase 6 runtime contract: job 23019658

## Outcome

The isolated GPU runtime contract passed at source revision
`852ff7391ab5058554cdb6a48d6ae15dd12d9773`. This resolves the CUDA/cuDNN
loader failure observed in job `23019458`, but it is not a Phase 6 exit
certificate and does not freeze a checkpoint or architecture.

No ED oracle or ED artifact was read or executed.

## Slurm and runtime evidence

- Job: `23019658`
- Cluster: `xhcs3`
- Partition: `xhhgnormal`
- Node: `e01r04`
- GPU: NVIDIA GeForce RTX 3080,
  `GPU-37308f53-5d41-5adf-dc15-7dbd169c669f`
- Allocation: one GPU, four CPUs, 12 GiB
- State and exit: `COMPLETED`, `0:0`
- Elapsed: 17 seconds
- JAX: `0.4.38`, device `cuda:0`, x64 enabled
- Pinned compatibility-library SHA-256:
  `4f045231ff3a95c2fbfde450575f0ef45d23e95be15193c8729b521fc363ece4`

## Contract gates

- Source revision matched the pre-registered revision.
- The remote worktree was clean before execution and on independent readback.
- JAX initialized a GPU device with x64 enabled.
- Ruff passed.
- All 58 scoped Route D+ tests passed in 7.19 seconds.
- The job printed `CONTRACT_GATE=passed`.

## Pinned logs

- stdout:
  `tracks/qmc/results/route-d-plus-phase6-runtime-contract-20260730-01/slurm-23019658.out`
- stdout SHA-256:
  `a24dd17567e5be060c6328f165f21a91d35c5c46aae7ac6db00525cbf04f9d5d`
- stderr:
  `tracks/qmc/results/route-d-plus-phase6-runtime-contract-20260730-01/slurm-23019658.err`
- stderr SHA-256:
  `956c70518ba64f566516d055a51cb9dc8fdc8942ab6340a3660ecd4f57fe8b09`

## Gate assessment

The certified Phase 1 compatibility directory and CUDA-wheel library paths
are sufficient to initialize the current Phase 6 JAX runtime. Full Phase 6
training remains blocked on the stronger Phase 6A--6C contracts: common
architecture calibration, combined state-averaged SR, complete symmetry and
blind-ED audit, statistically adequate three-seed runs, checkpoint freeze,
and independent aggregate readback.
