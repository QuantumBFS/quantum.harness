# Issue #147 Minimal Figure Design

## Goal

Produce the smallest defensible figure set before the hackathon deadline using
only completed h=3 calculations. Do not launch additional h, D, or delta-beta
scans for presentation purposes.

## Figure 1: Thermodynamic comparison

Create a two-panel comparison over beta:

- Internal energy per site, u(beta).
- Specific heat per site, C(beta).

Show ordinary PEPO and thermodynamic PEPO with distinct line styles and
markers. Show 10x10 QMC with statistical error bars. Show 4x4 ED only when its
finite-size diagnostic role is explicit in the title or legend.

## Figure 2: Available convergence evidence

Create a two-panel diagnostic:

- QMC internal energy near beta J = 0.5 against (beta/M)^2 for the available
  M = 32, 64, and 128 data.
- The relative change in PEPO internal energy from chi = 16 to chi = 32 over
  beta, with the existing 0.1% diagnostic line.

This figure supports only QMC Trotter extrapolation and boundary-contraction
stability. It must not imply convergence in PEPO bond dimension or imaginary-
time step.

## Evidence and fallback rules

- Use only fetched outputs that pass the run-spec and success-manifest checks.
- Do not interpolate, synthesize, or silently omit failed methods or beta
  points.
- If a required data series is incomplete, report it as incomplete instead of
  producing a misleading comparison.
- State that D = 4 and delta_beta = 0.025 are fixed-budget choices whose
  convergence was not assessed.
- Treat 4x4 ED as a finite-size diagnostic, not the 10x10 thermodynamic
  reference.

## Output and acceptance

Export both figures as 300 DPI PNG and vector PDF. Keep the existing
colorblind-safe colors and redundant line/marker encodings. The deliverable is
accepted when the figures are generated from validated real outputs and the
summary records the two unassessed convergence directions explicitly.
