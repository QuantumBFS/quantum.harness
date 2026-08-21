# Phase 6 Validated Local Reproduction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a bounded `sigma=1.75`, `L<=64` reproduction with separately measured MPS (`chi=128` versus `256`) and MPO (`K=24` versus `32`) uncertainties.

**Architecture:** Extend the existing checkpointed cell runner rather than creating a second DMRG implementation. Pure analysis code reads completed cell summaries and coupling profiles, calculates fixed-bracket shifts, and writes machine-readable tables before the final report. Compute cells remain independent and resumable.

**Tech Stack:** Python 3.11, TeNPy, NumPy, SciPy, h5py/HDF5, pytest, matplotlib.

## Global Constraints

- Use `H = -sum J_L Z_phys Z_phys - Gamma sum X_phys` with the pinned periodic Hurwitz-zeta finite-ring coupling at `sigma=1.75`.
- In the rotated TeNPy basis, use `X_phys -> Sigmaz`, `Z_phys -> Sigmax`, even parity for the ground state, and odd parity for the first excitation.
- Use the full correlation function without connected-correlation subtraction.
- Never run `L>64`, Slurm, `chi>256`, an expanded Gamma grid, or approximate MPO compression.
- Preserve exact-zero MPO pruning and provenance-safe HDF5 checkpoints.
- Permit a differing checkpoint code hash only for audited initialization;
  all physical/structural fingerprints must match and current-code DMRG must
  fully reoptimize the state.
- The MPS comparison is `K=24`, `L=64`, `Gamma={1.560,1.565}`, `chi={128,256}`.
- The MPO comparison is `K={24,32}`, `L={32,64}`, `Gamma={1.560,1.565}`, with direct `chi=128`.
- Compute crossings by linear interpolation of `R_xi(L,Gamma)-R_xi(2L,Gamma)` on the fixed bracket.
- If K=32 cost is limiting, prioritize L=64 and label the two-size crossing incomplete.
- Do not judge stability by agreement with published thermodynamic-limit values.

---

### Task 1: Select an explicit exponential fit from a regenerated summary

**Files:**
- Modify: `scripts/benchmark_phase6_optimizations.py`
- Test: `tests/test_phase6_optimization_benchmark.py`

**Interfaces:**
- Consumes: the existing `regenerate_sigma_fits(...)` JSON schema.
- Produces: `select_fit(summary: dict, num_exponentials: int, alpha: float, r_fit: int) -> dict` and CLI options `--num-exponentials`, `--alpha`, `--r-fit`.

- [ ] **Step 1: Write a failing selection test**

Add a unit test that regenerates a small fixture and asserts that selecting
`K=32`, `alpha=0.5`, and `r_fit=8*l_max` returns 32 lambdas and records
`K=32` in the output summary. Add a rejection test for a missing fit tuple:

```python
with pytest.raises(ValueError, match="fit tuple not found"):
    select_fit(summary, 31, 0.5, 32)
```

- [ ] **Step 2: Run the focused test and verify failure**

Run:

```bash
PYTHONPATH=src:. conda run -n mps python -m pytest \
  tests/test_phase6_optimization_benchmark.py -q
```

Expected: failure because explicit fit selection is not implemented.

- [ ] **Step 3: Implement exact fit selection**

Replace `_normalize` with a selector that supports the current multi-fit
summary and the legacy single-fit summary. Match all three fields exactly;
never silently fall back to the primary fit. Add the three CLI options with
defaults `24`, `0.5`, and `2048`, and include them in resumability settings.

- [ ] **Step 4: Run the focused tests**

Run the command from Step 2. Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add \
  tracks/mps/solutions/agent-of-my-agent-is-not-my-agent/scripts/benchmark_phase6_optimizations.py \
  tracks/mps/solutions/agent-of-my-agent-is-not-my-agent/tests/test_phase6_optimization_benchmark.py
