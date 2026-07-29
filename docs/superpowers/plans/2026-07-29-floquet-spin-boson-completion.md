# Floquet Spin-Boson Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing validation-complete Floquet spin-boson implementation into a locally verified, visually reviewable Fig. 2/3/5 reproduction with measured convergence and honest production gating.

**Architecture:** Preserve the existing numerical modules and close the remaining delivery gaps around environment bootstrap, acceptance tests, plotting, convergence evidence, and production orchestration. Each numerical stage writes machine-readable diagnostics first and then a deterministic comparison plot; the next expensive stage starts only after that plot is reviewed.

**Tech Stack:** Julia 1.12, UniformTEMPO.jl, KrylovKit.jl, JLD2.jl, FFTW.jl, Python 3 with NumPy/Matplotlib for deterministic plots, GitHub Actions, local CPU execution with Slurm only beyond the 10-minute or 16-GB gate.

## Global Constraints

- Physics is fixed at Ω=1, S=σz, Hsys(t)=σx/2+Hdrive(t), α=0.05, ωc=2.5, εd=1, and zero temperature.
- Longitudinal driving is εd cos(ωd t)σx; transversal driving is εd cos(ωd t)σz.
- Every Floquet period satisfies T=2π/ωd=Mdt exactly; no closing-step interpolation is permitted.
- QF acts on the 4χ augmented space and defaults to matrix-free forward and adjoint actions.
- Fig. 3 uses the ordered augmented-space two-time correlation, split into Casym and Cdecay; system energy balance is validation only.
- Delta peaks remain separate measures compared by position and integrated weight.
- Prefer local execution only below 10 minutes wall time and 16 GB resident memory.
- Production mode requires complete evidence for dt, compression/rank, eigensolver tolerance, τmax, Δω, ωmax, and nmax.
- Every plottable stage produces and pauses at a visual comparison before more expensive computation.
- At execution start set `RUN_DIR=tracks/mps/results/$(date +%Y%m%d-%H%M%S)-floquet-spin-boson-completion` once, create it, and reuse that exact path for every generated artifact.

---

### Task 1: Reproducible Julia Environment and Full Test Gate

**Files:**
- Modify: `tracks/mps/solutions/reproduction/floquet_spin_boson/README.md`
- Modify: `.github/workflows/test.yml`
- Test: `tracks/mps/solutions/reproduction/floquet_spin_boson/test/runtests.jl`
- Create if required by a failing bootstrap test: `tracks/mps/solutions/reproduction/floquet_spin_boson/scripts/bootstrap.jl`

**Interfaces:**
- Consumes: `envs/current/Project.toml` and `envs/current/Manifest.toml`.
- Produces: one documented command that instantiates and tests the pinned environment from a fresh depot; exit code zero certifies the local test gate.

- [ ] **Step 1: Reproduce the clean-depot failure**

Run:

```bash
tmp_depot="$(mktemp -d)"
JULIA_DEPOT_PATH="$tmp_depot" julia \
  --project=tracks/mps/solutions/reproduction/floquet_spin_boson/envs/current \
  -e 'import Pkg; Pkg.instantiate(); Pkg.status()'
```

Expected before any fix: dependency installation either succeeds from the manifest or fails with an exact package/provenance error. Record the command, wall time, and error; do not silently fall back to another depot.

- [ ] **Step 2: Verify dependency declarations**

Run:

```bash
julia --project=tracks/mps/solutions/reproduction/floquet_spin_boson/envs/current \
  -e 'import TOML; p=TOML.parsefile("tracks/mps/solutions/reproduction/floquet_spin_boson/envs/current/Project.toml"); println(sort!(collect(keys(p["deps"]))))'
```

Expected: direct runtime imports from `FloquetSpinBoson.jl`—including `FFTW`, `JLD2`, `KrylovKit`, `SpecialFunctions`, and `UniformTEMPO`—appear in `[deps]`.

- [ ] **Step 3: Add a bootstrap smoke test only if direct dependencies are missing**

Create `scripts/bootstrap.jl` with:

```julia
import Pkg
Pkg.instantiate()
for package in (:FFTW, :JLD2, :KrylovKit, :SpecialFunctions, :UniformTEMPO)
    Base.require(Main, package)
end
println("Floquet environment ready")
```

