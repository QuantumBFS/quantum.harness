# Liu et al. Figures 1–4 audit changelog

- Added an opt-in, source-constrained Figure 3(b) backend at the existing
  basis/kernel seams: fixed sinusoidal-edge flat-top amplitude, 400
  piecewise-constant phase controls, and the common-α first-order residual.
  Preserved the CLI, `input.in`, default backends, waveform archive contract,
  and provenance boundary; documented why the unpublished phase remains a
  non-unique equivalent reoptimization rather than a waveform match.
- Upgraded `input.in` to schema v2 with collaborator-facing atomic-state,
  laser, magnetic-field, geometry, waveform, Zeeman/polarization, MQDT,
  distance, decay, and noise-spectrum inputs. Added strict CSV/inline
  validation, legacy schema-v1 compatibility, a physical-input audit output,
  and an explicit no-silent-consumption boundary for the ten-state Hessian.
- Restored the independently runnable Figure 1(a–i) reconstruction. Panel
  1(g) is explicitly labelled as a mechanistic reconstruction from the
  computed two-cycle Hessian trajectory rather than experimental recovery.
- Corrected reproduction claims and added strict panel-level provenance.
- Replaced hard-coded run choices with nested configuration dataclasses,
  three run profiles, resolved configuration output, and config/code cache
  validation.
- Made JAX optional for the NumPy-only MWE.
- Audited the Appendix-C Hamiltonian, signs, √2 factors, units, basis order,
  detuning convention, propagators, and fidelity normalization.
- Added generic multistarts, spline/time-bin backends, branch-safe AR
  residuals, staged coarse/fine optimization, and final-manifold smoothing.
- Added fixed standard CZ, fixed nominal virtual-Z, and pointwise
  CZ-equivalent fidelity conventions.
- Corrected Figure 3(c) to total Rydberg population for each computational
  input and saved wrapped/unwrapped phase.
- Implemented the paper laboratory I/Q Hessian and a separate local-frame
  diagnostic, signed spectra, resolution studies, central finite differences,
  null tests, and channel decomposition.
- Renamed the non-robust comparison as a same-duration surrogate and added
  directional, baseline-aware intensity fits.
- Rebuilt synthetic AOM calibration as plant-in-loop, removed oracle scan
  information, and serialized mutually consistent command/output arrays.
- Split all experimental data contracts and analysis pipelines by panel.
- Renamed the reported Figure 4(f) stage and displayed missing values as
  missing rather than zero.
- Expanded automated tests across physics, numerics, fidelity, Hessian, CLI,
  cache, serialization, and provenance.
- Removed obsolete Hessian/AOM implementations and unused compiled kernels so
  prohibited clipping and oracle formulas do not remain as dormant code paths.
- Added propagation-spectrum, lab/local-frame, and null-space finite-difference
  acceptance checks plus post-write synthetic archive validation.
- Added the user-editable input.in manifest interface, inline synthetic test
  rows for all ten experimental panels, CSV path support, and per-panel
  provenance/summary outputs.
- Added manifest-driven PNG rendering for all ten experimental pipelines plus
  a single overview image, with visible synthetic/experimental provenance.
- Corrected Figure 2(a) to first/second-image photon counts and added
  paper-matched grouped layouts: Figure 2 as a/b, Figure 3 as a-b-c/d-e, and
  Figure 4 as a-b-c/d-e-f; standalone panel plots are diagnostics only.