git commit -m "feat: select explicit MPO fit for local cells"
```

### Task 2: Add exact-checkpoint χ refinement

**Files:**
- Modify: `scripts/benchmark_phase6_optimizations.py`
- Test: `tests/test_phase6_optimization_benchmark.py`
- Test: `tests/test_checkpoints.py`

**Interfaces:**
- Consumes: `load_checkpoint(directory, expected)` and
  `_run_sector(model, options, sector, initial_psi=...)`.
- Produces: CLI option `--initial-checkpoint-root PATH`; each sector loads
  `PATH/<sector>/chi128`, while output is saved under
  `checkpoints/<sector>/chi256`.
- Produces:
  `load_initialization_checkpoint(directory, expected, audit) -> (MPS, dict)`,
  which is distinct from strict final-result `load_checkpoint`.

- [ ] **Step 1: Write failing tests for refinement initialization**

Create a small `L=4`, `chi=8` baseline checkpoint, request `chi=16`, and
assert:

```python
assert summary["initialization"]["even"]["source_requested_chi"] == 8
assert summary["initialization"]["even"]["mode"] == "exact_checkpoint"
assert summary["direct"]["even"]["requested_chi"] == 16
```

Also mutate Gamma, K, alpha, `r_fit`, coefficient hash, MPO/operator
convention, sector, and lattice fingerprint separately and assert fail-closed
`CheckpointMismatch` behavior. Give the fixture a different source code hash
and assert audited initialization accepts it while strict `load_checkpoint`
still rejects it.

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
PYTHONPATH=src:. conda run -n mps python -m pytest \
  tests/test_checkpoints.py \
  tests/test_phase6_optimization_benchmark.py -q
```

Expected: failure because the runner does not load an initial checkpoint.

- [ ] **Step 3: Implement initialization-only refinement**

Extend new checkpoint provenance with an exponential-coefficient hash,
MPO/operator-convention identifier, and lattice fingerprint. For legacy
checkpoints, derive the coefficient hash from a deterministically regenerated
fit whose complete file hash must equal the stored `fit_hash`; derive the
lattice fingerprint from the serialized MPS sites; and verify the convention
against the stored active-channel/MPO metadata plus the previously passed
rotated-basis dense-MPO validation record. Write these evidence sources into
an `initialization_audit` record instead of pretending the legacy checkpoint
contained new fields.

Build the requested provenance before DMRG and audit all physical/structural
fields. Permit source/current code hashes to differ only in
`load_initialization_checkpoint`; record both hashes and the source
provenance ID in the new summary. Pass only a copied MPS to `_run_sector` and
fully reoptimize it with current settings. Do not copy source energy,
observables, variance, or discarded weight into the new physical record.
Write progress with `flush=True` before audit, before DMRG, after DMRG, and
after each atomic checkpoint save.

- [ ] **Step 4: Run focused tests**

Run the command from Step 2. Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add \
  tracks/mps/solutions/agent-of-my-agent-is-not-my-agent/scripts/benchmark_phase6_optimizations.py \
  tracks/mps/solutions/agent-of-my-agent-is-not-my-agent/tests/test_checkpoints.py \
  tracks/mps/solutions/agent-of-my-agent-is-not-my-agent/tests/test_phase6_optimization_benchmark.py
git commit -m "feat: warm start targeted chi refinement"
```

### Task 3: Implement separated uncertainty analysis

**Files:**
- Create: `src/lrtfim/local_uncertainty.py`
- Create: `scripts/analyze_local_reproduction.py`
- Create: `tests/test_local_uncertainty.py`
- Modify: `src/lrtfim/__init__.py`

**Interfaces:**
- Produces:
  - `numeric_shift(reference: float, candidate: float) -> dict`
  - `compare_chi(cell128: dict, cell256: dict) -> dict`
  - `compare_k(cells24: dict, cells32: dict, coupling_summary: dict) -> dict`
  - `fixed_bracket_crossing(gammas, small, large) -> Crossing`
- Writes `results/phase6_sigma1.75/validated-local-reproduction/analysis.json`,
  `mps-uncertainty.csv`, `mpo-uncertainty.csv`, and `rxi-by-chi-k.csv`.

- [ ] **Step 1: Write failing pure-analysis tests**

Use synthetic summaries with known shifts. Assert:

```python
shift = numeric_shift(2.0, 2.2)
assert shift["absolute"] == pytest.approx(0.2)
assert shift["relative"] == pytest.approx(0.1)
```

For crossing data, use signed differences that change sign once and verify
that both K values call `linear_crossing` on
`R_xi(32,Gamma)-R_xi(64,Gamma)`. Test missing L=32 K=32 data yields
`status="incomplete_cost_limited"` rather than an invented crossing.

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
PYTHONPATH=src:. conda run -n mps python -m pytest \
  tests/test_local_uncertainty.py -q
```

Expected: import failure because `local_uncertainty.py` does not exist.

- [ ] **Step 3: Implement pure comparisons**

Validate exact agreement of fixed settings before subtracting records.
Calculate energy shifts per sector, gap absolute/relative shifts, `R_xi`
absolute shifts, and before/after variance and discarded weights. Keep MPS
and MPO sections distinct. Define qualitative stability as preservation of
the single fixed-bracket crossing and no sign reversal of the positive gaps;
report numeric shifts without a literature-value test.

