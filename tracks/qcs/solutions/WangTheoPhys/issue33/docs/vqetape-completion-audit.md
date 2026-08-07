# VQETape Completion Audit

## Status

The approved VQETape next-stage design is implemented and audited, including
an RTX 3090 follow-up validation and a correct same-node TensorCircuit-NG
threshold for the matched RZZ/RX workload. The paper Fig. 2 SU(4) protocol is
implemented with a passing small GPU correctness smoke; the formal
`N=32,L=16` scale run remains open.

Last full repository regression before the incremental Fig. 2 runner:

```text
395 passed, 6 skipped in 1582.14s (0:26:22)
```

The matched-baseline and Fig. 2 targeted suites subsequently pass
`17 passed` together, including a real cotengra path search, JSON round-trip,
and direct value-gradient control. The six skips in the full run are all the
expected structural case
`block wider than interior` in `tests/test_spatial_programs.py`; there are no
failed tests. This final clean-room regression used Python 3.12 with JAX and
jaxlib 0.11.0; the pinned RTX 3090 performance environment remains JAX 0.4.38.

Static artifact checks also passed:

- all 27 JSON reports parse with the standard JSON decoder;
- all `src/vqetape` modules compile;
- `git diff --check` reports no whitespace errors;
- the public API exposes compile, training, ansatz-growth, spatial, TFIM, and
  holdout entry points.

## Requirement-to-evidence matrix

| Approved requirement | Implementation | Tests | Raw evidence | Decision |
|---|---|---|---|---|
| Exact blocked spatial contraction | `spatial_plan.py`, `spatial_programs.py`, `spatial_candidates.py` | block/tail/path and value-gradient tests | blocked-spatial n8/n12 reports | Width 2/3 improve some warm frontiers; width 1 remains the 100-call default |
| Differentiated contraction model | `ad_analysis.py` | exact forward/reverse FLOPs, intermediates, traffic, residuals | AD-aware n8/n12 reports | Diagnostic; first static score did not beat forward FLOPs as a runtime predictor |
| Explicit contraction-tree VJP | `explicit_vjp.py` plus spatial integration | complex VJP correctness and identical-path comparisons | AD-aware reports | Reduces logical tape in every valid pair and reaches Pareto fronts; not a universal warm-time default |
| Exact symmetry compression | `symmetry.py`, `symmetry_programs.py` | sector invariance and compressed/reference/native value/VJP | symmetry n8/n12 reports | Recurrent boundary exactly halved; native BCOO remains optional because CPU tape/temp often increase |
| VQE time-to-solution | `ground_state.py`, `training.py`, `training_benchmark.py` | BdG oracle, timing/call accounting, fresh-process isolation | `vqetape-training-report.json` | Small-workload statevector wins; exact spatial choices remain scalability candidates |
| Classical optimizer co-design | `optimizers.py` | Adam, L-BFGS-B, exact-QGT natural-gradient fixtures | training report | Zero initialization is stationary; natural gradient saves calls but exact QGT loses wall time on the audited CPU |
| Initialization and recycling | `initialization.py` | deterministic random, chain/depth growth, shrink, padding | training report | Recycling lowers target-workload calls, but source-solve cost must be separately amortized |
| Adaptive ansatz design | `ansatz.py`, `ansatz_signals.py`, `ansatz_selection.py`, `ansatz_training.py` | exact gradients, metric diagonals, redundancy, fresh workers | `vqetape-ansatz-report.json` | Lie-closed YZ/ZY pool removes X/ZZ false convergence; 10 adaptive parameters reach \(5.05\times10^{-11}\) while the 14-parameter fixed control stops at \(1.70\times10^{-7}\) |
| Contraction-aware ansatz score | `ansatz_cost.py`, `ansatz_selection.py` | cut growth, cache keys, policy fixtures | ansatz report | Correct and non-harmful here, but selects the same three gates as gradient-only; no distinct speedup claim |
| Holdout generality | `holdout.py`, `holdout_worker.py`, `holdout_report.py` | dense action/energy, finite-difference gradient, commutator | `vqetape-holdout-report.json` | Longitudinal-field/RZZ–RY–RX workload converges; TFIM Z2 compression is explicitly rejected |
| Device/GPU evidence | `runtime_capabilities.py`, `subprocess_env.py` | JSON, memory-semantics, and worker-environment tests | `vqetape-gpu-rtx3090-findings.md` plus five raw JSON reports | RTX 3090 statevector/direct-TN/spatial jobs pass exactness with `highest` matmul precision; platform default fails a controlled spatial A/B comparison; an unset-parent-environment integration job confirms the worker default |
| TensorCircuit-NG threshold | `tensorcircuit_baseline.py`, `tensorcircuit_baseline_cli.py` | parameter/protocol parity, strict value-gradient correctness, CLI defaults | `tensorcircuit-ng-baseline-findings.md` and matched JSON | On the same RTX 3090, VQETape spatial is 8.2% faster on `compile + first + 100 warm` and uses 28.3% less host RSS; sampled device memory is tied |
| TensorCircuit-NG Fig. 2 protocol | `tensorcircuit_fig2.py`, `tensorcircuit_fig2_cli.py` | 7,440-parameter contract, score/slicing manifest, safe JSON round-trip, direct value-gradient control | `tensorcircuit-ng-fig2-smoke-findings.md` plus path/run JSON | RTX 3080 `N=6,L=3` smoke passes at `2.38e-7` energy and `3.29e-7` gradient error; this proves the protocol path, not formal `N=32,L=16` scale performance |

