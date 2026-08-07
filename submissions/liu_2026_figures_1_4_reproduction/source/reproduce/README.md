# Liu et al. Figures 1–4 reproduction: Codex handoff

This directory is the auditable reproduction package for Liu et al.,
arXiv:2606.05060v1. It contains the Figure 1 theory reconstruction, the
numerically accessible Figure 3–4 calculations, and raw-data interfaces for
all experimental panels in Figures 2–4.

The package never treats generated test points as measurements. Every output
uses one of these provenance labels:

- `exact analytic/theoretical check`;
- `equivalent numerical reoptimization`;
- `digitized paper data`;
- `synthetic demonstration`;
- `experimental raw data`;
- `literal transcription`;
- `unavailable`.

## Files and ownership

| File | Purpose |
|---|---|
| `liu_2026_fig1_reproduction.py` | Figure 1(a–i) theory and optimization reconstruction. Panel (g) is an explicitly labelled mechanistic reconstruction because the underlying experimental trajectory was not published. |
| `liu_2026_fig234_reproduction.py` | Main Figure 3–4 theory, optimization, Hessian, intensity, synthetic calibration, and reported-error-budget workflow. |
| `liu_2026_experimental_analysis.py` | Reads `input.in`, validates all experimental schemas, performs fits, and renders paper-layout Figures 2–4. |
| `liu_2026_noise_modules.py` | Optional finite-blockade and Lindblad building blocks. |
| `liu_2026_build_report.py` | Converts a completed run into report metadata. |
| `input.in` | Single user-editable manifest for collaborator data. |
| `INPUT_SCHEMA.md` | Schema-v2 physical metadata and microscopic CSV contracts. |
| `figure1_run.example.json` | Minimal full-run configuration for Figure 1. |
| `liu_2026_fig234_config.example.json` | Example Figure 2–4 numerical configuration. |
| `MATH_SPEC.md` | Hamiltonian, basis, units, fidelity, Hessian, and provenance contract. |
| `tests/test_liu_2026_fig234.py` | Automated physics, numerical, CLI, cache, serialization, and provenance tests. |

## Environment

The tested target is a local CPU with Python 3.12 and JAX x64.

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
export JAX_ENABLE_X64=true
export JAX_PLATFORM_NAME=cpu
export MPLCONFIGDIR=/tmp/liu-figures-mpl
```

JAX is optional for the NumPy/SciPy MWE and experimental-data plotting. JAX
x64 is required for differentiable pulse optimization and Hessian stages.

## Figure 1

The combined output contains panels `a–i`. Panel (g) is an explicitly labelled
mechanistic reconstruction from the computed two-cycle Hessian trajectory; it
is not presented as a recovery of unpublished experimental data.

```bash
mkdir -p results/figure1
cp figure1_run.example.json results/figure1/run.json

# Fast validation
.venv/bin/python liu_2026_fig1_reproduction.py \
  --run-dir results/figure1 --mwe

# Complete Figure 1 reconstruction
.venv/bin/python liu_2026_fig1_reproduction.py \
  --run-dir results/figure1
```

Main output: `results/figure1/figs/figure1_reproduction.png`.

Figure 1(h,i) are deterministic mechanistic reconstructions because the paper
does not publish its distortion seed, Chebyshev coefficients, line-scan
brackets, or distorted waveform arrays.

## Figures 2–4 theory and synthetic stages

```bash
# NumPy/SciPy MWE
.venv/bin/python liu_2026_fig234_reproduction.py \
  --quick --stage mwe --run-dir results/fig234-quick

# Full accessible calculation; stops on a failed acceptance gate
.venv/bin/python liu_2026_fig234_reproduction.py \
  --standard --all --run-dir results/fig234-standard
```

Figure 3(b,c) are an equivalent physical reoptimization, not the authors'
unpublished waveform. Figure 4 synthetic AOM output is a synthetic
demonstration. Figure 4(f) reported values are a literal transcription unless
the missing open-system inputs are supplied.

### Optional source-constrained Figure 3(b) backend

The original spline/time-bin path remains the default.  To use the
source-described flat-top amplitude, 400 phase bins, and common-α first-order
condition without changing the CLI or `input.in`:

```bash
.venv/bin/python liu_2026_fig234_reproduction.py \
  --standard \
  --config liu_2026_fig3_source_constrained_config.json \
  --stage optimize \
  --run-dir results/fig3b-source-constrained
