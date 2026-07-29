# Phase 7 Crossover Scan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a documented, costed, deterministic, and resumable two-pass
planner for the low-cost long-range TFIM sigma scan without running DMRG.

**Architecture:** Add a pure `phase7_protocol` module that owns immutable
grids, cell identifiers, crossing decisions, quality flags, gap interpolation,
and cost estimates. A thin CLI serializes broad, refinement, and gap plans.
The existing checkpointed direct-sector runner remains the compute
entrypoint; this implementation only prepares and audits work.

**Tech Stack:** Python 3.11, NumPy, JSON, TeNPy result manifests, pytest.

## Global Constraints

- Hamiltonian and rotated operator convention remain unchanged.
- Exploration uses `K=24`, `chi=64`, and `L=32,64`.
- Broad axes are exactly `sigma={1.50,1.60,1.70,1.75,1.80,1.90,2.00}` and
  `Gamma=1.20:0.05:1.90`.
- Refinement uses the unique observed broad bracket at spacing `0.01`.
- No adaptive Gamma optimization or automatic grid expansion is permitted.
- `K=32`, `chi=128`, `chi=256`, and `L>=128` are not exploration defaults.
- Exact-zero pruning, checkpoints, full raw observables, and no approximate
  MPO compression remain mandatory.
- This plan must not execute a DMRG cell.

---

### Task 1: Document the Phase 7 workflow

**Files:**
- Modify: `README.md`
- Modify: `docs/methodology.md`
- Modify: `scripts/README.md`

**Interfaces:**
- Consumes: approved `docs/phase7-crossover-scan-design.md`
- Produces: user-facing scope and planner commands

- [ ] **Step 1: Add documentation assertions**

Extend a documentation test in `tests/test_phase7_protocol.py` that reads the
three files and asserts they contain:

```python
for token in (
    "validated local reproduction",
    "sigma=1.50,1.60,1.70,1.75,1.80,1.90,2.00",
    "K=24",
    "chi=64",
    "no thermodynamic-limit",
):
    assert token in combined_docs
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
PYTHONPATH=src:. conda run -n mps pytest -q \
  tests/test_phase7_protocol.py::test_phase7_documentation_declares_exploration_scope
```

Expected: failure because Phase 7 is not yet described consistently.

- [ ] **Step 3: Update the documents**

State that Phase 6 established the local `sigma=1.75`, `L<=64` validation,
while Phase 7 maps crossover behavior. Include the common broad grid,
deterministic refinement, selective `chi=128` flag policy, uncertainty
separation, planner-only commands, and the explicit absence of a
thermodynamic-limit claim.

- [ ] **Step 4: Run the documentation test**

Run the command from Step 2. Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add README.md docs/methodology.md scripts/README.md \
  tests/test_phase7_protocol.py
git commit -m "docs: describe phase7 crossover exploration"
```

---

### Task 2: Implement immutable broad-scan planning

**Files:**
- Create: `src/lrtfim/phase7_protocol.py`
- Modify: `src/lrtfim/__init__.py`
- Modify: `tests/test_phase7_protocol.py`

**Interfaces:**
- Produces:
  - `SIGMAS: tuple[float, ...]`
  - `SIZES: tuple[int, ...]`
  - `broad_gamma_grid() -> np.ndarray`
  - `grid_hash(values: Sequence[float]) -> str`
  - `build_broad_spec(fit_records, output_dir) -> dict`

- [ ] **Step 1: Write failing broad-grid tests**

Test exact axes, 210 cells, even sectors only, stable unique IDs, common grid
hash, `K=24`, `chi=64`, and rejection of a fit map missing any sigma:

```python
spec = build_broad_spec(fit_records=fit_records, output_dir=tmp_path)
assert len(spec["cells"]) == 7 * 2 * 15
assert {cell["sector"] for cell in spec["cells"]} == {"even"}
assert {cell["chi"] for cell in spec["cells"]} == {64}
assert len({cell["cell_id"] for cell in spec["cells"]}) == 210
assert len({cell["grid_hash"] for cell in spec["cells"]}) == 1
```

- [ ] **Step 2: Verify the tests fail**

```bash
PYTHONPATH=src:. conda run -n mps pytest -q \
  tests/test_phase7_protocol.py -k "broad or grid_hash"
