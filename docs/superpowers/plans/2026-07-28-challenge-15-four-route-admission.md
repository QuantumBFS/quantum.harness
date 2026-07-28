# Challenge #15 Four-Route Admission Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Admit Route D and add the missing reveal-only ED-fidelity metric without changing any physics, training, sampling, gate, or resource budget, then publish one exact comparison base for Routes A-D.

**Architecture:** This is an additive Step 1 amendment. It adds one route-capacity record and a common post-audit overlap estimator that evaluates all routes only after ED reveal. The protocol changes only in the Route D capacity map; no training, sampling, threshold, gate, or resource value changes. It does not implement a candidate, expose ED data before freeze, or consume a Step 2 attempt.

**Tech Stack:** Python 3.11+, JSON, pytest, Git worktrees, existing `scalable_v1.protocol` loader.

---

## Immutable boundary

- Start from the planning branch containing this document and the approved four-route design.
- Preserve common ancestor `78577cd8f70adf918648fb02962e3b7bc09255e8`.
- Do not change `physics`, `training`, `sampling`, `symmetry`, `oracle`, `resources`, or `smoke_n8`.
- Add exactly one capacity key: `analytic_seed_correlator`.
- Freeze exactly `operator_layers=2`, `density_ranks=[2,3,4]`, and `hidden_width=64`.
- Add normalized ED fidelities as reveal-only continuous metrics; do not create
  an overlap hard gate or use fidelity for training/checkpoint selection.
- Run in worktree `D:/Playground/worktrees/quantum.harness/challenge-qmc-chiral-graviton-scalable-v1-route-admission` on branch `challenge/qmc-chiral-graviton-scalable-v1-route-admission`.

### Task 1: Add the Route D protocol contract with TDD

**Files:**
- Modify: `tracks/qmc/solutions/BOTS-848/tests/test_scalable_protocol.py`
- Modify: `tracks/qmc/solutions/BOTS-848/scalable_v1/protocol.json`

- [ ] **Step 1: Create the isolated amendment worktree**

```powershell
git worktree add `
  D:/Playground/worktrees/quantum.harness/challenge-qmc-chiral-graviton-scalable-v1-route-admission `
  -b challenge/qmc-chiral-graviton-scalable-v1-route-admission `
  challenge/qmc-chiral-graviton-scalable-v1-parallel-design
```

Expected: the new worktree contains this plan, the four-route design, and no route implementation.

- [ ] **Step 2: Write the failing capacity test**

Replace the route-set assertion in `test_protocol_freezes_route_capacity_and_n8_smoke` and add the exact Route D assertion:

```python
assert set(p.capacity["routes"]) == {
    "occupation_autoregressive",
    "continuous_holomorphic",
    "cf_flow_l2",
    "analytic_seed_correlator",
}
assert p.capacity["routes"]["analytic_seed_correlator"] == {
    "operator_layers": 2,
    "density_ranks": [2, 3, 4],
    "hidden_width": 64,
}
```

- [ ] **Step 3: Run RED**

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/test_scalable_protocol.py::test_protocol_freezes_route_capacity_and_n8_smoke -q
```

Expected: FAIL because `analytic_seed_correlator` is absent from `protocol.json`.

- [ ] **Step 4: Add the exact JSON capacity record**

Change only `capacity.routes` so that its logical content is:

```json
{
  "occupation_autoregressive": {"hidden_width": 128, "hidden_layers": 2},
  "continuous_holomorphic": {"determinant_rank": 64, "generator_hidden_width": 64},
  "cf_flow_l2": {"flow_layers": 4, "hidden_width": 64},
  "analytic_seed_correlator": {
    "operator_layers": 2,
    "density_ranks": [2, 3, 4],
    "hidden_width": 64
  }
}
```

Do not reformat or mutate any other protocol section.

- [ ] **Step 5: Run GREEN and the immutability regression**

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/test_scalable_protocol.py -q
git diff --check
```

Expected: the protocol tests pass and `git diff --check` is silent.

- [ ] **Step 6: Commit the additive contract**

```powershell
git add tracks/qmc/solutions/BOTS-848/scalable_v1/protocol.json `
        tracks/qmc/solutions/BOTS-848/tests/test_scalable_protocol.py
git commit -m "feat(qmc): admit analytic seed correlator route"
```

### Task 2: Add a route-independent reveal-only ED fidelity

**Files:**
- Create: `tracks/qmc/solutions/BOTS-848/scalable_v1/overlap.py`
- Modify: `tracks/qmc/solutions/BOTS-848/scalable_v1/evaluator.py`
- Modify: `tracks/qmc/solutions/BOTS-848/tests/test_scalable_evaluator.py`

- [ ] **Step 1: Write RED tests for normalized fidelity and reveal ordering**