- [ ] **Step 4: Implement the collector CLI**

Accept explicit paths for K=24 fit data, K=24 χ refinement cells, and K=32
cells. Reject mixed code/fit provenance within a comparison. Write JSON
first, then CSV tables, using temporary files followed by `Path.replace`.

- [ ] **Step 5: Run focused and regression tests**

Run:

```bash
PYTHONPATH=src:. conda run -n mps python -m pytest \
  tests/test_local_uncertainty.py \
  tests/test_crossing_analysis.py \
  tests/test_gap_scaling.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add \
  tracks/mps/solutions/agent-of-my-agent-is-not-my-agent/src/lrtfim/local_uncertainty.py \
  tracks/mps/solutions/agent-of-my-agent-is-not-my-agent/src/lrtfim/__init__.py \
  tracks/mps/solutions/agent-of-my-agent-is-not-my-agent/scripts/analyze_local_reproduction.py \
  tracks/mps/solutions/agent-of-my-agent-is-not-my-agent/tests/test_local_uncertainty.py
git commit -m "feat: separate local MPS and MPO uncertainties"
```

### Task 4: Regenerate and validate K=24/K=32 coupling data

**Files:**
- Reuse: `results/phase2_tail_stable/rfit_2048/alpha_05/summary_K24.json`
- Create: `scripts/prepare_local_k_comparison.py`
- Test: `tests/test_prepare_local_k_comparison.py`
- Output: `results/phase6_sigma1.75/validated-local-reproduction/fits/`

**Interfaces:**
- Produces: `fit-summary.json` and distance-resolved K=24/K=32 coupling CSVs
  for `L=32,64`.

- [ ] **Step 1: Write a failing focused-fit test**

On a small fixture, assert the script retains the supplied K=24 coefficients,
fits only K=32 with `alpha=0.5` and `r_fit=8*l_max`, and writes coupling
profiles for each requested length.

- [ ] **Step 2: Implement and run the focused preparation**

Run:

```bash
PYTHONPATH=src:. conda run -n mps python \
  scripts/prepare_local_k_comparison.py \
  --k24-summary results/phase2_tail_stable/rfit_2048/alpha_05/summary_K24.json \
  --sigma 1.75 \
  --lengths 32 64 \
  --l-max 256 \
  --output-dir results/phase6_sigma1.75/validated-local-reproduction/fits
```

This avoids rerunning the seven-cell per-sigma protocol. Measure it with
`/usr/bin/time -v`; if it exceeds ten minutes, retain its progress log and
report the bounded local-compute deviation before continuing.

- [ ] **Step 3: Validate the outputs**

Assert the summary contains exact tuples `(24,0.5,2048)` and
`(32,0.5,2048)`, all lambdas satisfy `0<lambda<1`, all coefficients are
nonnegative, and both lengths have full coupling profiles. Verify that the
existing K=24 file SHA-256 is exactly
`897be6b010a39994b5f7e199bfbdc33561e2d512c9dbb027a887c08f80a5f401`,
the `fit_hash` stored by the legacy checkpoints; audited initialization is
forbidden if it does not match. Record coefficient-only hashes for K=24 and
K=32 and the L=32/64 max/RMS/central errors and coupling shifts.

### Task 5: Run the bounded K=24 χ=256 refinement

**Files:**
- Reuse: `scripts/benchmark_phase6_optimizations.py`
- Inputs: existing K=24 χ=128 checkpoints for `L=64`,
  `Gamma={1.560,1.565}`.
- Output: `results/phase6_sigma1.75/validated-local-reproduction/K24_chi256/`

**Interfaces:**
- Produces four independently resumable sector cells: two Gamma values times
  even/odd sectors.

- [ ] **Step 1: Verify all four χ=128 initialization checkpoints**

The Γ=1.565 odd checkpoint is not present in the current pilot. Run only
that missing K=24 χ=128 odd cell first. For every initialization source,
audit Hamiltonian parameters, `sigma`, `L`, `Gamma`, K, alpha, `r_fit`,
coefficient hash, MPO/operator convention, parity sector, and lattice
fingerprint. Record its historical code hash and the current code hash.
Accept a code-hash mismatch only for initialization; reject every physical
or structural mismatch.

- [ ] **Step 2: Estimate runtime from the existing L=64 measurements**

Record the projected wall time for each sector and the four-cell total.
This is an explicitly approved local deviation from the ten-minute default,
but each cell remains separately resumable.

- [ ] **Step 3: Run Γ=1.560 even then odd at χ=256**