```

Expected: import failure for `lrtfim.phase7_protocol`.

- [ ] **Step 3: Implement the immutable protocol**

Generate decimal-safe grids with integer ticks, encode sigma as three
decimal places and Gamma as two decimal places in IDs, and hash canonical
compact JSON:

```python
def grid_hash(values):
    payload = json.dumps([float(x) for x in values], separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()
```

Require each fit record to include `path`, `fit_hash`, `coefficient_hash`,
`K=24`, `alpha=0.5`, `r_fit=2048`, and matching sigma. Put correctness
settings in the shared run specification and echo their IDs into cells.

- [ ] **Step 4: Run the protocol tests**

Run the Step 2 command. Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/lrtfim/phase7_protocol.py src/lrtfim/__init__.py \
  tests/test_phase7_protocol.py
git commit -m "feat: plan immutable phase7 broad scan"
```

---

### Task 3: Implement crossing decisions and selective validation flags

**Files:**
- Modify: `src/lrtfim/phase7_protocol.py`
- Modify: `tests/test_phase7_protocol.py`

**Interfaces:**
- Produces:
  - `quality_flags(summary: Mapping) -> list[dict]`
  - `decide_refinement(sigma, broad_spec, manifests) -> dict`
  - `build_gap_spec(decisions, manifests, output_dir) -> dict`

- [ ] **Step 1: Write failing quality-flag tests**

Cover each approved trigger independently:

```python
assert quality_flags(nonconverged)[0]["code"] == "dmrg_nonconverged"
assert "relative_variance" in codes(quality_flags(high_variance))
assert "discarded_weight" in codes(quality_flags(high_discarded))
assert "invalid_second_moment" in codes(quality_flags(s_zero_below_s_k))
assert "nonpositive_gap" in codes(quality_flags(reversed_sectors))
```

Also assert a flag never mutates chi, status, Gamma axes, or schedules.

- [ ] **Step 2: Write failing refinement tests**

Use synthetic broad manifests to test:

- a unique `[1.50,1.55]` sign change produces
  `[1.50,1.51,1.52,1.53,1.54,1.55]`;
- no sign change yields `unresolved_no_bracket`;
- two sign changes yield `unresolved_multiple_brackets`;
- a missing cell yields `incomplete`;
- the final refined interpolation records both endpoints and
  `delta_gamma_grid=0.005`;
- unresolved cases produce no gap cells.

- [ ] **Step 3: Run tests and verify failure**

```bash
PYTHONPATH=src:. conda run -n mps pytest -q \
  tests/test_phase7_protocol.py -k "quality or refinement or gap_spec"
```

- [ ] **Step 4: Implement pure decision functions**

Use strict ascending adjacent-pair inspection. Never call an optimizer or
construct points outside the observed bracket. Store the broad grid, grid
hash, every signed difference, decision reason, refinement values, and final
interpolation inputs. Compute

```python
delta_gamma_grid = 0.5 * (gamma_b - gamma_a)
```

and interpolate endpoint gaps to the common crossing before calling the
existing `effective_z`.

- [ ] **Step 5: Run tests**

Run the Step 3 command. Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add src/lrtfim/phase7_protocol.py tests/test_phase7_protocol.py
git commit -m "feat: audit phase7 crossing decisions"
```

---

### Task 4: Add an evidence-based local cost model

**Files:**
- Modify: `src/lrtfim/phase7_protocol.py`
- Modify: `tests/test_phase7_protocol.py`

**Interfaces:**
- Produces:
  - `estimate_scan_cost(timing_records, broad_spec) -> dict`

- [ ] **Step 1: Write failing cost-model tests**

Provide synthetic `chi=128` L32/L64 even/odd timings and assert:

```python
estimate = estimate_scan_cost(records, spec)
assert estimate["scaling"]["time_chi_factor"] == pytest.approx((64 / 128) ** 3)
assert estimate["scaling"]["memory_chi_factor"] == pytest.approx((64 / 128) ** 2)
assert estimate["stages"]["broad"]["cells"] == 210
assert estimate["stages"]["refinement"]["maximum_new_even_cells"] == 56
assert estimate["stages"]["gaps"]["maximum_odd_cells"] == 28
assert estimate["safety_factor"] == 2.0
```

Reject missing L32/L64 calibration records and nonpositive timing or memory.

- [ ] **Step 2: Verify failure**

```bash
PYTHONPATH=src:. conda run -n mps pytest -q \
  tests/test_phase7_protocol.py -k cost
```

- [ ] **Step 3: Implement the estimator**

Use median measured wall time and peak memory per `(L,sector)` at `chi=128`.
Scale time by `(64/128)^3`, memory by `(64/128)^2`, and report central and
two-times safety estimates. Report broad, maximum refinement, targeted-gap,
and combined totals separately. Preserve calibration paths, code hashes,
hardware records, sample counts, and formulas in the JSON output.

- [ ] **Step 4: Run tests**

Run the Step 2 command. Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/lrtfim/phase7_protocol.py tests/test_phase7_protocol.py
git commit -m "feat: estimate local phase7 scan cost"
```

---

### Task 5: Add the resumable planner CLI

**Files:**
- Create: `scripts/plan_phase7_scan.py`
- Create: `tests/test_phase7_planner_cli.py`
- Modify: `scripts/README.md`

**Interfaces:**
- Consumes: `phase7_protocol` pure functions
- Produces:
  - `broad/run_spec.json`
  - `broad/cost-estimate.json`
  - `decisions/sigma-<value>.json`
  - `refinement/run_spec.json`
  - `gaps/run_spec.json`

- [ ] **Step 1: Write failing CLI tests**

Test four explicit subcommands:

```text
plan_phase7_scan.py broad
plan_phase7_scan.py decide
plan_phase7_scan.py gaps
plan_phase7_scan.py estimate
```

The fixture `broad` command must write 210 pending cells and executable
argument arrays that call the existing checkpointed runner with
`--direct-only --sectors even --chi-schedule 64`. `decide` must reuse
successful compatible endpoints, leave failures visible, and refuse to
overwrite a decision whose input hashes differ. `gaps` must schedule only
the two accepted interpolation endpoints in the odd sector.

- [ ] **Step 2: Verify CLI tests fail**

```bash
PYTHONPATH=src:. conda run -n mps pytest -q \
  tests/test_phase7_planner_cli.py
```

- [ ] **Step 3: Implement atomic serialization**

Write JSON to a sibling `.tmp`, flush and replace the destination. Print one
flushed progress line per sigma. The CLI only plans and inspects manifests;
it must not import the TeNPy DMRG engine or invoke subprocesses.

- [ ] **Step 4: Run CLI and protocol tests**

```bash
PYTHONPATH=src:. conda run -n mps pytest -q \
  tests/test_phase7_protocol.py tests/test_phase7_planner_cli.py
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/plan_phase7_scan.py scripts/README.md \
  tests/test_phase7_planner_cli.py
git commit -m "feat: add resumable phase7 scan planner"
```

---

### Task 6: Generate and audit the proposal artifacts

**Files:**
- Generate: `results/phase7-crossover/proposal/broad/run_spec.json`
- Generate: `results/phase7-crossover/proposal/broad/cost-estimate.json`
- Generate: `results/phase7-crossover/proposal/review-summary.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: independently regenerated K24 fit records for all seven sigmas
  and measured Phase 6 local timing manifests
- Produces: reviewable cell count and resource estimate; no state data

- [ ] **Step 1: Regenerate and validate fit metadata only**

Use the existing fit regeneration command for each sigma with
`K=24`, `alpha=0.5`, and `r_fit=2048`. This is CPU fitting, not DMRG. Record
the fit and coefficient hashes and require the established coupling-error
summary before accepting each fit into `fit-map.json`.

- [ ] **Step 2: Run the broad planner**

```bash
PYTHONPATH=src:. conda run -n mps python -u scripts/plan_phase7_scan.py broad \
  --fit-map results/phase7-crossover/proposal/fit-map.json \
  --output results/phase7-crossover/proposal/broad/run_spec.json
```

Expected: exactly 210 pending even-sector cells and no DMRG output.

- [ ] **Step 3: Generate the cost estimate**

```bash
PYTHONPATH=src:. conda run -n mps python -u scripts/plan_phase7_scan.py estimate \
  --run-spec results/phase7-crossover/proposal/broad/run_spec.json \
  --timing-root results/phase6_sigma1.75/validated-local-reproduction \
  --output results/phase7-crossover/proposal/broad/cost-estimate.json
```

- [ ] **Step 4: Audit the proposal**

Assert the cell count, common grid hash, no `L>64`, no `chi>64`, no `K>24`,
even-only broad cells, no approximate compression, and zero created HDF5
files. Summarize central/safety wall time and peak memory in
`review-summary.md`.

- [ ] **Step 5: Run the full test suite**

```bash
PYTHONPATH=src:. conda run -n mps pytest -q tests
```

Expected: all tests pass.

- [ ] **Step 6: Stop at the review gate**

Present `run_spec.json`, `cost-estimate.json`, and `review-summary.md`.
Do not execute any cell command until the user reviews the proposal.

- [ ] **Step 7: Commit**

```bash
git add README.md
git add -f results/phase7-crossover/proposal
git commit -m "docs: prepare phase7 crossover proposal"
```