```python
def test_normalized_fidelity_is_scale_invariant_and_exact_for_identical_state():
    candidate = np.array([1.0, 1.0j]) / np.sqrt(2.0)
    assert normalized_fidelity(candidate, 7.0j * candidate) == pytest.approx(1.0)

def test_orthogonal_state_has_zero_fidelity():
    candidate = np.array([1.0, 1.0]) / np.sqrt(2.0)
    oracle = np.array([1.0, -1.0]) / np.sqrt(2.0)
    assert normalized_fidelity(candidate, oracle) == pytest.approx(0.0, abs=1e-15)

def test_tampered_manifest_stops_before_overlap_oracle_build(tmp_path):
    calls = []
    with pytest.raises(ValueError, match="manifest audit failed"):
        evaluate_candidate(..., overlap_oracle_builder=lambda physics: calls.append(physics))
    assert calls == []
```

Run:

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/test_scalable_evaluator.py -q
```

Expected: FAIL because `normalized_fidelity` and the post-audit builder do not exist.

- [ ] **Step 2: Implement a stable importance-sampled fidelity estimator**

For samples `x~|psi_candidate|^2`, use `r=psi_ED(x)/psi_candidate(x)` and
`F=|mean(r)|^2/mean(|r|^2)`. The denominator removes the candidate's unknown
normalization because the ED state is normalized.

```python
@dataclass(frozen=True)
class FidelityEstimate:
    mean: float
    standard_error: float
    effective_sample_size: float

def normalized_fidelity(candidate_amplitude, oracle_amplitude):
    ratios = np.asarray(oracle_amplitude) / np.asarray(candidate_amplitude)
    return float(abs(np.mean(ratios))**2 / np.mean(abs(ratios)**2))

def fidelity_from_log_amplitudes(candidate_logpsi, oracle_amplitude, block_size):
    finite = np.isfinite(candidate_logpsi) & np.isfinite(oracle_amplitude)
    if not np.all(finite):
        raise ValueError("overlap amplitudes must be finite")
    log_scale = np.max(np.log(np.maximum(abs(oracle_amplitude), 1e-300)) - np.real(candidate_logpsi))
    ratios = oracle_amplitude * np.exp(-candidate_logpsi - log_scale)
    blocks = ratios.reshape(-1, block_size)
    block_fidelity = abs(blocks.mean(axis=1))**2 / np.mean(abs(blocks)**2, axis=1)
    return FidelityEstimate(
        mean=float(np.mean(block_fidelity)),
        standard_error=float(np.std(block_fidelity, ddof=1) / np.sqrt(len(block_fidelity))),
        effective_sample_size=float(len(ratios)),
    )
```

Use `minimum_ess_per_state=4096` existing samples per state and the existing
`block_size=256`; no new sampling budget is introduced.

- [ ] **Step 3: Build the ED amplitude only after manifest audit**

`build_ed_amplitude_oracle(physics)` may use the full `N=6` basis and ED
vectors because it is called after the freeze audit. For integer occupation
configs it returns the selected ED coefficient. For sphere-spinor configs it
evaluates `sum_alpha c_alpha det(phi_{occupied_alpha}(z))` in batches.

```python
def evaluate_overlaps(candidate, protocol, oracle):
    states = {"ground": candidate.ground_state(), **{str(m): s for m, s in candidate.generate_multiplet().items()}}
    estimates = {}
    for index, (label, state) in enumerate(states.items()):
        batch = state.sample(int(protocol.sampling["minimum_ess_per_state"]), int(protocol.symmetry["seed"]) + 1000*index)
        estimate = fidelity_from_log_amplitudes(
            np.asarray(state.logpsi(batch.configs)), oracle.amplitude(label, batch.configs),
            int(protocol.sampling["block_size"]),
        )
        estimates[label] = asdict(estimate)
    return estimates
```

- [ ] **Step 4: Merge overlap fields into `ed_comparison` without a new gate**

Call the overlap builder only after `verify_manifest` succeeds and after the
progress line `reveal: loading ED oracle after audit`. Add:

```python
revealed["ed_comparison"].update(
    ground_fidelity=overlaps.pop("ground"),
    l2_fidelity_by_m=overlaps,
    minimum_l2_fidelity=min(item["mean"] for item in overlaps.values()),
    overlap_wall_seconds=overlap_meter.wall_seconds,
)
```

`ed_crosscheck_valid` remains the frozen energy-consistency gate. Fidelity is
never read by a trainer and never changes a boolean gate.

- [ ] **Step 5: Run GREEN, ordering tests, and commit**

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests/test_scalable_evaluator.py tracks/qmc/solutions/BOTS-848/tests/test_scalable_gates.py -q
git diff --check
git add tracks/qmc/solutions/BOTS-848/scalable_v1/overlap.py tracks/qmc/solutions/BOTS-848/scalable_v1/evaluator.py tracks/qmc/solutions/BOTS-848/tests/test_scalable_evaluator.py
git commit -m "feat(qmc): report reveal-only ED fidelities"
```

### Task 3: Prove that no frozen budget drifted

**Files:**
- Create: `tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s01-route-d-admission.md`

- [ ] **Step 1: Compare protocol sections against the parent commit**

Run this exact read-only check:

