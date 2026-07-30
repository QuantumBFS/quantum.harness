# VQETape Technical Report

**Challenge:** [QuantumBFS/quantum.harness #33](https://github.com/QuantumBFS/quantum.harness/issues/33)

**Team:** Ranger - Junkai Wang

**Pull request:** [QuantumBFS/quantum.harness #263](https://github.com/QuantumBFS/quantum.harness/pull/263)

**Evidence snapshot:** `748c5e974573e11a22e639dfe76ff00be9819f78`

**Report date:** 2026-07-30

## Executive result

VQETape is an exact, auto-evaluated VQE compiler prototype that searches tensor representation, contraction path, reverse program, checkpoint schedule, symmetry sector, classical optimizer, initialization, and ansatz growth. A controlled same-node baseline against TensorCircuit-NG 1.8.0 is complete.

On the matched RTX 3090 workload, VQETape spatial transfer is **8.2% faster** for `compile + first + 100 warm` and uses **28.3% less host peak RSS** than TensorCircuit-NG. This is a real but bounded win: TensorCircuit-NG still has the fastest warm kernel, and sampled device-memory peaks are tied. Therefore the literal challenge is **partially met**, not fully met.

| Requirement | Verdict | Evidence |
|---|---|---|
| Auto-iteratable and auto-evaluatable harness | PASS | Candidate search, isolated workers, exact value-gradient checks, JSON reports, 395-test regression |
| First-time / amortized time efficiency | PASS at matched `n=10,L=4` | 18.2720 s TensorCircuit-NG vs 16.7781 s VQETape spatial |
| Subsequent warm runtime superiority | NOT MET | 2.6577 ms TensorCircuit-NG vs 3.3785 ms best VQETape warm kernel |
| Host space efficiency | PASS at matched size | 661.3 MiB vs 473.9 MiB |
| Device-memory superiority | NOT ESTABLISHED | sampled job peaks 272-274 MiB |
| Formal TensorCircuit-NG Fig. 2 scale | OPEN | protocol plus small GPU smoke complete; `N=32,L=16` H200-scale run absent |

## Problem and protocol

The core kernel is `theta -> (E(theta), grad E(theta))` for the open-boundary transverse-field Ising model

`H = -J sum_i Z_i Z_(i+1) - g sum_i X_i`, with `J=g=1`.

The matched comparison uses one RTX 3090 on Slurm node `c05r05`, `n=10`, depth `L=4`, the plus initial state, RZZ then RX per layer, seed 33, complex64, five synchronized warm repeats, and highest JAX matmul precision. Every candidate is checked against an exact statevector value and complete gradient.

The declared selection objective is:

`T_objective = T_compile + T_first + 100 * median(T_warm)`.

## Matched RTX 3090 result

| Implementation | Compile (s) | First (s) | Warm median (ms) | Objective (s) | Host RSS (MiB) | NVML (MiB) | Correct |
|---|---:|---:|---:|---:|---:|---:|---|
| TensorCircuit-NG / OMECo | 17.7799 | 0.2263 | 2.6577 | 18.2720 | 661.3 | 272 | PASS |
| VQETape / statevector | 28.7213 | 0.4025 | 3.3785 | 29.4617 | 462.4 | 272 | PASS |
| VQETape / direct TN | 45.6544 | 0.1376 | 5.0498 | 46.2970 | 575.0 | 274 | PASS |
| VQETape / spatial block-2 | 15.5816 | 0.3636 | 8.3281 | 16.7781 | 473.9 | 274 | PASS |

The spatial program crosses the selected amortized threshold because its compile time is 2.1983 s lower. It does **not** win at steady state: its warm call is 3.13x slower than TensorCircuit-NG, while the statevector path is 1.27x slower. The NVML samples differ by only 2 MiB and cannot support a GPU-memory superiority claim.

## System design and technical contribution

VQETape treats VQE performance as a joint compiler problem instead of optimizing a single contraction:

1. **Exact representations:** statevector, direct bra-operator-ket tensor network, and an exact spatial-transfer lowering with a bond-dimension-three TFIM MPO.
2. **Program search:** contraction path, block width, scan/unroll policy, reverse-mode residual strategy, rematerialization, and checkpoint placement.
3. **Physics-aware reductions:** an exact global-X Z2 sector is enabled only when the Hamiltonian, initial state, and ansatz preserve it.
4. **End-to-end VQE co-design:** Adam, L-BFGS-B, exact-QGT natural gradient, initialization/recycling, and adaptive ansatz growth are evaluated with compile and optimizer overhead included.
5. **Auditable execution:** candidates run in fresh processes, record machine-readable JSON, keep memory semantics separate, and fail on value-gradient tolerance violations.

Two technically meaningful results go beyond a benchmark wrapper. First, explicit contraction-tree VJPs expose logical-tape/runtime tradeoffs hidden from forward-only path scores. Second, a commutator-complete YZ/ZY adaptive pool fixes the zero-gradient failure of the original X/ZZ pool: the adaptive 10-parameter circuit reaches `5.05e-11` energy error, while the 14-parameter fixed control stops at `1.70e-07` under the audited budget.

## TensorCircuit-NG Fig. 2 protocol

The separate Fig. 2 runner encodes the paper's SU(4) ladder ansatz, `15 * L * (N-1)` parameters, TensorNetwork FiniteTFI MPO, contraction-path search, slicing configuration, and checksum-bound safe JSON path artifacts. On an NVIDIA RTX 3080, the `N=6,L=3` structural smoke (225 parameters) passed with energy error `2.38e-07` and gradient relative L2 error `3.29e-07`. This validates protocol construction only; it is not the paper-comparable `N=32,L=16` result.

## Verification and provenance

- Full regression before the incremental Fig. 2 runner: `395 passed, 6 skipped in 1582.14s`; the skips are documented structural cases, with no failures.
- Targeted matched-baseline and Fig. 2 suite: `17 passed`.
- All 27 committed JSON reports parse; all `src/vqetape` Python modules compile; `git diff --check` passes.
- TensorCircuit-NG job `23020496` completed on `c05r05`, reported `cuda:0`, passed strict energy/gradient tolerances, and passed SHA256 provenance checks.
- Fig. 2 smoke job `23027373` completed on an RTX 3080 and passed direct unsliced value-gradient comparison.

## Negative results and limitations

Negative results are retained because they prevent misleading optimization claims: sparse Z2 metadata can exceed the dense carry on CPU; exact natural gradient can save iterations but lose wall time; operator-Schmidt gates can reduce logical tape but lose runtime; and default GPU matmul precision failed strict spatial correctness until the TensorNetwork backend precision was mapped explicitly.

The present prototype is exact and focused on one-dimensional TFIM/longitudinal-Ising research workloads. It is not an arbitrary TensorCircuit-NG Python source transformer. It does not establish two-dimensional, deep-circuit, multi-GPU, host-offload, or formal Fig. 2 scale performance. Most importantly, the matched experiment does not meet the challenge's warm-runtime clause.

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

Canonical evidence remains under `outputs/`. `submission/vqetape-matched-benchmark.tsv` is the compact data export, `submission/submission-status.txt` is the literal pass/fail statement, and `submission/artifact-manifest.json` binds the review artifacts by SHA256.
