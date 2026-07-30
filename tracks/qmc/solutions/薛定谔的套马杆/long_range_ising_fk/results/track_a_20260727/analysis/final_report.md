# Issue #86 Track A reproduction report

## Data integrity

- Slurm array 22958313: 96/96 cells completed with exit code 0:0.
- 96 summaries, 96 raw-block files, 96 metadata files, and zero non-empty stderr logs.
- Each cell used 10,000 thermalization and 100,000 measurement sweeps with two independent seeds per point.
- Coupling normalization errors are at floating-point roundoff.

## Critical finite-size values

| sigma | Rp(L=64) | Rp(128) | Rp(256) | Rp(512) | Qm(512) | eta, L>=64 | eta, L>=128 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1.75 | -0.57267 | -0.53124 | -0.50906 | -0.45422 | 0.74199 | 0.3834 | 0.3729 |
| 1.875 | -0.40894 | -0.36351 | -0.30338 | -0.27176 | 0.78523 | 0.3290 | 0.3204 |
| 2.0 | -0.27337 | -0.21115 | -0.18811 | -0.13079 | 0.81589 | 0.2962 | 0.2915 |
| 2.5 | -0.03368 | -0.00506 | 0.00267 | 0.00919 | 0.85208 | 0.2541 | 0.2546 |

## Assessment

The finite-size trends are reproduced: Rp and Qm vary smoothly with L; sigma=2.5 approaches the short-range anchors (Rp=0, Qm=0.857, eta=0.25), while sigma<=2 remains visibly separated at L=512.
At sigma=1.875, L=512 gives Rp=-0.27176 and Qm=0.78523, moving toward the published thermodynamic estimates -0.207(9) and 0.815(8). The school-scale eta estimates (0.3290 using L>=64 and 0.3204 using L>=128) remain above the published 0.293(3), demonstrating the stated strong finite-size corrections.
The unrestricted three-parameter correction fits are weakly identified with only four sizes; after dropping L=64 they are underdetermined. Power and logarithmic corrections produce model-dependent limits, and AICc is undefined for n=4,k=3. BIC is reported, but it is not sufficient for a stable boundary verdict.

**Locked conclusion: finite-size reproduction successful; thermodynamic discrimination between the competing crossover scenarios is inconclusive at L<=512.**

This follows Issue #86's no-one-fit rule and is not a failure: the raw data reproduce the expected school-scale drift, but do not justify selecting a thermodynamic scenario.
