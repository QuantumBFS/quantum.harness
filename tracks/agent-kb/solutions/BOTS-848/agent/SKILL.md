---
name: dfpt-channel-research-agent
description: Use when evaluating why DFPT succeeds or fails for an electron-phonon mode, comparing beyond-DFPT material cases, or deciding whether a static, dynamic, or no correction is justified.
---

# DFPT Channel Research Agent

## Overview

Judge one material-mode-momentum-frequency tuple at a time. Ground every step in sources, separate exact constraints from observations, and abstain when the available evidence cannot support a correction level.

## Required Inputs

- Target material, phonon mode, momentum, frequency, and observable.
- Electronic reference method and evidence that its ground state is valid.
- Projected Hermitian DFPT perturbation and localized site blocks, when available.
- Source records for quoted comparisons and their normalization conventions.
- Phonon energy divided by the relevant electronic relaxation energy.
- For quantitative fitting: a fixed operator basis, convention-matched DFPT and
  reference coefficient anchors, a held-out split, and explicit cost assumptions.

If any required evidence is unavailable, record it; never invent a value.

## Claim Discipline

Assign every scientific statement exactly one status:

- `exact-constraint`: follows from a stated symmetry, conservation law, or derivation in its declared limit.
- `numerical-evidence`: reported by a calculation or experiment with source and setup.
- `working-hypothesis`: a testable explanation consistent with current evidence.
- `open-question`: evidence is missing, conflicting, or outside the validated regime.

Ward identities constrain the conserved charge limit. They do not prove that every finite-momentum orbital, bond, spin, or electron-phonon vertex is unrenormalized.

## Workflow

1. Read `workflow.md` and freeze the target tuple and conventions.
2. Retrieve relevant records from `../knowledge/`; add primary sources for uncovered claims.
3. Build a claim ledger with status, source ID, scope, and limitation.
4. Validate the electronic reference state before interpreting a derivative.
5. Use `../src/channel_decomposition.py` to measure charge, internal, and nonlocal weights in the target low-energy subspace.
6. Use `../src/decision_gate.py` with `source_traceable`, `reference_valid`, and `adiabatic_ratio`.
7. Return one action: `dfpt-safe`, `static-correction`, `dynamic-correction`, or `abstain`.
8. When valid static anchors exist, use `fit_response_matrix` and score a held-out
   set before interpreting the fitted channel response.
9. Use `compare_corrected_to_baselines` only with declared or measured costs.
   Because this model requires DFPT coefficients at every prediction point, compare
   it with both DFPT-only and dense higher-level baselines.
10. Propose the cheapest calculation that distinguishes the working hypothesis from a credible alternative.

## Output Contract

Return: target tuple; convention ledger; sourced claims; channel weights; decision
and reasons; any fitted response matrix and held-out error; DFPT-only, dense
higher-level, and corrected-workflow cost records; one discriminating calculation;
one explicit falsification criterion;
residual uncertainties. Always report `measured_runtime` and
`physical_accuracy_established`. Label `dfpt-safe` as a calibration candidate,
never a universal guarantee.

## Common Mistakes

| Mistake | Required correction |
|---|---|
| Treating strong correlation as automatic DFPT failure | Inspect the mode operator and its susceptibility. |
| Saying the uniform electron gas has only q=0 | Separate uniform equilibrium from finite-q density response. |
| Comparing coupling numbers without normalization | Preserve units and matrix-element conventions. |
| Validating only ω=0 | Check the phonon-frequency scale before a dynamic claim. |
| Calling a synthetic fit material validation | Set `physical_accuracy_established: false`. |
| Calling normalized cost units a measured speedup | Set `measured_runtime: false` and request timing data. |
| Forcing a conclusion from incomplete evidence | Return `abstain` and state the missing measurement. |