## Exactness invariants

The completed implementation preserves these invariants:

1. Candidate energy and complete gradients are checked against statevector
   oracles at audited sizes.
2. TFIM uses the fixed convention
   \[
   H=-J\sum_iZ_iZ_{i+1}-g\sum_iX_i.
   \]
3. The TFIM MPO has exact bond dimension three.
4. Spatial transfer never materializes a dense \(D\times D\) transfer matrix.
5. Z2 compression is only enabled for the supported plus-state,
   global-X-symmetric workload.
6. The longitudinal holdout uses dense diagonalization, not the TFIM BdG
   formula, and rejects Z2 compression.
7. Training target time includes compilation, synchronized value-gradient
   calls, screening/recompilation where applicable, and optimizer overhead.
8. Fresh workers use distinct in-memory and persistent compilation-cache
   state.
9. Process RSS, compiler temporary bytes, logical residual bytes, modeled
   checkpoint bytes, and genuine GPU peak memory remain separately labeled.
10. Fresh JAX workers default to `highest` matmul precision; an explicit
    caller environment override is preserved.
11. The TensorCircuit-NG runners apply that precision policy to both the
    TensorCircuit backend and TensorNetwork's separately cached JAX backend;
    otherwise TensorNetwork explicitly selects reduced-precision GPU dots.
12. Fig. 2 path artifacts are checksum-bound JSON, never executable pickle,
    and preserve the exact `15 * L * (N - 1)` parameter count.

## What is novel in the completed prototype

The integrated contribution is the executable comparison of

\[
\text{representation}
+\text{contraction path}
+\text{reverse program}
+\text{checkpoint schedule}
+\text{symmetry sector}
+\text{optimizer}
+\text{initialization}
+\text{ansatz growth}.
\]

Two results are especially substantive:

- explicit differentiated contraction programs expose a logical-tape versus
  runtime tradeoff that forward-only path scores miss;
- first-commutator YZ/ZY generators repair a real zero-gradient failure of the
  original symmetry-compatible X/ZZ adaptive pool while retaining exact
  rank-two two-site structure.

The project also records negative results:

- single-contraction and residual-threshold rematerialization do not
  automatically reduce compiler temporary memory;
- operator-Schmidt RZZ reduces logical tape but loses the measured executable
  Pareto comparison on the small CPU tests;
- the first AD-aware static score does not improve runtime ranking;
- sparse Z2 metadata can cost more than the removed dense carry on CPU;
- exact natural gradient can reduce iterations while increasing wall time;
- contraction-aware ansatz ranking earns no independent win on the symmetric
  four-qubit workload.
- a matched TensorCircuit-NG baseline beats VQETape statevector at this size,
  and VQETape spatial's 8.2% objective win does not yet imply a universal or
  Fig. 2-scale victory;
- `JAX_DEFAULT_MATMUL_PRECISION=highest` alone is insufficient for
  TensorNetwork contractions because its cached JAX backend explicitly uses
  `Precision.DEFAULT`; two controlled GPU jobs failed strict correctness
  before the backend precision was mapped explicitly.

## Current boundary

Completion means the approved exact one-dimensional research prototype is
done; it does not mean generic quantum simulation is solved. Remaining
out-of-scope work includes:

- arbitrary Python/TensorCircuit-NG program transformation;
- general Pauli-to-MPO compression;
- approximate MPS/PEPS truncation;
- two-dimensional or deep-circuit scaling;
- formal Fig. 2 `N=32,L=16,max_repeats=640` execution and slicing on
  paper-comparable hardware;
- larger-scale GPU peak-memory/performance sweeps and independent hardware
  replication;
- multi-GPU distribution and host offload;
- chemistry operator pools and shot/noise-aware optimization.

The original capability report records its local machine as CPU-only. The
separate RTX 3090 audit supplies CUDA-specific measurements without
retroactively relabeling those CPU runs.

## Reproduction

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python -m pytest -q
```

Representative reports can be regenerated with:

```bash
vqetape --mode spatial-transfer ...
vqetape --mode symmetry ...
vqetape-train ...
vqetape-ansatz \
  --output outputs/vqetape-ansatz-report.json \
  --findings outputs/vqetape-ansatz-findings.md
vqetape-tc-baseline \
  --nqubits 10 --depth 4 --seed 33 \
  --contractor omeco \
  --reference outputs/vqetape-gpu-rtx3090-statevector-n10-d4.json \
  --output outputs/tensorcircuit-ng-rtx3090-matched-n10-d4.json
vqetape-tc-fig2 manifest \
  --output outputs/tensorcircuit-ng-fig2-n32-l16-manifest.json
```

See the raw JSON and paired Markdown files under `outputs/` for the complete
machine-readable evidence.
