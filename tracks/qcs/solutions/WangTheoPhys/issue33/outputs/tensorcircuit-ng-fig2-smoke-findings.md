# TensorCircuit-NG Fig. 2 protocol and GPU smoke

## What is now implemented

The repository now has an executable two-stage implementation of the
TensorCircuit-NG paper's Fig. 2 protocol:

- an adjacent-pair SU(4) ladder with `15 * L * (N - 1)` parameters;
- the open-boundary TFIM MPO used by the upstream
  `DistributedContractor` VQE example;
- cotengra `max_repeats=640` and the exact `combo-640` ordering, equivalent
  to minimizing `FLOPS + 640 * WRITE`;
- an explicit slicing target, defaulting to `2^29` elements;
- separate path search and value-gradient execution commands; and
- a checksum-bound JSON contraction-path artifact instead of the upstream
  pickle format.

The formal CLI defaults are `N=32,L=16`, which gives 7,440 parameters. The
paper reports 17.86 s per optimization step on one NVIDIA H200 (141 GB) and
2.38 s on eight H200s. Those paper values are reference values, not results
measured by this submission.

Two boundaries are explicit in the manifest. The paper states `2^29` slicing
for its 40-qubit case, not specifically the 32-qubit case. It also does not
state the Fig. 2 random seed; this runner uses seed 42 and scale 0.1 from the
upstream `DistributedContractor` VQE example.

Primary source: [TensorCircuit-NG, arXiv:2602.14167](https://arxiv.org/abs/2602.14167).

## Audited GPU smoke

Slurm job `23027373` completed with `COMPLETED/0:0` on node `e04r04`:

| Field | Result |
|---|---:|
| GPU | NVIDIA GeForce RTX 3080, 10,240 MiB |
| Workload | `N=6,L=3`, 225 SU(4) parameters |
| Path policy | 16 repeats, `combo-640`, target `2^20`, 4 workers |
| Path search | 7.868 s |
| Slices / max intermediate | 1 / 192 elements |
| First value-gradient, including JIT | 22.751 s |
| Warm value-gradient median | 19.424 ms |
| Host peak RSS | 869.6 MiB |
| NVML job peak | 266 MiB |
| Energy absolute error vs direct contraction | `2.38e-7` |
| Gradient relative L2 error vs direct contraction | `3.29e-7` |

The smoke is a structural and correctness gate, not a performance comparison
with either the H200 paper result or the matched RTX 3090 RZZ/RX baseline.
The smoke environment did not have KaHyPar, so cotengra used its basic-labels
fallback. It also warned that four path workers forked after JAX initialized;
the search completed, but the checked-in runner now defaults to one worker to
remove that deadlock risk. Search worker count is not part of the paper's
reported physics protocol.

## Reproduce

Write the formal protocol without importing GPU dependencies:

```bash
vqetape-tc-fig2 manifest \
  --output outputs/tensorcircuit-ng-fig2-n32-l16-manifest.json
```

Search and execute in separate processes:

```bash
JAX_DEFAULT_MATMUL_PRECISION=highest vqetape-tc-fig2 path \
  --nqubits 32 --depth 16 \
  --max-repeats 640 --target-size-log2 29 \
  --output fig2-path.json

JAX_DEFAULT_MATMUL_PRECISION=highest vqetape-tc-fig2 run \
  --path fig2-path.json --warm-repeats 3 \
  --output fig2-run.json
```

The safe GPU smoke job is
[`../scripts/tensorcircuit-ng-fig2-rtx3090-smoke.sbatch`](../scripts/tensorcircuit-ng-fig2-rtx3090-smoke.sbatch).

Raw evidence:

- [`tensorcircuit-ng-fig2-rtx3080-smoke-n6-l3-path.json`](tensorcircuit-ng-fig2-rtx3080-smoke-n6-l3-path.json), SHA256 `6c49a22cbc3e5553e1b5da2a9c4dc8db9c53f6e31b8fd7b03501e1339a900fcf`;
- [`tensorcircuit-ng-fig2-rtx3080-smoke-n6-l3-run.json`](tensorcircuit-ng-fig2-rtx3080-smoke-n6-l3-run.json), SHA256 `bf2eaecb2943e971ce8dd45968e362de6056ab3ad95234f74275dbfccc7911d5`.

The remaining scale gate is a full `N=32,L=16,max_repeats=640` execution on
hardware comparable to the paper. No such result is claimed here.