Use the exact K=24 fit tuple, `--direct-only`, one sector per process,
`--chi-schedule 256`, and the matching χ=128 checkpoint root. Monitor each
process at 30–60 minute intervals and verify `summary.json` plus
`state.h5/checkpoint.json` before starting the next sector.

- [ ] **Step 4: Run Γ=1.565 even then odd at χ=256**

Use the same command shape and monitoring discipline as Step 3. Do not
launch χ=384 regardless of the observed shift.

- [ ] **Step 5: Analyze χ shifts immediately**

Run `scripts/analyze_local_reproduction.py` in MPS-only mode. Confirm that
the report includes runtime, energy, gap, variance, discarded weight,
`R_xi`, and χ=128→256 changes for both Gamma values. If the shift is large,
mark `mps_status="unresolved_at_local_chi_ceiling"` and stop escalation.

### Task 6: Run the bounded K=32 physics comparison

**Files:**
- Reuse: `scripts/benchmark_phase6_optimizations.py`
- Output: `results/phase6_sigma1.75/validated-local-reproduction/K32_chi128/`

**Interfaces:**
- Produces K=32, χ=128 summaries/checkpoints for the fixed `L`, Gamma, and
  parity cells only.

- [ ] **Step 1: Run L=64 cells first**

For Γ=1.560 and 1.565, run even and odd sectors at direct χ=128 with K=32.
Use exact-zero pruning and new K=32 checkpoints; K=24 checkpoints are
incompatible and must not initialize K=32 states.

- [ ] **Step 2: Apply the measured cost gate**

Sum measured K=32 L=64 runtimes and project the four L=32 cells. If the
remaining work is acceptable under the local campaign, proceed. Otherwise,
record `crossing_status="incomplete_cost_limited"` and retain the completed
L=64 coupling/Rξ/gap comparisons.

- [ ] **Step 3: Run the minimum L=32 cells when feasible**

Run even and odd sectors at Γ=1.560 and 1.565. These are the minimum cells
needed for both the fixed-bracket crossing and both gap comparisons; do not
add Γ points.

- [ ] **Step 4: Assemble the K uncertainty**

Compare K=24 and K=32 at common χ=128. Report coupling reconstruction
changes, per-point `R_xi` changes, fixed-bracket crossing changes, energy and
gap changes, and convergence diagnostics. Keep this section separate from
the χ uncertainty.

### Task 7: Final verification and local reproduction report

**Files:**
- Create: `scripts/plot_local_uncertainties.py`
- Test: `tests/test_plot_local_uncertainties.py`
- Modify: `README.md`
- Modify: `docs/methodology.md`
- Output: `results/phase6_sigma1.75/validated-local-reproduction/report.md`
- Output: `results/phase6_sigma1.75/validated-local-reproduction/local-uncertainties.png`

**Interfaces:**
- Consumes: the analysis JSON/CSV files from Task 3.
- Produces: one figure with Rξ fixed-bracket curves and separate MPS/MPO
  shift panels.

- [ ] **Step 1: Write and run a failing plot smoke test**

Use a synthetic analysis fixture, invoke the plot CLI, and assert nonempty
PNG and PDF outputs. Expected initial result: failure because the script
does not exist.

- [ ] **Step 2: Implement the figure**

Use colorblind-safe colors, distinct markers and line styles, explicit χ/K
labels, and an annotation that the crossing is two-size and local. Never
draw or quote a thermodynamic-limit extrapolation.

- [ ] **Step 3: Update durable documentation**

Change Phase 6 status to “validated local reproduction.” Document the
`L<=64`, `chi<=256` ceiling, the separate uncertainty budgets, resumability,
and the exact one-line commands used. Do not describe L=128/256 as pending
local work.

- [ ] **Step 4: Run complete verification**

Run:

```bash
PYTHONPATH=src:. conda run -n mps python -m pytest -q
git diff --check -- tracks/mps/solutions/agent-of-my-agent-is-not-my-agent
test ! -e skills/using-slurm/profiles/active.toml
```

Audit that every declared cell has complete raw observables and checkpoint
provenance, and search runnable code for MPO compression calls.

- [ ] **Step 5: Write the final report**

Lead with the local crossing behavior and whether it is stable under tested
χ and K changes. Report MPS and MPO uncertainty separately, state any
cost-limited missing cells, and explicitly avoid final thermodynamic Γc or z
claims.

- [ ] **Step 6: Commit code and documentation only**

Stage only source, tests, scripts, README, and methodology files. Do not
stage `Ion.lock` or ignored raw numerical results.
