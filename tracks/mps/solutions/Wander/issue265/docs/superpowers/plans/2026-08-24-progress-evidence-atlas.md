# Progress Evidence Atlas Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a provenance-backed, collision-checked scientific figure atlas for the current SCNet convergence results and effective-equation hierarchy.

**Architecture:** An immutable local data snapshot feeds a tested metrics layer, which writes JSON sidecars.  A separate renderer consumes those sidecars through fixed paper, atlas, and presentation layouts.  A QA pass renders every figure at final size and rejects clipping, missing provenance, invalid values, or evidence-language violations.

**Tech Stack:** Python 3.11, NumPy, Matplotlib, h5py for optional checkpoint inspection, pytest, SVG/PDF/PNG output.

## Global Constraints

- Never alter remote SCNet files or authoritative submission records.
- Never treat checkpoint-only trajectories as final NPZ data.
- Call coarse--medium differences numerical envelopes, not confidence intervals.
- Use `not rejected in available domain`, never `validated`, until the frozen gate is accepted.
- Preserve the visual grammar and collision rules in `docs/plans/2026-08-24-progress-evidence-atlas-design.md`.
- Generate separate paper and presentation layouts; do not scale one raster for every use.

---

### Task 1: Immutable SCNet snapshot and manifest

**Files:**
- Create: `artifacts/progress_atlas/source_data/`
- Create: `artifacts/progress_atlas/source_manifest.json`
- Create: `scripts/snapshot_scnet_progress_data.py`
- Test: `tests/test_progress_atlas_snapshot.py`

**Interfaces:**
- Consumes: six final NPZ files, six run summaries, convergence submission JSON, and declared partial-run metrics.
- Produces: `build_manifest(paths: list[Path], root: Path) -> dict` with SHA-256, size, modification time, and relative path.

- [ ] **Step 1: Write the failing manifest test**

```python
def test_manifest_hashes_inputs(tmp_path):
    source = tmp_path / "a.dat"
    source.write_bytes(b"abc")
    manifest = build_manifest([source], tmp_path)
    assert manifest["files"][0]["sha256"] == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `python3 -m pytest -q tests/test_progress_atlas_snapshot.py`

Expected: FAIL because the snapshot module is absent.

- [ ] **Step 3: Implement deterministic hashing and manifest serialization**

Implement sorted relative paths, byte sizes, nanosecond mtimes, SHA-256, and a `generated_at` timestamp.  Reject missing or unreadable inputs.

- [ ] **Step 4: Copy the authorized read-only remote inputs and generate the manifest**

Run the snapshot script with explicit source and output roots.  Do not use glob expansion on the remote shell for destructive operations.

- [ ] **Step 5: Run the snapshot tests**

Run: `python3 -m pytest -q tests/test_progress_atlas_snapshot.py`

Expected: PASS.

### Task 2: Metrics sidecars

**Files:**
- Create: `src/progress_atlas/__init__.py`
- Create: `src/progress_atlas/io.py`
- Create: `src/progress_atlas/metrics.py`
- Create: `artifacts/progress_atlas/metrics/`
- Create: `tests/test_progress_atlas_metrics.py`

**Interfaces:**
- Consumes: NPZ arrays with `x`, `t`, `m`, `current`, optional `czz`, `fcs_gamma`, and `fcs_logZ`.
- Produces: `profile_error(reference, candidate, background, mask) -> dict`, `spin_flip_metrics(up, down) -> dict`, `continuity_residual(data) -> dict`, and JSON sidecars containing only finite scalars and downsampled curves.

- [ ] **Step 1: Write failing tests for profile and spin-flip metrics**

```python
def test_profile_error_is_zero_for_equal_arrays():
    a = np.array([[1.0, 2.0]])
    result = profile_error(a, a, 0.0, np.array([True, True]))
    assert result["relative_l2"][0] == 0.0

def test_spin_flip_residual_vanishes_for_opposites():
    up = np.array([[1.0, -2.0]])
    down = -up
    result = normalized_even_odd_residual(up, down)
    assert result[0] == 0.0
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `python3 -m pytest -q tests/test_progress_atlas_metrics.py`

- [ ] **Step 3: Implement coordinate alignment and finite-domain checks**

Require exact common coordinates and monotone time axes.  Reject extrapolation, nonfinite arrays, empty masks, and mismatched physical observables.

- [ ] **Step 4: Serialize the coverage, convergence, symmetry, FCS, and resource sidecars**

Sidecars record definitions and source hashes, not only plotted values.

- [ ] **Step 5: Run the metrics tests**

Run: `python3 -m pytest -q tests/test_progress_atlas_metrics.py`

Expected: PASS.

### Task 3: Visual system and collision QA

**Files:**
- Create: `src/progress_atlas/style.py`
- Create: `src/progress_atlas/layout.py`
- Create: `src/progress_atlas/qa.py`
- Create: `tests/test_progress_atlas_style.py`

**Interfaces:**
- Produces: `apply_style(target: Literal["paper", "atlas", "presentation"])`, `make_figure(template: str, target: str)`, and `audit_figure(fig, evidence: dict) -> list[str]`.

- [ ] **Step 1: Write failing tests for palettes, font floors, and evidence status**

