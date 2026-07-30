# Issue #86 Track A cutoff report

This report freezes the successful results available at the time cutoff. It
does not wait for the remaining Slurm cells and never treats missing cells as
zeros or imputes them.

## Frozen data

- Original production: 96/96 successful cells.
- Large-size snapshot: 36 successful cells with matching summary, raw-block,
  and metadata files: 30 central-beta cells and 6 partial crossing cells.
- Central-beta coverage reaches L=2048 for every sigma. Sigma=2.5 is missing
  one of two seeds at L=1024 and L=2048; the other central points have two.
- Clock production: 16/16 cells with matching summary, raw-block, and metadata
  files and empty stderr.
- The six large-size crossing cells do not form the complete registered grid,
  so no crossing extrapolation is claimed from them.

## Largest-size central values

| sigma | Rp(L=2048) | Qm(L=2048) | seeds |
|---:|---:|---:|---:|
| 1.75 | -0.376800(16) | 0.76486(21) | 2 |
| 1.875 | -0.1885(103) | 0.80589(17) | 2 |
| 2.0 | -0.076125(19) | 0.83474(11) | 2 |
| 2.5 | 0.01065 | 0.85351 | 1 |

At sigma=1.875, the L=2048 values are within about 1.35 combined standard
errors for Rp and 1.11 for Qm of the published thermodynamic estimates
Rp=-0.207(9) and Qm=0.815(8). This is a successful finite-size reproduction.

## Locked competing-model analysis

The analysis used 1000 parametric-bootstrap replicas.

For the complete L=64--2048 window:

| sigma | observable | AICc power | AICc marginal | absolute difference |
|---:|---|---:|---:|---:|
| 1.875 | Rp | 17.54 | 17.36 | 0.18 |
| 1.875 | Qm | 13.99 | 14.06 | 0.07 |
| 2.0 | Rp | 19.06 | 19.12 | 0.06 |
| 2.0 | Qm | 20.95 | 21.04 | 0.10 |

These scores are statistically indistinguishable. Removing smaller sizes
destabilizes the inferred limits rather than selecting one correction form.
The registered forecast does not reach 3-sigma separation by L=65536 for any
sigma or primary observable.

Several sigma=1.75 fits and the sigma=2.5 Rp fits have poor absolute
chi-square or hit parameter bounds. Their formal thermodynamic limits are fit
pathology and are not interpreted physically. By contrast, the sigma=2.5 Qm
power fit gives 0.85623 with a 16--84% bootstrap interval
[0.85494, 0.85851], which contains the known short-range value near 0.857 and
serves as a useful end-to-end control.

## Independent Clock comparison

Clock agrees with FK through L=256 at both tested sigmas. All six such points
pass the preregistered 3-sigma gate.

At L=512, Clock Qm differs from FK by -3.21 sigma at sigma=1.875 and -4.38
sigma at sigma=2.0. The corresponding maximum integrated autocorrelation
times are about 7,860 and 8,372 sweeps. The one-million-sweep local-update run
is therefore not sufficiently mixed at L=512. This is an algorithmic
convergence limit of this Clock implementation and sampling budget, not
evidence against the FK physics result. The raw failed-gate results are
retained.

## Cutoff conclusion

1. The published finite-size trends and the sigma=2.5 short-range control are
   reproduced.
2. Large sizes through L=2048 move smoothly toward the published critical
   estimates.
3. Power and marginal/log corrections remain indistinguishable and
   size-window unstable. The crossover boundary cannot be adjudicated from
   this data without violating the locked honesty rule.
4. A useful new negative result is obtained: at the achieved uncertainty,
   the two correction scenarios are not forecast to separate by 3 sigma even
   at L=65536 under the registered model; independent local Clock dynamics
   also becomes impractically slow by L=512.

The scientifically defensible final label is:

**finite-size reproduction successful; thermodynamic discrimination
inconclusive at the completed accessible scales.**