```powershell
python -c "import json,subprocess,pathlib; p=pathlib.Path(r'tracks/qmc/solutions/BOTS-848/scalable_v1/protocol.json'); new=json.loads(p.read_text()); old=json.loads(subprocess.check_output(['git','show','HEAD^^:'+p.as_posix()], text=True)); changed=[k for k in new if new[k]!=old[k]]; print(changed); assert changed==['capacity']; assert new['capacity']['max_trainable_parameters']==old['capacity']['max_trainable_parameters']; assert {k:v for k,v in new['capacity']['routes'].items() if k!='analytic_seed_correlator'}==old['capacity']['routes']"
```

Expected: `['capacity']`.

- [ ] **Step 2: Run the full scoped suite and forbidden-import check**

```powershell
python -m pytest tracks/qmc/solutions/BOTS-848/tests -q
rg -n --glob '!protocol.json' --glob '!overlap.py' "benchmark_v0\.(ed_oracle|fock_ed|projected_nqs|nqs_benchmark)" `
  tracks/qmc/solutions/BOTS-848/scalable_v1 `
  tracks/qmc/solutions/BOTS-848/run_scalable_evaluator.py
```

Expected: all BOTS:848 tests pass. `rg` exits `1` with no match.

- [ ] **Step 3: Record the exact new base and protocol hashes**

```powershell
python -c "import sys; sys.path.insert(0,r'tracks/qmc/solutions/BOTS-848'); from scalable_v1.protocol import load_protocol; print(load_protocol().sha256)"
git rev-parse HEAD
git merge-base --is-ancestor 78577cd8f70adf918648fb02962e3b7bc09255e8 HEAD
```

Write `s01-route-d-admission.md` with two machine-readable lines matching:

```text
^comparison_base_sha: `[0-9a-f]{40}`$
^protocol_sha256: `[0-9a-f]{64}`$
```

Follow them with the test count, command exits, changed-section result, and classification
`common-amendment-pass`. `comparison_base_sha` is the literal `git rev-parse
HEAD` printed after Task 1's additive protocol commit. The journal is a child
documentation commit and is not part of that recorded code base; this avoids
an impossible self-referential commit hash. State that the admission consumes
no `s02*` attempt.

- [ ] **Step 4: Commit the admission journal**

```powershell
git add tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s01-route-d-admission.md
git commit -m "docs(qmc): record four-route comparison base"
git show HEAD^:tracks/qmc/solutions/BOTS-848/scalable_v1/protocol.json | Out-Null
```

Expected: `HEAD^` is exactly the journaled `comparison_base_sha`; only the
journal file differs between `HEAD^` and `HEAD`.

### Task 4: Publish the one comparison base

**Files:**
- No new files.

- [ ] **Step 1: Verify the branch is clean and scoped**

```powershell
git status --short
git diff --name-only 78577cd8f70adf918648fb02962e3b7bc09255e8..HEAD
```

Expected: clean status; the diff contains the approved design/plans, the Route D capacity test/JSON entry, the common reveal-only overlap estimator, and the admission journal, with no candidate code or result data. Route worktrees start from the journaled `HEAD^` code SHA, while the collaboration branch may point at the journal child commit.

- [ ] **Step 2: Update the public comparison branch without force**

```powershell
git push collab HEAD:collab/challenge-15-scalable-v1
```

Expected: fast-forward succeeds. Record the remote SHA with:

```powershell
git ls-remote collab refs/heads/collab/challenge-15-scalable-v1
```

- [ ] **Step 3: Gate all four route starts on the remote SHA**

Before creating any `s02[a-d]-a01` worktree, require:

```powershell
git fetch collab collab/challenge-15-scalable-v1
git rev-parse FETCH_HEAD
$journal = git show "FETCH_HEAD:tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s01-route-d-admission.md"
$match = $journal | Select-String '^comparison_base_sha: `([0-9a-f]{40})`$'
$routeBase = $match.Matches.Groups[1].Value
git merge-base --is-ancestor $routeBase FETCH_HEAD
git diff --exit-code $routeBase..FETCH_HEAD -- . ':(exclude)tracks/qmc/solutions/BOTS-848/logs/scalable-v1/s01-route-d-admission.md'
```

Expected: the fetched branch head is the journal child commit; the parsed
`$routeBase` is its ancestor and the only later tree change is the admission
journal. Every route worktree starts at `$routeBase` and every route journal
copies that exact value.

## Acceptance checklist

- [ ] The only protocol drift is the additive Route D capacity mapping.
- [ ] Ground and five `L=2,M` normalized ED fidelities are reported only after
      audit/reveal, with errors and wall time, and affect no hard gate.
- [ ] All four routes are accepted by `freeze_manifest`/`verify_manifest`.
- [ ] Physics, seeds, optimizer/sample budgets, gates, and resource ceilings are byte-logically unchanged.
- [ ] The full BOTS:848 suite passes.
- [ ] The remote collaboration branch has one exact four-route comparison SHA.
- [ ] No route code, ED value, checkpoint, credential, or secret is included.
