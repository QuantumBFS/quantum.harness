# Closed-loop Hessian robustness comparison

This directory is a self-contained handoff of the robustness comparison
study. It includes the manuscript, the complete simulation code, the archived
numerical evidence, and every plotted figure needed to inspect the study
without relying on a personal machine layout.

## Start here

- `FIGURE_NOTES.pdf` is the human-readable, figure-by-figure explanation.
- `FIGURE_NOTES.tex` is its LaTeX source.
- `code/hessian_loop_failure_map.py` is the complete calculation and plotting
  implementation (not a pseudocode excerpt).
- `code/validate_robustness_package.py` is the standard-library package
  validator for a fresh baseline or full run.
- `code/compare_robustness_runs.py` compares every archived and regenerated
  scientific table value within declared mixed tolerances.
- `summary.json` is the compact machine-readable result.
- `data/` contains the baseline arrays and all intermediate scan tables.
- `figs/` contains the nine generated study figures and two paper-reference
  figures.
- `PROVENANCE.md` explains the archived-evidence boundary and the clean-run
  refresh procedure.
- `FRESH_RUN_SEAL.json` records the completed clean baseline/full audit and
  source/result hashes.
- `fresh-run-evidence/` retains the small baseline/full summaries, generated
  manifests, full scientific tables, and comparison result needed to
  independently recompute the 4,353-field scientific comparison. Large
  duplicate NPZ and rendered figures remain represented by their manifest
  hashes rather than copied a second time.

The LaTeX build products (`.aux`, `.log`, `.out`, `.toc`, and `.synctex.gz`)
were intentionally omitted because they are reproducible transient files.
Fresh runs also write `artifact_manifest.json`, which seals every generated
artifact except itself and the transient `progress.json`.

## Governing insight and behavioral contract

The nominal complex waveform is sampled in 256 time bins and represented by
512 real control coordinates:

```text
x = [Re Ω_c(t_1), ..., Re Ω_c(t_N),
     Im Ω_c(t_1), ..., Im Ω_c(t_N)],  N = 256.
```

Near the nominal gate, the leading infidelity model is

```text
1 - F(x_0 + δx) ≈ 1/2 δxᵀ H_F δx.
```

There are two complex leakage amplitudes and one real controlled-phase error,
so the Gauss-Newton fidelity Hessian has five active real directions. The
closed loop scans those five fixed nominal eigenvectors. Its success therefore
depends on more than the distortion norm: the distortion's orientation,
higher-order breakdown, rotation of the local sensitive subspace, estimator
noise, and the appearance of physical channels outside the nominal response
span all matter.

### Inputs

- Published analytical pulse:
  `A = 2π(0.1122)`, `ω = 1.0431 Ω`, `φ_0 = -0.7318`,
  `δ_0 = 0`, and `ΩT/(2π) = 1.215`.
- Distortion magnitude:
  `η ∈ {0.01, 0.03, 0.06, 0.10, 0.20, 0.35, 0.60, 1.00}`.
- Initial principal-space power:
  `p_parallel ∈ {0, 0.5, 1}`.
- Ten deterministic random seeds per core scan cell.
- Seven symmetric fidelity samples per one-dimensional mode fit.
- Success target `1 - F ≤ 1e-5` within eight five-mode cycles.
- Optional fidelity noise and named Hamiltonian/pathology perturbations, as
  defined directly in the script.

### Outputs

- A baseline acceptance record and Hessian arrays.
- 240 core distortion trials, 100 estimator-noise trials, six pathology
  trials, and ten Hamiltonian-error points.
- CSV tables for the core boundary, subspace rotation, residual channels,
  estimator noise, pathology probes, and Hamiltonian errors.
- Nine figures and `summary.json`.

### Assumptions and scope

- Perfect Rydberg blockade and unitary dynamics.
- Symmetric two-atom reduced model around the constant-magnitude analytical
  Figure-1 pulse; distorted trial pulses need not have constant magnitude.
- No spontaneous decay, Doppler noise, finite blockade, or full experimental
  four-level ytterbium model.
- Ten seeds per core cell make the boundary exploratory, not a high-precision
  population estimate.
- The seven-point scan width and fit rule are explicit extension choices
  because the source paper does not publish every experimental fitting detail.

### Invariants and acceptance criteria

A valid baseline run must satisfy all of the following:

- `baseline.accepted` is `true`.
- Baseline infidelity is at or below `1e-5`; the archived value is
  `6.599615889280042e-06`.
- Active Hessian rank is exactly five using the relative eigenvalue threshold
  `1e-8`.
- `|λ_6|/λ_1` remains negligible; the archived value is
  `2.681505564779352e-16`.