If all dependencies are already declared, do not create this wrapper; document the direct `Pkg.instantiate()` command instead.

- [ ] **Step 4: Run the complete Julia suite**

Run:

```bash
PROJ=tracks/mps/solutions/reproduction/floquet_spin_boson
julia --project="$PROJ/envs/current" -e 'import Pkg; Pkg.instantiate()'
julia --project="$PROJ/envs/current" "$PROJ/test/runtests.jl"
```

Expected: every testset exits zero. Any assertion failure becomes a separate red-green-refactor fix before continuing.

- [ ] **Step 5: Make local and CI commands identical**

Update README and `.github/workflows/test.yml` so both execute:

```bash
julia --project=envs/current -e 'import Pkg; Pkg.instantiate()'
julia --project=envs/current test/runtests.jl
```

Expected: no undocumented pre-populated depot is required.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/test.yml \
  tracks/mps/solutions/reproduction/floquet_spin_boson/README.md \
  tracks/mps/solutions/reproduction/floquet_spin_boson/scripts/bootstrap.jl
git commit -m "fix: make Floquet environment reproducible"
```

Omit `bootstrap.jl` from `git add` when Step 3 determined it was unnecessary.

---

### Task 2: Deterministic Visual Checkpoints for Fig. 2, Fig. 3, and Fig. 5

**Files:**
- Create: `tracks/mps/solutions/reproduction/floquet_spin_boson/scripts/plot_results.py`
- Create: `scripts/tests/test_floquet_plot_results.py`
- Modify: `tracks/mps/solutions/reproduction/floquet_spin_boson/README.md`

**Interfaces:**
- Consumes: strict Zenodo CSVs plus generated Fig. 2, per-point Fig. 3, or Fig. 5 CSV outputs.
- Produces: `fig2_comparison.png`, `fig3_comparison.png`, or `fig5_comparison.png`; missing columns, mismatched grids, and absent production points exit nonzero.

- [ ] **Step 1: Write failing CLI tests**

Add fixtures with three-row CSVs and tests equivalent to:

```python
def test_fig3_plot_writes_comparison(tmp_path):
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "fig3",
         "--result-root", str(tmp_path / "ours"),
         "--reference-root", str(tmp_path / "reference"),
         "--output", str(tmp_path / "fig3.png")],
        text=True, capture_output=True)
    assert completed.returncode == 0, completed.stderr
    assert (tmp_path / "fig3.png").stat().st_size > 1000


def test_fig3_plot_rejects_missing_frequency(tmp_path):
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "fig3",
         "--result-root", str(tmp_path / "incomplete"),
         "--reference-root", str(tmp_path / "reference"),
         "--output", str(tmp_path / "fig3.png")],
        text=True, capture_output=True)
    assert completed.returncode != 0
    assert "missing Fig. 3 point" in completed.stderr
```

- [ ] **Step 2: Run the plotting tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest scripts/tests/test_floquet_plot_results.py -q
```

Expected: FAIL because `plot_results.py` does not exist.

- [ ] **Step 3: Implement the minimal strict plot CLI**

Implement subcommands with explicit point sets:

```python
FIG3_POINTS = {
    "longitudinal": (10.0, 5.0, 2.5),
    "transversal": (2.0, 1.5, 1.0),
}

def require_columns(table, names, path):
    missing = set(names).difference(table.dtype.names or ())
    if missing:
        raise ValueError(f"{path}: missing columns {sorted(missing)}")
```

For Fig. 3, draw the continuous current as a line, delta weights as vertical
markers in a separate lower strip, and the matching Zenodo curve as a dashed
line. For Fig. 5, plot longitudinal and transversal totals against the exact
reference frequency grid. Save with `dpi=180`, include units in labels, and
write no derived numerical data.

- [ ] **Step 4: Run plotting and repository tests**

Run:

```bash
.venv/bin/python -m pytest scripts/tests/test_floquet_plot_results.py -q
make test
```

Expected: PASS.

- [ ] **Step 5: Generate and display the existing Fig. 2 checkpoint**

Run the Fig. 2 subcommand against:

```text
tracks/mps/results/20260728-154023-mickiewicz2026-fig2
```

