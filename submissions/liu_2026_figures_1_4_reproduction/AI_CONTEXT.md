---
artifact_type: paper_reproduction_bundle
primary_issue: https://github.com/QuantumBFS/quantum.harness/issues/113
primary_paper: arXiv:2606.05060v1
paper_title: High-fidelity neutral atom gates leveraging low-rank Hessian optimization
status: issue_113_case_study_complete_but_full_challenge_incomplete
created: 2026-07-30
figures: [1, 2, 3, 4]
regression_tests: 33
regression_tests_passed: 33
digital_twin_platform_tests: 27
digital_twin_platform_tests_passed: 27
---

# AI context: Issue #113 sim-to-real case study using Liu et al.

> Reader note: this file is a detailed machine-facing audit and retains the
> paper's figure identifiers so claims can be traced to source artifacts. The
> external project narrative is `report.html`; it is organized around the
> scientific problem, the three completed work packages, and the next step.

## 1. Task and acceptance contract

Original problem: Quantum Harness Issue #113 asks whether a cheap
differentiable quantum-control model can identify the few Hessian directions
that matter, allowing an expensive finite-shot query-only device to be
calibrated with fewer black-box experiments than a search over all pulse
parameters.

This submission instantiates that question on the 171Yb neutral-atom
experiment of Liu et al., uses the collaborator’s simulator as the query-only
device, generates machine-readable input data, renders Figures 1–4, and states
exactly which Issue #113 deliverables are and are not established.

Acceptance criteria:

1. Figure 1 must recover the seven-state perfect-blockade low-rank mechanism.
2. Figure 3 must independently produce a source-constrained robust waveform,
   close the terminal conditions, and recover the ten-dimensional principal
   Hessian space.
3. Figures 2 and 4 must pass through `input.in` using explicit finite-shot
   records rather than hidden truth.
4. Every comparison must distinguish independent predictions, calibrated
   anchors, literal paper values, and unavailable author data.
5. Source, data, figures, and documentation must be locally auditable.
6. The enhanced Figure-4 run must obtain feedback fidelity from
   Cold_Atom Gate Simu_Platform, include explicit leakage and laser-noise
   channels, and finish within one hour.

## 2. Issue #113 hypothesis and three-stage pipeline

For a closed `d`-dimensional unitary target, write the terminal propagator as
`U(T)=U_target exp(iA)`. To second order, phase-insensitive infidelity depends
only on the traceless part of the Hermitian error generator:

`L approximately (1/(2d)) Tr[(A - Tr(A) I/d)^2]`.

The ideal closed-system prediction is therefore at most `d^2-1` curved
directions, independent of the number of raw pulse parameters. Issue #113
turns this observation into the following sim-to-real pipeline:

1. `open_loop_model`: differentiate through the model and optimize a pulse
   `u_star`.
2. `landscape_extraction`: compute the Hessian at `u_star`, retain its top
   `k` eigenvectors, and use them as reduced coordinates.
3. `closed_loop_black_box`: modify only the reduced coefficients using noisy
   scalar fidelity measurements from a query-only device.

The challenge’s headline evidence is query count and total shots to reach a
target versus search dimension, with full-parameter baselines, multiple seeds,
gap-size sweeps, shot-budget sweeps, and an invariant check across at least two
Hilbert-space sizes.

### Mapping in this submission

| Issue #113 object | Concrete neutral-atom realization |
|---|---|
| differentiable model | ten-state perfect-blockade 171Yb Schrödinger model |
| overparameterized control | fixed envelope plus 400 phase intervals |
| model optimum | independently optimized amplitude-robust CZ pulse |
| Hessian coordinates | ten stable principal modes plus numerical null space |
| model–truth gap | simplified injected AOM filtering plus finite blockade and decay |
| query-only device | `cs_tweezer_sim`; scan selection receives no gradient or hidden state |
| noisy observation | binomial failures, 50,000 shots per scan point |
| closed-loop correction | four Hessian scan cycles, nine scan points |
| target reached | correctable coherent error below `1e-3` after cycle 2 |
| irreducible floor | raw observed total error remains near the declared `0.004` baseline |

### Challenge completion status