```

This is still an equivalent reoptimization: the publications do not provide
the optimized phase array or all optimization hyperparameters.  See
[`FIG3B_SOURCE_CONSTRAINED.md`](FIG3B_SOURCE_CONSTRAINED.md) for the
old/new code-path comparison, declared reconstruction choices, and claim
boundary.

## Supplying collaborator experimental data

`input.in` is JSON despite its extension. Schema v2 has two independent
sections: `panels` for measured Figure 2–4 data and `physical_model` for the
atomic states, beams, magnetic field, geometry, and microscopic arrays needed
by a future full-physics model.

> **Required for a complete Figure 3:** `input.in` supplies only the
> experimental panels 3(d,e). Before assembling Figure 3(a–e), a collaborator
> or Codex must first complete the theory workflow above and pass its output
> directory with `--theory-run-dir`. Running `--stage experimental` without
> that directory still renders the supplied 3(d,e) diagnostics, but it cannot
> create the complete Figure 3 layout because panels 3(a–c) are not
> experimental-data inputs.

```json
{
  "schema_version": 2,
  "provenance": "experimental raw data",
  "physical_model": {
    "...": "retain the checked-in structure and replace unavailable slots"
  },
  "panels": {
    "fig4d_intensity": {
      "source": "csv",
      "path": "experimental_data/fig4d_intensity.csv",
      "provenance": "experimental raw data"
    }
  }
}
```

Paths are resolved relative to `input.in`. Inline rows are supported for smoke
tests, but the checked-in inline rows are explicitly synthetic. Each
microscopic slot accepts `inline`, a relative `csv` path, or an explicit
`unavailable` marker. Quantum-number fields can include `n`, `nu`, `L`, `J`,
`F`, `m_J`, and `m_F`; vector fields remain `null` when the paper or
experiment does not provide them. See [`INPUT_SCHEMA.md`](INPUT_SCHEMA.md) for
the complete collaborator contract.

The present Figure 3 Hessian remains the ten-state perfect-blockade model.
Schema-v2 physical inputs are validated and recorded, but are not silently
inserted into that Hamiltonian. The manifest analysis writes
`physical_model_inputs.json` with resolved paths and supplied/missing counts.

Run all supplied experimental pipelines and assemble the paper layouts:

```bash
.venv/bin/python liu_2026_fig234_reproduction.py \
  --stage experimental \
  --input-in input.in \
  --theory-run-dir results/fig234-standard \
  --run-dir results/experimental
```

The three principal images are written to:

```text
results/experimental/figs/input_manifest_analysis/paper_layout/
  figure2_paper_layout_synthetic.png
  figure3_paper_layout_mixed_provenance.png
  figure4_paper_layout_synthetic.png
```

When real CSV data are supplied, filenames may retain the historical
`synthetic` suffix, but the figure banner and JSON metadata are controlled by
the manifest provenance. Rename publication exports only after confirming
that every included panel is experimental.

Independent interface diagnostics are kept under
`figs/input_manifest_analysis/diagnostics/`; they are not paper-layout
figures.

## Experimental schemas

### Figure 2(a): two successive images

`shot_id`, `prepared_state`, `first_image_photon_count`,
`second_image_photon_count`, `state_assignment`, `loss_assignment`.

### Figure 2(b): single-qubit randomized benchmarking

`rb_depth`, `sequence_id`, `shot_id`, `success`, `survival`,
`postselection_flag`.

### Figure 3(d): Hessian-mode sensitivity

`mode`, `coefficient`, `rb_fidelity_or_error`, `uncertainty`,
`theory_sensitivity`.

### Figure 3(e): measured error channels

`mode`, `coefficient`, `initial_computational_state`, `leakage_channel`,
`measured_leakage`, `leakage_uncertainty`, `ramsey_phase`,
`ramsey_phase_uncertainty`.

### Figure 4(a): measured waveforms

`time_us`, ideal/before/after amplitude, ideal/before/after intensity,
`wrapped_phase`, `unwrapped_phase`, `measurement_uncertainty`.

### Figure 4(b): closed-loop scans

`cycle`, `mode`, `scan_coefficient`, `gate_error`, `uncertainty`,
`selected_optimum`.

### Figure 4(c): echoed randomized benchmarking

`rb_circuit_depth`, `sequence_id`, `shot_id`, `success`, `loss`,
`postselection_flag`.

### Figure 4(d): intensity scan

`gate_type`, `intensity_ratio`, `gate_error`, `uncertainty`,
`fidelity_convention`.

### Figure 4(e): long-term stability

`elapsed_time`, `gate_error`, `uncertainty`,
`calibration_or_reoptimization_event`.

### Figure 4(f): error budget

`noise_source`, `raw_contribution`, `postselected_contribution`,
`uncertainty`, `parameter_source`.

Figure 4(c) and Figure 4(d) are deliberately separate pipelines.

## Figure grouping

- Figure 2: panel `a` above panel `b`; panel `a` contains separate
  Prepare |0⟩ and Prepare |1⟩ plots.
- Figure 3: `a,b,c` on the top row and `d,e` on the bottom row.
- Figure 4: `a,b,c` on the top row and `d,e,f` on the bottom row.

Figure 3(a) shows nonzero schematic gaps Δq between |0⟩ and |1⟩ and Δr
between |r⟩ and |r′⟩. These gaps are not drawn to scale. In the paper's
notation, |0⟩ and |1⟩ are the mF=±1/2 nuclear-spin qubit sublevels of the
³P₀, F=1/2 manifold; their field-dependent separation is the qubit Zeeman
splitting.

## Verification

```bash
PYTHONDONTWRITEBYTECODE=1 \
  .venv/bin/python -m unittest tests.test_liu_2026_fig234 -v
```

Before accepting collaborator data, verify:

1. `manifest_provenance` is `experimental raw data`;
2. `experimental_points_generated` is true;
3. `synthetic_points_generated` is false for every claimed experimental
   panel;
4. uncertainties and postselection flags are present;
5. the fidelity convention is named for every Figure 4(d) row;
6. no missing experimental panel is silently replaced by generated values.

## Reproduction limits

The repository does not contain the authors' Figure 3(b) pulse array, raw
experimental observations, MQDT pair-state data, blockade-versus-distance
table, decay branching ratios, thermal position distribution, or laser-noise
power spectra. Outputs depending on these remain equivalent reoptimizations,
synthetic demonstrations, literal transcriptions, or unavailable as recorded
in metadata.
