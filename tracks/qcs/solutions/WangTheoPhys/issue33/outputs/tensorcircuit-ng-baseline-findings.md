# TensorCircuit-NG matched RTX 3090 baseline

## Comparison contract

This experiment supplies the missing same-machine TensorCircuit-NG threshold
for the workload already measured by VQETape:

- open-boundary `H = -sum(ZZ) - sum(X)`;
- `n=10`, depth `L=4`, `|+>^n`, RZZ then RX;
- parameter shape `(4, 2, 10)`, NumPy `default_rng(33)`, normal scale `0.1`;
- `complex64`, five synchronized warm repetitions;
- one NVIDIA RTX 3090 on Slurm node `c05r05`;
- JAX/JAXlib 0.4.38 and `JAX_DEFAULT_MATMUL_PRECISION=highest`.

TensorCircuit-NG 1.8.0 with TensorNetwork-NG 0.5.1 uses the construction in
`examples/benchmark_jax_vs_torch_vqe.py`: `PauliStringSum2COO`, a JAX
value-and-gradient, and OMECo TreeSA with 16 trials, 16 iterations, and the
published small-example score weights. Lowering plus compilation includes the
one measured OMECo path search.

## Audited result

| Implementation | Slurm job | Compile (s) | First execute (s) | Warm median (ms) | Warm MAD (ms) | Compile + first + 100 warm (s) | Host peak RSS (MiB) | NVML job peak (MiB) | Energy abs. error | Gradient rel. L2 error |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| TensorCircuit-NG, OMECo | 23020496 | 17.7799 | 0.2263 | 2.6577 | 0.0070 | 18.2720 | 661.3 | 272 | 3.81e-6 | 6.19e-7 |
| VQETape statevector | 23015042 | 28.7213 | 0.4025 | 3.3785 | 0.0231 | 29.4617 | 462.4 | 272 | 0 | 0 |
| VQETape direct TN | 23015037 | 45.6544 | 0.1376 | 5.0498 | 0.0669 | 46.2970 | 575.0 | 274 | 9.54e-7 | 4.18e-7 |
| VQETape spatial transfer, block 2 | 23015038 | 15.5816 | 0.3636 | 8.3281 | 0.0269 | 16.7781 | 473.9 | 274 | 3.81e-6 | 9.15e-7 |

Job 23020496 ended `COMPLETED/0:0`, reported `cuda:0`, recorded both
TensorCircuit and TensorNetwork contraction precision as `HIGHEST`, passed
the `1e-5` energy and gradient tolerances, and passed remote and local SHA256
audits.

The baseline is competitive and changes the interpretation of the existing
results:

- TensorCircuit-NG is 1.61x faster than VQETape statevector on the declared
  100-step objective and has a 1.27x faster warm value-gradient;
- VQETape spatial transfer is 8.2% faster than TensorCircuit-NG on the same
  objective and uses 28.3% less host peak RSS;
- TensorCircuit-NG has the faster warm kernel, so the measured spatial win is
  a compilation-amortization result, not a universal steady-state win;
- the 272--274 MiB sampled NVML peaks are effectively tied at this small size
  and do not establish a device-memory victory.

This crosses the minimum threshold of having an executable, correct,
same-workload, same-node TensorCircuit-NG baseline. It does **not** establish
that VQETape has surpassed every official TensorCircuit-NG benchmark in both
time and space.

## Precision defect found during the baseline

Two control jobs exposed a TensorNetwork/JAX integration hazard:

| Control | Slurm job | TensorNetwork dot precision | Energy abs. error | Gradient rel. L2 error | Result |
|---|---:|---|---:|---:|---|
| OMECo | 23020299 | `DEFAULT` | 2.71e-3 | 2.14e-3 | fail |
| Greedy | 23020423 | `DEFAULT` | 3.87e-3 | 2.30e-3 | fail |
| OMECo, repaired | 23020496 | `HIGHEST` | 3.81e-6 | 6.19e-7 | pass |

TensorNetwork caches a separate JAX backend and passes an explicit
`Precision.DEFAULT` to `jnp.tensordot`. That explicit argument overrides the
surrounding `JAX_DEFAULT_MATMUL_PRECISION=highest` policy. The baseline runner
now maps the requested JAX policy onto both the TensorCircuit and
TensorNetwork backend objects before tracing. The strict correctness threshold
was not relaxed.

## Boundary versus the paper Fig. 2 protocol

This matched RZZ/RX comparison is deliberately smaller and different from the
TensorCircuit-NG paper's Fig. 2 experiment. The paper uses an SU(4) ladder
ansatz with `15 * L * (N - 1)` trainable parameters, reports `N=32, L=16` for
the single-GPU case, searches with cotengra `max_repeats=640`, scores FLOPs
plus `640 * WRITE`, and slices toward roughly `2^29` elements. Reproducing that
protocol is the next scale gate; none of the numbers above should be relabeled
as a Fig. 2 reproduction.

## Reproduction and raw evidence

Install the optional baseline dependencies and run:

```bash
python3.12 -m pip install -e '.[baseline]'
JAX_DEFAULT_MATMUL_PRECISION=highest vqetape-tc-baseline \
  --nqubits 10 --depth 4 --seed 33 \
  --warm-repeats 5 --expected-steps 100 \
  --contractor omeco \
  --reference outputs/vqetape-gpu-rtx3090-statevector-n10-d4.json \
  --output outputs/tensorcircuit-ng-rtx3090-matched-n10-d4.json
```

Machine-readable result:
[`tensorcircuit-ng-rtx3090-matched-n10-d4.json`](tensorcircuit-ng-rtx3090-matched-n10-d4.json),
SHA256 `25a0e6ae819582410ca87492eb03a73f1c1aff1a7df5125d5509acae62e0ac9b`.