| Issue #113 deliverable | Status | Evidence or missing work |
|---|---|---|
| clean three-stage pipeline | complete | source, manifest, serialized plant and query-only scans are bundled |
| one realistic model/device gap case | complete | full Schrödinger coherent error `5.88e-2` to `1.22e-4` |
| honest failed or limited case | complete | raw target `1e-3` is impossible with the `0.004` floor; one Figure-3 check also misses by 0.2316 percentage points |
| queries-to-target versus dimension | incomplete | only fixed rank-10 closure and qualitative basis comparisons were run |
| multiple seeds and error bars | partial | the one-hour gap scan has 3 seeds per gap; the full four-cycle trajectory still has one seed |
| model–truth gap sweep | partial | fixed `k=10`, gaps `0.03, 0.11, 0.70`, 3 seeds each, 2-cycle cutoff |
| `d^2-1` check across system sizes | incomplete | ranks 5 and 10 arise from different accessible-channel reductions, not a controlled `d=2,4,8` series |
| shot-budget sweep | incomplete | one budget, 50,000 shots per scan point |

Conclusion: this bundle is a complete, auditable scientific case study and
paper reproduction supporting the Issue #113 mechanism, but it is not a
complete solution to every challenge deliverable.

## 3. Physical models

### Figure 1 model

- System: two identical three-level atoms.
- Basis: computational states `|00>`, `|01>`, `|10>`, `|11>` and leakage
  partners `|0r>`, `|r0>`, `|W>`.
- Boundary: perfect blockade; `|rr>` is excluded.
- Hamiltonian:

  `H(t) = 1/2 Σ_j [Ω_tilde(t)|r>_j<1| + Ω_tilde*(t)|1>_j<r|]`.

- Analytic pulse:

  `Ω_tilde(t)=exp(i phi(t))`,
  `phi(t)=A cos(omega t - phi_0) + delta_0 t`,
  with `A=2 pi * 0.1122`, `omega=1.0431`,
  `phi_0=-0.7318`, `delta_0=0`, and `T=2 pi * 1.215`.

- Expected real Hessian rank: 5, from two complex leakage channels and one
  real controlled-phase channel after eliminating correctable local-Z phase.

### Figures 3–4 design model

- System: one 171Yb atom pair in the paper’s ten-state perfect-blockade
  reduction.
- Drive: `Omega_0=2 pi * 6.0 MHz`.
- Rydberg splitting: `Delta_r=2 pi * 16.1 MHz`.
- Gate duration: `T=0.55 us`.
- Control: fixed sinusoidal-edge amplitude envelope and 400 independent
  piecewise-constant phase intervals.
- The independently optimized phase array is an equivalent solution. It is
  not the authors’ unpublished numerical array.

### Digital-twin execution model

- Effective Hamiltonian:

  `H(t)=Delta_r Pi_rprime + 1/2[Omega(t) sigma_plus +
  Omega*(t) sigma_minus] + B_eff(R) Pi_double`.

- Effective interaction:

  `B_eff(R)=B0*(2 um/R)^6`.

- `B0/(2 pi)=303.32537141073584 MHz`, calibrated so the nominal
  finite-blockade contribution is `1.6e-4` at `R=2 um`.
- Rydberg lifetime: `42 us`.
- Assumed fraction of lifetime-induced error mapped to erasure: `0.90`.
- `B0` is a calibrated effective parameter, not an independent reconstruction
  of the unavailable experiment-specific MQDT pair table.

### Enhanced Cold_Atom Gate Simu_Platform run

The enhanced run is a second evidence layer built on the Figure-3 equivalent
waveform and Hessian. It replaces the earlier simplified Figure-4 feedback
oracle with fidelity computed by the bundled platform.

- Array reduction: five independent 171Yb dimers; one two-atom dimer is
  propagated because the dimers are separated by 25 um and have no
  inter-dimer interaction.
- Local basis per atom: `0`, `1`, `r`, `r_prime`, and `erasure`.
- Explicit pair sectors: `rr`, `rr_prime/r_prime_r`, and
  `r_prime_r_prime`.
- Shared actuator: one complex 302-nm field drives `1<->r` and
  `0<->r_prime`.
- Noise: 2.7 uK Doppler, 0.02 um position spread and resulting `R^-6`
  variation, 1% pulse-energy RMS, Lorentzian linewidth, 500 Hz
  quasistatic frequency spread, and 1 kHz Ornstein-Uhlenbeck frequency
  noise with 0.2 us correlation time.
- No independent EOM is added because Liu et al. do not report one in this
  gate path.
- Online access: failure count and finite-shot fidelity only. Exact channel,
  state, hidden contexts, gradient, and Hessian are validator-only.
