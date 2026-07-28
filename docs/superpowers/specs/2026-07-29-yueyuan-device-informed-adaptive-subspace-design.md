# YueYuan Device-Informed Adaptive Subspace Design

## Goal

Push challenge #113 attempt 004 from a strong fixed/widened Hessian-subspace
answer toward a publishable-method answer by adding a genuinely device-informed
subspace update. The current adaptive method widens inside the model Hessian
basis. This pass should use only black-box finite-shot device observations to
estimate additional local directions when the fixed model subspace stalls.

After that method-focused pass is complete, continue with a software-only
completion pass that adds a lightweight invariant/rank-scaling probe so the
report addresses the challenge's three-system `d^2 - 1` question more directly
without claiming a full three-qubit closed-loop calibration.

## Challenge Gap Addressed

Issue #113 says the real research content is deciding when the model Hessian
subspace has become wrong because the true-device relevant directions rotated
away from it. The existing attempt 004 already covers:

- differentiable model optimization;
- dense Hessian and Hessian-vector products;
- query-only noisy simulated device;
- fixed Hessian, full-space, random-subspace, and widen-only adaptive baselines;
- full sweeps over search dimension, mismatch, shots, system size, and seeds;
- failure analysis and hardware-style dry-run artifacts.

The missing method-level piece is device-feedback subspace re-estimation. The
new method should not merely increase `k`; it should spend counted device
queries to learn new directions from measured finite-shot responses.

## Phase 1: Device-Informed Adaptive Subspace

### Method

Add a new black-box local curvature sketch around the current best pulse. Given
a center pulse `theta_center`, an existing model Hessian basis `B`, and a set of
random directions orthogonal to `B`, the method should:

1. Query the device at the center.
2. For each probe direction `q_i`, query paired perturbations
   `theta_center + delta q_i` and `theta_center - delta q_i`.
3. Estimate a noisy directional curvature proxy:

   ```text
   curvature_i = (f_plus + f_minus - 2 f_center) / delta^2
   ```

   where `f_*` are finite-shot infidelity estimates returned by the black-box
   device.
4. Build a positive local sketch:

   ```text
   S = sum_i max(curvature_i, 0) q_i q_i^T
   ```

5. Extract top sketch eigenvectors, orthonormalize them against the model
   Hessian basis, and append the best residual directions.
6. Continue derivative-free optimization in the merged basis while charging all
   probing queries and shots to the same total query budget.

This is not a gradient estimator and it does not inspect the true Hamiltonian.
It is a finite-shot black-box measurement of local curvature in candidate
directions.

### New Module

Create `tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/device_subspace.py`.

It should expose:

- `ProbeConfig(direction_count, append_count, step, repeats, min_positive_curvature)`.
- `ProbeResult(basis, curvatures, query_count, shot_count, selected_count, metadata)`.
- `orthonormalize_against(existing_basis, candidate_basis, tolerance=1e-10)`.
- `random_residual_directions(raw_dim, existing_basis, count, seed)`.
- `estimate_device_subspace(oracle, system_config, center_theta, existing_basis, shots, seed, cfg)`.

`estimate_device_subspace` must accept a `QueryOnlyDevice` instance so the
caller can share query and shot counters across pilot optimization, probing, and
final optimization.

### Baseline Integration

Add a new method in `baselines.py`:

```python
run_device_informed_adaptive_hessian_method(...)
```

It should:

1. Run a pilot Nelder-Mead search in an initial low-dimensional Hessian basis.
2. Decide whether to probe using only the noisy observed pilot result.
3. Spend a fixed, bounded number of remaining queries on paired local probes.
4. Merge model Hessian directions with selected device-informed directions.
5. Continue Nelder-Mead in the merged basis.
6. Return a normal `RunRecord` with extra fields describing:
   - initial Hessian `k`;
   - final merged `k`;
   - whether probing happened;
   - probe directions tested;
   - probe directions selected;
   - probe query count;
   - probe shot count.

The method must keep exact true fidelity inside the audit path only. It may use
the audit evaluator to record success and final infidelity after each query, as
the existing methods do, but not to choose probe directions or decide whether the
method has stalled.

### Focused Research Sweep

Do not add the new method to every default full-sweep cell immediately. That
would expand runtime too much. Add a focused runner:

`run_device_informed_focus.py`

It should compare:

- fixed Hessian subspace;
- existing widen-only adaptive Hessian method;
- new device-informed adaptive method;
- full-space Nelder-Mead;
- random benchmark-rank subspace.

Initial focus cells:

