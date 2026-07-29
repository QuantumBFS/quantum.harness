# Phase 8 critical-field sensitivity at sigma=1.75

This branch keeps the original DMRG crossing result at
Gamma=1.573850488705473 and independently evaluates all final energies
at the external Shiratani--Todo benchmark Gamma=1.5609. The
external field is a sensitivity coordinate, not a replacement or a
field-selection criterion.

The direct gap regressions give z=0.70934904
at the self-consistent field and z=0.88015388
at the published field. The effective-exponent power-correction results are
0.55881828 and
0.90324532; the logarithmic
results are 0.20019604 and
0.95926329.

Relative to Shiratani--Todo's published power/log values, the discrepancy
is reduced
by using the external field. This statement describes sensitivity only;
`field_selected_by_outcome` remains false. No Gamma search, larger size,
sigma extension, or K=32 calculation was performed.

Selective chi=256 refinements: 2. Every chi=128 baseline,
including failed convergence diagnostics, is retained in `analysis.json`;
final gaps use only accepted states.