```python
def test_paper_font_floor_is_seven_points():
    assert STYLE_TARGETS["paper"].min_font_size >= 7.0

def test_unaccepted_gate_cannot_use_verified_label():
    errors = audit_evidence_text("verified", gate_accepted=False)
    assert errors
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `python3 -m pytest -q tests/test_progress_atlas_style.py`

- [ ] **Step 3: Implement fixed grids, legend rails, and typography fallbacks**

Measure text using the final renderer.  Keep legends outside data axes and cap major ticks at six.

- [ ] **Step 4: Implement overlap and clipping checks**

Collect visible text bounding boxes after `canvas.draw()`.  Ignore intentional axis-title relationships but reject intersections between free annotations, legends, and the canvas boundary.

- [ ] **Step 5: Run style tests**

Run: `python3 -m pytest -q tests/test_progress_atlas_style.py`

Expected: PASS.

### Task 4: Visual specimen and first four hero figures

**Files:**
- Create: `src/progress_atlas/figures.py`
- Create: `scripts/build_progress_evidence_atlas.py`
- Create: `artifacts/progress_atlas/figures/hero/`
- Create: `artifacts/progress_atlas/figure_manifest.json`
- Test: `tests/test_progress_atlas_figures.py`

**Interfaces:**
- Consumes: metrics sidecars and style targets.
- Produces: specimen sheet plus Hero 1--4 as PNG, PDF, and SVG.

- [ ] **Step 1: Write a failing smoke test for required figure outputs**

```python
def test_core_hero_figure_names():
    assert set(core_hero_names()) == {
        "01_evidence_map",
        "02_time_coverage",
        "03_profile_current_convergence",
        "04_initial_state_dynamics",
    }
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `python3 -m pytest -q tests/test_progress_atlas_figures.py`

- [ ] **Step 3: Implement the specimen sheet and data-driven hero figures**

Use conclusion titles, a dedicated legend rail, shared physical limits, and explicit evidence badges.  Do not display checkpoint trajectories.

- [ ] **Step 4: Render paper and presentation targets**

Run: `python3 scripts/build_progress_evidence_atlas.py --targets paper,presentation --groups specimen,hero-core`

- [ ] **Step 5: Audit final-size renders**

Run the figure QA, inspect every PNG, and reject overlap, clipping, misleading scales, or illegible labels.

### Task 5: Symmetry, scaling, closure, and theory heroes

**Files:**
- Modify: `src/progress_atlas/figures.py`
- Modify: `scripts/build_progress_evidence_atlas.py`
- Create: `artifacts/progress_atlas/figures/hero/05_*` through `08_*`
- Modify: `tests/test_progress_atlas_figures.py`

**Interfaces:**
- Produces: Hero 5--8 and their caption/provenance records.

- [ ] **Step 1: Add failing output-name and evidence-language tests**
- [ ] **Step 2: Implement spin-flip, scaling-competition, closure-memory, and hierarchy figures**
- [ ] **Step 3: Render all targets and run collision QA**
- [ ] **Step 4: Visually inspect at paper width and 4K size**
- [ ] **Step 5: Run all progress-atlas tests**

Run: `python3 -m pytest -q tests/test_progress_atlas_*.py`

### Task 6: Evidence plates and forensic appendix

**Files:**
- Create: `src/progress_atlas/plates.py`
- Create: `artifacts/progress_atlas/figures/plates/`
- Create: `artifacts/progress_atlas/figures/forensic/`
- Create: `tests/test_progress_atlas_plates.py`

**Interfaces:**
- Produces: A3 evidence plates and single-question forensic figures from the same sidecars.

- [ ] **Step 1: Write failing tests for plate footer fields and shared limits**
- [ ] **Step 2: Implement numerical reliability and initial-state plate templates**
- [ ] **Step 3: Implement window-sensitivity, raw-difference, continuity, and FCS forensic groups**
- [ ] **Step 4: Render and audit every figure**
- [ ] **Step 5: Run the complete test suite**

### Task 7: Atlas index, captions, animations, and interactive overview

**Files:**
- Create: `artifacts/progress_atlas/README.md`
- Create: `artifacts/progress_atlas/captions/`
- Create: `scripts/build_progress_atlas_animation.py`
- Create: `scripts/build_progress_atlas_html.py`
- Create: `artifacts/progress_atlas/animation/`
- Create: `artifacts/progress_atlas/interactive/index.html`

**Interfaces:**
- Consumes: figure manifest and metrics sidecars.
- Produces: searchable atlas index, two fixed-layout animations, and an offline interactive viewer that never extrapolates unavailable times.

- [ ] **Step 1: Generate bilingual captions and a figure-to-source index**
- [ ] **Step 2: Build fixed-axis profile and double-wall animations**
- [ ] **Step 3: Build the offline initial-state/resolution/observable/time selector**
- [ ] **Step 4: Verify unavailable selections display `not available`**
- [ ] **Step 5: Run final provenance, collision, font, grayscale, and evidence-language audits**

### Task 8: Documentation and final verification

**Files:**
- Modify: `project_summary.md`
- Modify: `README.md`
- Create: `artifacts/progress_atlas/verification.json`

**Interfaces:**
- Produces: reproduction commands and the final machine-readable verification result.

- [ ] **Step 1: Document snapshot, metrics, rendering, and audit commands**
- [ ] **Step 2: Run focused atlas tests**

Run: `python3 -m pytest -q tests/test_progress_atlas_*.py`

- [ ] **Step 3: Run repository regression tests relevant to the plotted theory hierarchy**

Run: `python3 -m pytest -q tests/test_running_field_full_matrix_wall.py tests/test_low_rank_self_consistent_full_matrix.py tests/test_match_full_matrix_memory_to_exact_mori.py`

- [ ] **Step 4: Compile all new Python files**

Run: `python3 -m compileall -q src/progress_atlas scripts/build_progress_*`

- [ ] **Step 5: Record final hashes, renderer versions, pass/fail status, and known unavailable panels in `verification.json`**