- one-qubit `X`, medium and large mismatch, 2048 shots, 8 seeds;
- two-qubit `CZ`, medium and large mismatch, 2048 shots, 8 seeds.

This directly targets the known failure cases and keeps the compute budget
bounded.

### Analysis Outputs

Extend `analysis.py` and `plotting.py` only where needed to summarize the new
focused run. The required generated outputs should be:

- `device_informed_summary.csv`
- `device_informed_recovery.csv`
- `device_informed_recovery.png`

The report should compare:

- success rate;
- median queries to target;
- median final exact infidelity;
- probe query/shot overhead;
- whether the new method improves over fixed Hessian and widen-only adaptive on
  the medium/large mismatch cases.

### Tests

Add tests in `test_attempt_004_device_subspace.py` and extend smoke tests where
useful.

Required behaviors:

- residual random directions are orthonormal and orthogonal to an existing
  basis;
- paired probing consumes exactly `1 + 2 * direction_count * repeats` queries
  when repeats are configured;
- query and shot counters include probing;
- learned basis columns are orthonormal;
- no exact true-device fidelity, gradients, Hessian, or hidden true Hamiltonian
  are used by the probe routine;
- the new method respects the total query budget;
- the fast focused runner emits records for the new method.

## Phase 2: Best Software-Only Completion Pass

After Phase 1 passes and is reported, add the highest-value software-only
completion that remains feasible locally.

### Lightweight Three-System Invariant Probe

Add a lightweight invariant/rank-scaling probe rather than a full three-qubit
closed-loop calibration. The purpose is to address the challenge's question:
does useful subspace dimension track `d^2 - 1`?

The probe should compare:

- current one-qubit `X`: `d=2`, benchmark rank 3;
- current two-qubit `CZ`: `d=4`, benchmark rank 15;
- a lightweight three-qubit local-chart or controllable-chart probe:
  `d=8`, benchmark rank 63.

The three-qubit probe may use a mathematically controlled local unitary chart
instead of the full closed-loop pulse simulator if the full physical simulation
would be too slow for the current week. It must be labeled clearly as an
invariant sanity probe, not as a real three-qubit calibration.

Required output:

- `invariant_rank_probe.csv`
- `invariant_rank_probe.png`
- report section explaining where the current physical simulator evidence ends
  and where the lightweight chart evidence begins.

### Optional Speed-Limit Stress Probe

If time permits after the invariant probe, add a short-resource stress probe by
reducing segments or amplitude and showing that curvature concentration can drop
or shift when the system is under-resourced. This directly connects to the
issue's warning that the `d^2 - 1` invariant assumes controllability and enough
resources.

This optional probe should be smaller than the device-informed sweep and should
not delay publishing Phase 1.

## Reporting Changes

Update `REPORT.md`, `README.md`, and PR body with:

- clear statement that device-informed subspace re-estimation uses only
  finite-shot black-box values;
- new focused-run tables comparing fixed, widen-only, and device-informed
  adaptive recovery;
- honest result interpretation, including cases where probing overhead does not
  pay off;
- explicit note that no real hardware was used unless measured hardware results
  are later added;
- invariant probe caveat if the three-qubit evidence uses a local chart.

## Verification

Before committing implementation:

```bash
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_device_subspace.py -q
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests/test_attempt_004_*.py -q
python3 -m pytest tracks/qcs/solutions/YueYuan/research/attempt_tests -q
python3 tracks/qcs/solutions/YueYuan/research/validator/self_test.py
python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_candidate.py --fast --out /tmp/yueyuan-attempt004-candidate.json
python3 tracks/qcs/solutions/YueYuan/research/attempts/attempt-004/run_hardware_dry_run.py --out /tmp/yueyuan-attempt004-hardware --shots 256
```

Also run the focused device-informed runner in fast mode and the invariant probe
runner once they exist.

Before publishing, run the local private-marker scan over
`tracks/qcs/solutions/YueYuan` and `docs/superpowers`, and keep `Ion.lock`
unstaged unless the user explicitly asks otherwise.

## Success Criteria

Phase 1 is successful if:

- the new method is implemented with strict query-only device feedback;
- all probe overhead is counted;
- tests prove budget and boundary behavior;
- focused mismatch results show either improved recovery or clear negative
  evidence about when device-informed probing is too noisy or too expensive;
- the report explains the result without overselling it.

Phase 2 is successful if:

- the solution adds a third-system invariant/rank-scaling check;
- any non-physical chart evidence is labeled honestly;
- the report's rating against issue #113 can be increased because the remaining
  gap is mostly real-hardware access rather than missing software science.