Expected: a side-by-side ωd=2.5 and ωd=10 PNG preserving the physical
Redfield discrepancy at low frequency.

- [ ] **Step 6: Commit**

```bash
git add scripts/tests/test_floquet_plot_results.py \
  tracks/mps/solutions/reproduction/floquet_spin_boson/scripts/plot_results.py \
  tracks/mps/solutions/reproduction/floquet_spin_boson/README.md
git commit -m "feat: add strict Floquet visual checkpoints"
```

---

### Task 3: Local Validation, Measured Cost Gate, and Convergence Evidence

**Files:**
- Modify: `tracks/mps/solutions/reproduction/floquet_spin_boson/src/convergence.jl`
- Modify: `tracks/mps/solutions/reproduction/floquet_spin_boson/scripts/run_convergence.jl`
- Test: `tracks/mps/solutions/reproduction/floquet_spin_boson/test/test_convergence.jl`
- Generated: `$RUN_DIR/convergence/evidence.json`
- Generated: `$RUN_DIR/fig3_validation_comparison.png`

**Interfaces:**
- Consumes: validation timing, MaxRSS, achieved χ, diagnostics, and the seven convergence-axis comparisons.
- Produces: immutable `evidence.json` accepted by `validate_production_evidence`; a per-point route of `local` or `slurm` with reason and estimated wall/memory.

- [ ] **Step 1: Write failing evidence-completeness tests**

Add:

```julia
@testset "measured resource gate is fail-closed" begin
    @test choose_compute_route(599.0, 15 * 2^30) == :local
    @test choose_compute_route(600.0, 15 * 2^30) == :slurm
    @test choose_compute_route(10.0, 16 * 2^30) == :slurm
    @test_throws ArgumentError choose_compute_route(NaN, 1)
end
```

and require all seven named axes to contain at least two settings, a declared
primary quantity, a finite difference, and a passing tolerance.

- [ ] **Step 2: Run the convergence test and verify RED**

Run:

```bash
PROJ=tracks/mps/solutions/reproduction/floquet_spin_boson
julia --project="$PROJ/envs/current" \
  -e 'include("'"$PROJ"'/test/test_convergence.jl")'
```

Expected: FAIL because the strict measured route/evidence interface is absent.

- [ ] **Step 3: Implement the strict route and evidence schema**

Add:

```julia
function choose_compute_route(wall_seconds::Real, resident_bytes::Integer)
    isfinite(wall_seconds) && wall_seconds >= 0 ||
        throw(ArgumentError("wall estimate must be finite and nonnegative"))
    resident_bytes >= 0 ||
        throw(ArgumentError("memory estimate must be nonnegative"))
    return wall_seconds < 600 && resident_bytes < 16 * 2^30 ? :local : :slurm
end
```

Persist raw settings, measured values, tolerance, pass/fail, source artifact,
Julia version, UniformTEMPO revision, and cache identity for each axis.

- [ ] **Step 4: Run local Fig. 2 and one-point-per-drive Fig. 3 validation**

Use `/usr/bin/time -v`, BLAS thread count one, and a timestamped result
directory. Start with longitudinal ωd=5 and transversal ωd=1 because they
exercise distinct drive directions without duplicating the already inspected
quick points. Do not exceed validation settings before measuring them.

Expected outputs per point: steady state, micromotion, complex correlation,
decomposition, continuous current, delta weights, diagnostics, timing, and
MaxRSS.

- [ ] **Step 5: Generate and pause at the Fig. 3 validation plot**

Run:

```bash
.venv/bin/python \
  tracks/mps/solutions/reproduction/floquet_spin_boson/scripts/plot_results.py \
  fig3 --allow-validation-subset \
  --result-root "$RUN_DIR/fig3" \
  --reference-root tracks/mps/results/20260728-floquet-if-complete-reproduction/references/zenodo-19593671/extracted/fig_3 \
  --output "$RUN_DIR/fig3_validation_comparison.png"
```

Expected: two panels showing our continuous spectrum and the matching Zenodo
curves, with delta weights visually separate. Stop for user review.

- [ ] **Step 6: Run the seven convergence axes locally where admitted**