- Runtime: 1301.7 s (21.7 min), below the declared 55-minute limit.

The AOM model is a `HardwareTransferGraph` containing gain and one first-order
low-pass response fitted to the rasterized blue trace in paper Figure 4(a).
The optimum hits the 20 MHz bandwidth-search boundary and has MSE `0.0873`;
this is evidence that the simple response model is inadequate, not evidence
for a measured 20 MHz apparatus bandwidth.

## 4. Provenance classes

Use the following interpretation for every artifact:

- `independent_computation`: obtained by propagation, optimization, Hessian
  calculation, or finite-shot sampling in this run.
- `calibrated_anchor`: a simulator parameter fitted to one published number;
  it must not be counted as independent validation of that same number.
- `paper_literal`: transcribed from the paper because the microscopic data
  needed for a new calculation were unavailable.
- `external_calibration`: published calibration from another apparatus, used
  to exercise the analysis pipeline but not claimed to describe Liu’s camera.
- `unavailable`: author raw shots, exact AR phase array, AOM transfer function,
  microscopic noise spectra, or MQDT pairing table were not public.

## 5. Numerical results

| Quantity | Reproduction | Paper target | Interpretation |
|---|---:|---:|---|
| Figure 1 Hessian rank | 5 | 5 | independent mechanism match |
| Figure 1 lambda_6/lambda_1 | 1.222379e-16 | low-rank separation | independent |
| Figure 1 maximum principal FD error | 4.468553e-6 | approximately zero | verification |
| Figure 1 maximum null curvature/lambda_1 | 7.998850e-7 | approximately zero | verification |
| Figure 3 optimized infidelity | 2.226532e-9 | high-fidelity closure | independent equivalent pulse |
| Figure 3 maximum leakage | 3.644800e-9 | approximately zero | independent |
| Figure 3 Hessian rank | 10 | 10 | independent mechanism match |
| Figure 3 lambda_10/abs(lambda_11) | 7.346489e13 | strong rank gap | independent |
| Figure 3 principal FD error | 4.756397e-7 | approximately zero | verification |
| Figure 3 finite-bin lab/local spectrum difference | 2.2316% | threshold 2.0% | marginal miss; threshold not relaxed |
| Figure 4 raw CZ error | 4.570168e-3 | 4.0(5)e-3 | downstream simulator prediction |
| Figure 4 postselected CZ error | 5.346451e-4 | 1.0(2)e-3 | downstream simulator prediction |
| Figure 4 Appendix-E simulated postselected error | 5.346451e-4 | 6.6e-4 | 19% low |
| Figure 4 erasure fraction | 0.8835 | 0.75(6) | about 2.2 paper sigma high |
| AR intensity exponent | approximately 4.00 | quartic | qualitative mechanism match |
| Nonrobust intensity exponent | approximately 1.98 | quadratic | qualitative mechanism match |
| Simplified closed-loop initial error | 5.881218e-2 | decreasing trajectory | earlier injected-gap baseline |
| Simplified closed-loop final error | 1.224858e-4 | decreasing trajectory | earlier injected-gap baseline |

Enhanced Cold_Atom Gate Simu_Platform run:

| Quantity | Result | Interpretation |
|---|---:|---|
| wall time | 1301.7 s | below 55-minute limit |
| finite-shot initial error | `0.0173497 ± 0.0005839` | controller-visible |
| best public checkpoint | `0.0080698 ± 0.0004001` | after Hessian mode 9 |
| finite-shot final error | `0.0085098 ± 0.0004108` | mode-10 increase is shot fluctuation |
| exact coherent fidelity | 0.9979874 | no decay or stochastic ensemble |
| exact open raw fidelity | 0.9935862 | 42 us lifetime model |
| exact open no-loss fidelity | 0.9976167 | erasure postselection |
| 1 kHz combined-noise raw fidelity | about 0.99153–0.99225 | two independent 16-context estimates |
| 1 kHz combined-noise no-loss fidelity | about 0.99556–0.99628 | context uncertainty about `7e-4` |

Enhanced run error ablations:

| Source | Raw error increment | Provenance |
|---|---:|---|
| Rydberg lifetime / erasure | 4.4012e-3 | exact open-system propagation |
| Doppler | 1.0636e-3 | platform ablation |
| laser phase + 1 kHz linewidth | 4.8053e-4 | platform ablation |
| thermal position / varying blockade | 2.0692e-4 | platform ablation |
| finite blockade | 1.6e-4 | paper-calibrated, not independent |
| laser amplitude | 6.2946e-5 | platform ablation |

