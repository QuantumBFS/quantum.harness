# VQETape Completion Audit

## Status

The approved VQETape next-stage design is implemented and audited.

Final repository regression:

```text
387 passed, 6 skipped in 795.29s (0:13:15)
```

The six skips are all the expected structural case
`block wider than interior` in `tests/test_spatial_programs.py`; there are no
failed tests.

Static artifact checks also passed:

- all 19 JSON reports parse with the standard JSON decoder;
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
| Device/GPU evidence | `runtime_capabilities.py` | JSON and memory-semantics tests | `vqetape-runtime-capabilities.json` | CPU backend detected; GPU benchmark is structurally skipped, not inferred from host RSS |

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

## Current boundary

Completion means the approved exact one-dimensional research prototype is
done; it does not mean generic quantum simulation is solved. Remaining
out-of-scope work includes:

- arbitrary Python/TensorCircuit-NG program transformation;
- general Pauli-to-MPO compression;
- approximate MPS/PEPS truncation;
- two-dimensional or deep-circuit scaling;
- cotengra/cuTensorNet-specific execution and slicing;
- real GPU peak-memory/performance measurements on a CUDA/ROCm machine;
- multi-GPU distribution and host offload;
- chemistry operator pools and shot/noise-aware optimization.

The capability report records the present machine as CPU-only, so no
CUDA-specific conclusion is made.

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
```

See the raw JSON and paired Markdown files under `outputs/` for the complete
machine-readable evidence.
