# Human-report figure plan

> Planning and asset-source file. Curated PNG previews are embedded directly
> in `../main.md`; readers do not need to open this directory.

## Figure 1 — Model and computational workflow

- Stored as `figure-01-workflow.svg` and embedded in `../main.md`: exact
  periodic Hurwitz-zeta coupling → constrained
  exponential fit → direct/wrapped MPO channels → even/odd parity DMRG →
  Rξ crossings and parity gaps.

## Figure 2 — Validation summary

- Panel A: nearest-neighbor Rξ crossings near Γ=1.
- Panel B: σ=2/3 gap-based pairwise `z_eff` versus `L_eff`, with the
  power-correction sensitivity and z=1/3 guide.
- Source data:
  `../../results/phase9-validation/final-report/analysis.json`,
  `nn-gaps.csv`, and `mean-field-sigma-2over3-gaps.csv`.
- Panel A retains the nearest-neighbor gap validation.
- Panel B shows the σ=2/3 gap-based pairwise `z_eff` versus this DMRG
  analysis's logarithmic midpoint `L_eff`, with the accepted
  `z_eff=z+a/L_eff` power-correction sensitivity and the z=1/3 guide.
- The uncomputed σ=0.4 panel is excluded.

## Figure 3 — σ=7/4 dynamical scaling

- Panel A: gaps versus L for the self-consistent and published-field branches.
- Panel B: gap-based pairwise `z_eff` drift at the published Γc=1.5609.
- Use bold uppercase panel labels A and B.
- Source:
  `../../results/phase8-scaling/sigma-1.75/sensitivity-Gamma-ST/analysis/`.

## Figure 4 — σ=1.8 dynamical scaling

- Show gap-based pairwise `z_eff` against `L_eff=sqrt(L1*L2)` at the
  published Γc=1.5288.
- Plot the stored power-correction sensitivity `z_eff=z_power+a/L_eff`,
  its asymptote, and the Shiratani–Todo QMC `z=0.93(2)` reference line.
- Leave the direct-gap and logarithmic-correction values in Table 3 rather
  than duplicating them graphically.
- Source: `../../results/phase9-validation/sigma1.8-z/report/`.

## Excluded from the human figure set

- Checkpoint/provenance diagrams, runtime plots, and the redundant numerical
  uncertainty figure; Table 4 presents the latter more clearly.
- Raw Phase 2 fit sweeps and unsuccessful tail-window variants.
- Phase 7 provisional gap and mislabeled equal-time “gamma/nu” plots.
- The σ=0.4 DMRG benchmark, which was not run after the MPO-bias gate failed.