The effective-linewidth sweep gives total raw errors `7.44e-3`, `8.47e-3`,
`1.18e-2`, and `1.37e-1` at respectively 0.1 kHz, 1 kHz, 10 kHz, and
300 kHz. A product-catalog laser linewidth must therefore not be treated as
the locked experiment's effective 302-nm linewidth.

One-hour fixed-`k=10` gap/seed scan, with three finite-shot seeds per gap and
a two-cycle cutoff:

| AOM gap | final coherent error, mean ± sample std | target successes | queries to target, mean ± sample std |
|---:|---:|---:|---:|
| 0.03 | `(2.5293e-4 ± 3.8755e-5)` | 3/3 | `104.0 ± 10.4` |
| 0.11 | `(2.9916e-4 ± 1.4175e-4)` | 3/3 | `218.7 ± 62.9` |
| 0.70 | `(6.0059e-2 ± 1.4035e-2)` | 0/3 | not reached |

The scan establishes a finite model-gap failure boundary for the fixed model
Hessian subspace. It does not establish scaling with retained dimension.
The first uncached four-cycle cell required approximately 5.9 minutes, so the
multi-seed scan was capped at two cycles to remain within the declared
one-hour wall-time budget.

Figure 2 finite-shot camera results, 50,000 shots per prepared state:

| Prepared state | Outcome | Simulator | Liu Table I |
|---|---|---:|---:|
| `|0>` | assigned `0` | 0.98400 | 0.9875 |
| `|0>` | assigned `1` | 0.00328 | 0.0017 |
| `|0>` | loss | 0.01272 | 0.0107 |
| `|1>` | assigned `0` | 0.00328 | 0.0083 |
| `|1>` | assigned `1` | 0.98368 | 0.9753 |
| `|1>` | loss | 0.01304 | 0.0165 |

The Figure 2 fluorescence model uses the published Radnaev et al. 2025 fit
from a different apparatus. The single-qubit RB raw fidelity `0.99935` is an
explicit Liu-paper anchor, so Figure 2 RB is a pipeline-closure demonstration,
not an independent prediction.

## 6. Figure interpretation

### Figure 1

The figure shows the analytic pulse, Hessian spectrum and modes, and optimizer
trajectories. The rank-5 spectrum is the main scientific result. Panel (g) is
an explicitly labelled mechanistic reconstruction from the computed
two-cycle Hessian trajectory because the corresponding author trajectory is
not published.

### Figure 2

The figure exercises the complete observable boundary: photon counts,
classification, retention/loss, and randomized-benchmarking fits. Its value is
pipeline validation. It is not a recovery of Liu’s raw camera records.

### Figure 3

The figure shows the independently optimized 400-bin robust pulse, Rydberg
populations, rank-10 Hessian spectrum, principal modes, and error-channel
organization. Compare terminal closure, rank, mode separation, and channel
structure; do not compare the phase waveform point by point with the paper.

### Figure 4

The reproduced Figure 4 shows the earlier simplified AOM baseline,
finite-shot echoed RB, intensity robustness, stability, and the error budget.
The enhanced platform run is reported separately because it uses a different,
more complete forward model. Its feedback reduces the finite-shot error by
about 51%, but its raw and no-loss fidelities remain below the paper values.
The discrepancy is retained rather than removed by calibration; the dominant
unconstrained inputs are the measured complex AOM transfer, apparatus noise
spectra, and experiment-specific MQDT pair table.

## 7. Artifact map

- Human report: `report.html`
- Human report source: `report.json`
- Final images: `figures/reproduced/Figure_1.png` through `Figure_4.png`
- Paper comparison images: `figures/reference/Paper_Figure_1.png` through
  `Paper_Figure_4.png`