- The controlled-phase error to π is approximately
  `1.9361575390020036e-04` radians.

A valid full run must finish with `summary.json:status == "complete"`, retain
the declared trial counts, and produce all nine expected figure paths.
Numerical refreshes should be compared first at the intermediate-table level,
not only by visual similarity of the final plots.

## Minimal working example

The supported handoff workflow is WSL/Linux with Python 3.12, matching the
environment used for the archived study. From the repository root, create the
pinned environment and an empty temporary run directory:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r robustness/comparison/requirements.txt

RUN_DIR="$(mktemp -d /tmp/ql1f-robustness-baseline.XXXXXX)"
JAX_ENABLE_X64=true MPLCONFIGDIR=/tmp/hessian-loop-mpl \
  .venv/bin/python robustness/comparison/code/hessian_loop_failure_map.py \
  --baseline-only \
  --run-dir "$RUN_DIR"

.venv/bin/python \
  robustness/comparison/code/validate_robustness_package.py \
  --run-dir "$RUN_DIR" \
  --mode baseline
```

Inspect `$RUN_DIR/data/baseline.json` before scaling up. It should pass every
baseline acceptance criterion above. Native Windows Python has not been
independently validated for this archived workflow and is therefore not
claimed as a supported execution path.

## Full reproduction

Use another empty temporary directory; never point the command at this
directory's archived `data/`, `figs/`, or `summary.json`:

```bash
RUN_DIR="$(mktemp -d /tmp/ql1f-robustness-full.XXXXXX)"
JAX_ENABLE_X64=true MPLCONFIGDIR=/tmp/hessian-loop-mpl \
  .venv/bin/python robustness/comparison/code/hessian_loop_failure_map.py \
  --seeds 10 \
  --max-wall-seconds 600 \
  --run-dir "$RUN_DIR"

.venv/bin/python \
  robustness/comparison/code/validate_robustness_package.py \
  --run-dir "$RUN_DIR" \
  --mode full
```

The checked-in legacy `summary.json` records `23.19` seconds for its original
process-local wall clock. An earlier handoff note also reported roughly
`188` seconds from a different invocation, but that observation was not
sealed to the archived result and is not retained as a canonical runtime.
Host load, CPU model, and especially cold-versus-warm JAX/XLA compilation
caches can create large timing differences. Fresh summaries therefore record
the timing clock, measurement scope, and uncontrolled warm/cold state;
timing is diagnostic and is not a scientific acceptance gate.

## Archived evidence map

| File | Meaning |
| --- | --- |
| `data/baseline.json` | Baseline gate and rank-five acceptance metrics |
| `data/baseline.npz` | Nominal waveform, Hessian, eigenpairs, and principal basis |
| `data/core_scan.csv` | Per-seed distortion-boundary results |
| `data/subspace_rotation.csv` | Principal angles and singular overlaps |
| `data/channel_decomposition.csv` | Leakage and nonlinear-phase diagnostics |
| `data/noise_scan.csv` | Noisy-fit success and conditioning |
| `data/pathology_scan.csv` | Six named stress tests |
| `data/hamiltonian_error_scan.csv` | In-span detuning versus new leakage channel |

## Main result

All tested orientations succeeded through `η = 0.35`. At `η = 0.60`, the
success counts were `10/10`, `6/10`, and `2/10` for
`p_parallel = 0`, `0.5`, and `1`, respectively. Large principal-rich errors
coincide with quadratic-model breakdown and strong local-subspace rotation.
The clearest residual floors occur when the perturbed device introduces a new
physical error channel that the fixed five-direction calibration space cannot
span.

## Provenance

- Study date: 28 July 2026.
- Extension source: arXiv:2606.05060v1.
- Analytical-pulse source cited by that work:
  Evered et al., *Nature* 622, 268 (2023).
- Archived runtime: Python 3.12.13, JAX/JAXlib 0.11.0, NumPy 2.5.1,
  SciPy 1.18.0, CPU backend with JAX 64-bit mode enabled.

The checked-in `data/`, `figs/`, and `summary.json` predate the new source
hash and artifact-manifest contract. They remain immutable historical
evidence and have not been retroactively relabeled. A clean baseline/full run
has since passed the new validators and reproduced all scientific table
values within the declared tolerance; see `PROVENANCE.md` and
`FRESH_RUN_SEAL.json`.

From this directory, recompute the archived-versus-fresh scientific
comparison without JAX, NumPy, or SciPy:

```bash
python code/compare_robustness_runs.py \
  --reference-dir . \
  --candidate-dir fresh-run-evidence/full
```