For each axis, compare two adjacent settings at identical physics. If a point
crosses the resource gate, write its Slurm route without launching it until
the user has seen the validation plot.

- [ ] **Step 7: Run tests and commit code**

```bash
PROJ=tracks/mps/solutions/reproduction/floquet_spin_boson
julia --project="$PROJ/envs/current" "$PROJ/test/runtests.jl"
git add "$PROJ/src/convergence.jl" "$PROJ/scripts/run_convergence.jl" \
  "$PROJ/test/test_convergence.jl"
git commit -m "feat: gate Floquet production on measured convergence"
```

Generated results remain under the gitignored results directory.

---

### Task 4: Production Fig. 3/Fig. 5, Final Visuals, and Report

**Files:**
- Modify only if validation exposes a defect:
  `tracks/mps/solutions/reproduction/floquet_spin_boson/src/heat_current.jl`
- Modify only if validation exposes a defect:
  `tracks/mps/solutions/reproduction/floquet_spin_boson/scripts/reproduce_fig3.jl`
- Modify only if validation exposes a defect:
  `tracks/mps/solutions/reproduction/floquet_spin_boson/scripts/reproduce_fig5.jl`
- Generated: `$RUN_DIR/fig3_comparison.png`
- Generated: `$RUN_DIR/fig5_comparison.png`
- Generated: `$RUN_DIR/run.json`
- Generated: `$RUN_DIR/report.html`

**Interfaces:**
- Consumes: accepted convergence evidence, exact Zenodo grids, cached uniform IF tensors, and resumable point manifests.
- Produces: all six Fig. 3 points, both Fig. 5 scans, final comparison plots, energy-balance diagnostics, performance report, and self-contained HTML report.

- [ ] **Step 1: Reconfirm production setup and estimates**

Print for every dt group: frequencies, M, exact dt, achieved/target χ,
augmented dimension, dense-QF memory, selected matrix-free representation,
estimated wall, estimated resident memory, local/Slurm route, Julia threads,
BLAS threads, and process count.

- [ ] **Step 2: Execute Fig. 3 by dt group with resume enabled**

Run locally admitted groups first. For a Slurm-routed group, use the existing
cluster profile and monitor through first output and completion before
fetching. A point is complete only when all required artifacts and diagnostics
exist and reference metrics are finite.

- [ ] **Step 3: Generate and pause at the complete Fig. 3 visual**

Run `plot_results.py fig3` without `--allow-validation-subset`.

Expected: six point panels, continuous spectra compared on matching grids,
delta weights shown separately, and no quick/validation data mislabeled as
production. Stop for user review before Fig. 5.

- [ ] **Step 4: Execute the resumable Fig. 5 scan**

Read the exact Zenodo frequency grid, group identical dt values, reuse one q
per group, warm-start only exact-compatible neighbors, and write each point
manifest atomically. Retry only failed points.

- [ ] **Step 5: Verify total-current balance**

For every Fig. 5 point require:

```text
abs(period_averaged_power - total_current) /
max(abs(period_averaged_power), abs(total_current), balance_floor)
< energy_balance_tolerance
```

Record failures without replacing the correlation-derived current by the
power estimate.

- [ ] **Step 6: Generate and pause at the Fig. 5 visual**

Run `plot_results.py fig5`.

Expected: longitudinal and transversal total-current curves against the exact
Zenodo grid, with failed or nonconverged points visibly absent rather than
interpolated. Stop for user review.

- [ ] **Step 7: Build the final report**

Populate `run.json` from produced artifacts, then run:

```bash
python3 skills/reproduce-paper/build_report.py "$RUN_DIR"
python3 skills/report/render_report.py "$RUN_DIR"
```

The report states separately: physics reproduced, numerical convergence
status, reference errors, performance improvement, unresolved paper-era
UniformTEMPO provenance, and rerun commands.

- [ ] **Step 8: Final verification and commit**

Run:

```bash
make test
PROJ=tracks/mps/solutions/reproduction/floquet_spin_boson
julia --project="$PROJ/envs/current" "$PROJ/test/runtests.jl"
git status --short
```

Commit only source, tests, configs, and documentation. Do not commit caches,
JLD2 outputs, Zenodo archives, or generated results.