- Figure 1 source data: `data/figure1/data/`
- Figure 2 finite-shot records: `data/figure2/data/`
- Figures 3–4 manifest: `data/figures3_4/input.in`
- Figures 3–4 generated rows: `data/figures3_4/generated_input/`
- Figures 3–4 theory and fit records: `data/figures3_4/data/`
- One-hour gap/seed scan: `data/issue113_hour_scan/`
- One-hour scan figure: `figures/issue113/issue113_hour_scan.png`
- One-hour scan runner: `source/issue113_hour_scan.py`
- Enhanced platform run: `data/digital_twin/`
- Enhanced platform summary: `data/digital_twin/SUMMARY.md`
- Enhanced platform figure: `data/digital_twin/figs/digital_twin_summary.png`
- Enhanced platform machine result: `data/digital_twin/data/result.json`
- Enhanced platform runner: `source/liu_2026_complete_digital_twin.py`
- Reproduction code: `source/reproduce/`
- Simulator bridge: `source/liu_2026_simulator_input_bridge.py`
- Simulator modules: `source/simulator/src/cs_tweezer_sim/`
- Primary rendered reference: `references/liu_2026_paper_rendered.md`
- Citation and claim boundary: `references/CITATIONS.md`
- Original challenge summary: `references/ISSUE_113.md`

## 8. Reproduction entry points

Environment:

```bash
python -m venv .venv
.venv/bin/pip install -r source/reproduce/requirements.txt
export JAX_ENABLE_X64=true
export JAX_PLATFORM_NAME=cpu
export MPLCONFIGDIR=/tmp/liu-figures-mpl
```

Regression tests:

```bash
.venv/bin/python -m unittest discover \
  -s source/reproduce/tests -p 'test_*.py'
.venv/bin/python -m pytest -q \
  source/simulator/tests/test_s3b_waveforms.py \
  source/simulator/tests/test_s3c_stochastic.py \
  source/simulator/tests/test_s4a_dynamic_noise.py \
  source/simulator/tests/test_s4b_psd_stark.py \
  source/simulator/tests/test_s8_yb171_profile.py
```

Render Figures 2–4 from the bundled `input.in` and cached theory:

```bash
.venv/bin/python source/reproduce/liu_2026_fig234_reproduction.py \
  --stage experimental \
  --input-in data/figures3_4/input.in \
  --theory-run-dir data/figures3_4 \
  --run-dir data/figures3_4
```

The complete optimization is intentionally not launched by the above command;
its configuration is `data/figures3_4/source_constrained_standard.json`.

Re-run the enhanced digital twin from the submission root:

```bash
.venv/bin/pip install -e source/simulator
PYTHONPATH=source/simulator/src MPLCONFIGDIR=/tmp/liu-digital-twin-mpl \
  .venv/bin/python -u source/liu_2026_complete_digital_twin.py \
  --theory-dir data/figures3_4 \
  --paper-figure4 figures/reference/Paper_Figure_4.png \
  --output-dir data/digital_twin-rerun
```

## 9. Known limitations

1. No author experimental raw data were available.
2. The exact author AR waveform was not available.
3. The experiment-specific MQDT pairing table was not available.
4. Doppler and laser-noise budget entries that require unpublished
   microscopic samples or spectra remain paper literals.
5. Figure 3 has one marginal fixed-threshold miss: 2.2316% versus 2.0%.
6. Figure 4’s calibrated blockade anchor cannot validate itself.
7. The main claims are therefore mechanism reproduction, source-constrained
   equivalent control, and effective digital-twin closure—not apparatus-level
   experimental duplication.
8. The fixed-`k=10` three-gap, three-seed scan is complete within its declared
   two-cycle budget, but the Issue #113 headline dimension sweep, fair
   full-400 baseline, cross-system `d^2-1` test, and shot-budget sweep remain
   incomplete.
9. Estimated reasons/times for the remaining work: dimension sweep plus a fair
   full-400 baseline requires code generalization and many more queries
   (`0.5–1 day`); a shot-budget sweep multiplies the existing cells
   (`1–2 additional hours`); controlled `d=2,4,8` models require new model and
   acceptance definitions (`0.5–1 day`); iterative device-informed subspace
   re-estimation is a research extension (`1–2 days`); real-hardware closure
   is unavailable without device access and author data.
10. The enhanced AOM fit reaches the 20 MHz search boundary with raster
    MSE `0.0873`; a gain plus one-pole response cannot represent measured
    ringing, chirp, or I/Q cross-coupling.
11. The enhanced final ablations use only 16 stochastic contexts. Two
    independent nominal 1 kHz context sets differ by about `7e-4`, so the
    stochastic ensemble mean is not converged below that scale.
12. Finite shots are sampled after averaging the hidden-context ensemble
    rather than by repropagating every shot; this explicit approximation keeps
    the full run below one hour.
