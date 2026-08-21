# Figures 3–4 and Table 3 Revision Design

## Scope

Revise reviewer-facing presentation only. Existing numerical JSON, raw data,
fit outputs, and validation artifacts remain unchanged.

## Figure 3

- Keep the existing gap comparison as panel **A**.
- Keep the existing gap-based pairwise effective-exponent comparison as panel
  **B**.
- Add bold uppercase panel labels.
- Remove the former estimator-summary panel C because Table 3 already reports
  those values.

## Figure 4

- Replace the gap plot with a single plot of the four sigma=1.8 gap-based
  pairwise effective dynamical exponents against
  `L_eff=sqrt(L1*L2)`.
- Draw the stored power-correction sensitivity
  `z_eff=z_power+a/L_eff`.
- Mark the fitted asymptote `z_power=0.918948`.
- Show the Shiratani–Todo QMC power-correction result `0.93(2)` as a dotted
  reference line. Do not plot the logarithmic correction in this figure.

## Table 3

Replace the rounded sigma=1.8 reference entry with the published uncertainty:
`0.93(2) / 1.00(3)`.

## Verification

- Test the Figure 3 panel count and labels.
- Test the Figure 4 axes and the stored power-correction curve.
- Test the exact Table 3 reference text.
- Render both figures and inspect them at final resolution.
