# VQETape: A Differentiated Co-Design Compiler for Exact VQE

**Challenge:** [QuantumBFS/quantum.harness #33](https://github.com/QuantumBFS/quantum.harness/issues/33)

**Team:** Ranger - Junkai Wang

**Pull request:** [QuantumBFS/quantum.harness #263](https://github.com/QuantumBFS/quantum.harness/pull/263)

**Public showcase:** [JunkaiWang-TheoPhy/issue-33-extreme-efficiency-vqe](https://github.com/JunkaiWang-TheoPhy/issue-33-extreme-efficiency-vqe)

**Evidence snapshot:** `748c5e974573e11a22e639dfe76ff00be9819f78`

**Report date:** 2026-07-30

> Compile the forward contraction, reverse program, and variational ansatz as one optimization problem.

## Executive result

VQETape is an exact, auto-evaluated compiler that searches tensor representation, contraction path, reverse program, saved residuals, checkpoint schedule, symmetry sector, classical optimizer, initialization, and ansatz growth. A controlled same-node TensorCircuit-NG 1.8.0 baseline anchors the result.

On the matched RTX 3090 workload, VQETape spatial transfer is **8.2% faster** for `compile + first + 100 warm` and uses **28.3% less host peak RSS** than TensorCircuit-NG. The same measurement identifies a precise next frontier: TensorCircuit-NG records a 2.6577 ms warm reference, while VQETape statevector records 3.3785 ms. Job-level device samples span 272-274 MiB.

| Result area | Status | Evidence |
|---|---|---|
| Auto-iteratable and auto-evaluatable harness | Demonstrated result | Candidate search, isolated workers, exact value-gradient gates, JSON reports, 395-test regression |
| First-time / amortized time efficiency | Demonstrated result | 18.2720 s TensorCircuit-NG vs 16.7781 s VQETape spatial |
| Host space efficiency | Demonstrated result | 661.3 MiB vs 473.9 MiB |
| Subsequent warm runtime | Next optimization frontier | 2.6577 ms TensorCircuit-NG reference vs 3.3785 ms VQETape statevector |
| Device-memory measurement | Measured trade-off | sampled job peaks 272-274 MiB |
| TensorCircuit-NG Fig. 2 construction | Validated protocol | direct value-gradient comparison at `N=6,L=3` |
| Paper-scale Fig. 2 execution | Scale-up target | `N=32,L=16` on paper-comparable hardware |

## Problem and protocol

The core kernel is `theta -> (E(theta), grad E(theta))` for the open-boundary transverse-field Ising model

`H = -J sum_i Z_i Z_(i+1) - g sum_i X_i`, with `J=g=1`.

The matched comparison uses one RTX 3090 on Slurm node `c05r05`, `n=10`, depth `L=4`, the plus initial state, RZZ then RX per layer, seed 33, complex64, five synchronized warm repeats, and highest JAX matmul precision. Every candidate is checked against an exact statevector value and complete gradient.

The declared selection objective is:

`T_objective = T_compile + T_first + 100 * median(T_warm)`.

## Matched RTX 3090 result

| Implementation | Compile (s) | First (s) | Warm median (ms) | Objective (s) | Host RSS (MiB) | NVML (MiB) | Correct |
|---|---:|---:|---:|---:|---:|---:|---|
| TensorCircuit-NG / OMECo | 17.7799 | 0.2263 | 2.6577 | 18.2720 | 661.3 | 272 | VALIDATED |
| VQETape / statevector | 28.7213 | 0.4025 | 3.3785 | 29.4617 | 462.4 | 272 | VALIDATED |
| VQETape / direct TN | 45.6544 | 0.1376 | 5.0498 | 46.2970 | 575.0 | 274 | VALIDATED |
| VQETape / spatial block-2 | 15.5816 | 0.3636 | 8.3281 | 16.7781 | 473.9 | 274 | VALIDATED |

The spatial program crosses the selected amortized threshold because its compile time is 2.1983 s lower. Steady-state measurements define a complementary design point: its warm call is 3.13x the TensorCircuit-NG reference, while the statevector path is 1.27x. The 2 MiB NVML spread is reported as a measured range.

## System design and technical contribution

VQETape treats VQE performance as a joint compiler problem instead of optimizing a single contraction:

1. **Exact representations:** statevector, direct bra-operator-ket tensor network, and an exact spatial-transfer lowering with a bond-dimension-three TFIM MPO.
2. **Program search:** contraction path, block width, scan/unroll policy, reverse-mode residual strategy, rematerialization, and checkpoint placement.
3. **Physics-aware reductions:** an exact global-X Z2 sector is enabled only when the Hamiltonian, initial state, and ansatz preserve it.
4. **End-to-end VQE co-design:** Adam, L-BFGS-B, exact-QGT natural gradient, initialization/recycling, and adaptive ansatz growth are evaluated with compile and optimizer overhead included.
5. **Auditable execution:** candidates run in fresh processes, record machine-readable JSON, keep memory semantics separate, and enter selection only after value-gradient validation.

Two technical contributions go beyond a benchmark wrapper. First, explicit contraction-tree VJPs expose logical-tape/runtime trade-offs hidden from forward-only path scores. Second, a commutator-complete YZ/ZY adaptive pool expands the tangent space beyond the stationary X/ZZ pool: the adaptive 10-parameter circuit reaches `5.05e-11` energy error, while the 14-parameter fixed control records `1.70e-07` under the audited budget.

## TensorCircuit-NG Fig. 2 protocol

The separate Fig. 2 runner encodes the paper's SU(4) ladder ansatz, `15 * L * (N-1)` parameters, TensorNetwork FiniteTFI MPO, contraction-path search, slicing configuration, and checksum-bound safe JSON path artifacts. On an NVIDIA RTX 3080, the `N=6,L=3` execution (225 parameters) records energy error `2.38e-07` and gradient relative L2 error `3.29e-07`. This validates construction and artifact replay; `N=32,L=16` is the declared scale-up target.

## Verification and provenance

- Full regression before the incremental Fig. 2 runner: `395 passed, 6 declared structural cases in 1582.14s`.
- Targeted matched-baseline and Fig. 2 suite: `17 passed`.
- All 27 committed JSON reports parse; all `src/vqetape` Python modules compile; `git diff --check` passes.
- TensorCircuit-NG job `23020496` completed on `c05r05`, reported `cuda:0`, passed strict energy/gradient tolerances, and passed SHA256 provenance checks.
- Fig. 2 smoke job `23027373` completed on an RTX 3080 and passed direct unsliced value-gradient comparison.

## Measured trade-offs and research frontier

Every explored design remains visible in the evidence layer: sparse Z2 metadata trades a smaller exact carry for CPU bookkeeping; exact natural gradient trades fewer iterations for QGT construction; operator-Schmidt gates trade logical tape for executable time; and the precision bridge maps the declared JAX policy into TensorNetwork's cached backend. These observations make the next compiler search directions explicit and reproducible.

The demonstrated scope is exact one-dimensional TFIM and longitudinal-Ising workloads. The next research trajectory extends the same differentiated-program representation to deeper circuits, two-dimensional networks, multi-GPU slicing, host offload, and the paper-scale Fig. 2 point. The immediate compiler objective is fusion of VQETape's reverse-program advantages with the TensorCircuit-NG warm-kernel reference.

## Reproduction

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[test,baseline]'
.venv/bin/python -m pytest -q

vqetape-tc-baseline \
  --nqubits 10 --depth 4 --seed 33 --warm-repeats 5 \
  --expected-steps 100 --contractor omeco \
  --reference outputs/vqetape-gpu-rtx3090-statevector-n10-d4.json \
  --output outputs/tensorcircuit-ng-rtx3090-matched-n10-d4.json

python scripts/build_submission_report.py
```

Canonical evidence remains under `outputs/`. `submission/vqetape-matched-benchmark.tsv` is the compact data export, `submission/submission-status.txt` is the result map, and `submission/artifact-manifest.json` binds the review artifacts by SHA256.
