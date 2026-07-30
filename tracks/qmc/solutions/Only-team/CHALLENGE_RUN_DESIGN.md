# Challenge #148 production-run design

> **Record status:** approved design snapshot. The initial production scan is
> complete; see `CURRENT_STATUS.md` for the latest result and active recovery
> calculations.

## Objective

Determine whether

```text
R = h_c(triangular) / h_c(honeycomb)
```

is exactly `√5`, while improving the 2002 uncertainty by at least a factor
of five.

Blöte and Deng, Physical Review E 66, 066110 (2002), report:

| Lattice | Lmin | Lmax | Critical field |
|---|---:|---:|---:|
| triangular | 6 | 20 | 4.76811(9) |
| honeycomb | 10 | 20 | 2.13250(4) |

Thus the PRE honeycomb calculation stopped at **L=20**.  The corresponding
central ratio is `2.2359249707`, while `√5=2.2360679775`; their difference is
`−0.0001430068`.  Propagating the reported PRE field errors gives a ratio
uncertainty of about `5.95×10⁻⁵`, so the 2002 central value is only about
2.4 standard errors below `√5`.

The challenge targets are:

```text
σ[h_c(triangular)] ≤ 1.8×10⁻⁵
σ[h_c(honeycomb)]  ≤ 8.0×10⁻⁶
σ[R]               ≤ 1.19×10⁻⁵
```

The final quoted fifth decimal must also remain stable under finite-size fit
and time-step variations.

Source:
`doi:10.1103/PhysRevE.66.066110`, especially Table I and Eq. (23).

## Locked physical setup

```text
H = J1 Σ_<i,j> σᶻ_i σᶻ_j − h Σ_i σˣ_i

J1 = −1
J2 = 0
periodic boundaries
triangular and honeycomb lattices
```

The PRE anisotropic mapping has `M=βh/ε`, and the physical imaginary-time
length is chosen equal to `L`.  Therefore every production cell uses

```text
βh = L
β = L/h
```

For a requested time step `FixedDltau`, configuration derivation remains:

```text
LTrot = ceil(β/FixedDltau)
if LTrot is odd, LTrot += 1
actual Dltau = β/LTrot
```

Fits and metadata use the actual `Dltau`, not only the requested value.

## Sampling algorithm

The validated sampler is unchanged:

```text
nLocal = 1
nWolff = 5
local sweep followed by ordinary Wolff updates
32 deterministic independent MPI chains per cell
```

No tau-Wolff, geometry update, continuous-time update, or additional
observable is introduced.

The challenge calculation uses the already validated implementation without
changing its allocation behavior.  No Wolff buffer reuse and no
`nLocal=0`/`nLocal=1` comparison is performed before the time-limited scan.

## Production grid

### Main finite-size grid

Use the following time-limited main grids:

```text
triangular: L = 8, 12, 16, 20, 24, 32, 40, 48
honeycomb:  L = 10, 12, 16, 20, 24, 28, 32
FixedDltau = 0.013
```

At each size, use seven fields centered on the PRE result:

```text
triangular:
4.76511, 4.76611, 4.76711, 4.76811,
4.76911, 4.77011, 4.77111

honeycomb:
2.12950, 2.13050, 2.13150, 2.13250,
2.13350, 2.13450, 2.13550
```

This is 56 triangular cells and 49 honeycomb cells.  A spacing of 0.001
brackets the transition while the multi-size scaling fit interpolates the
critical field.  It does not by itself set the final field uncertainty.
The triangular maximum `L=48` is 2.4 times the PRE maximum; the honeycomb
maximum `L=32` is 1.6 times the PRE maximum.

### Time-step grid

After the main fit, use the current step and two larger requested steps:

```text
triangular: L = 32, 40, 48
honeycomb:  L = 24, 28, 32
FixedDltau = 0.013, 0.016, 0.020
```

For each lattice and time step, use five fields centered on the preliminary
critical field:

```text
h_preliminary − 0.0010
h_preliminary − 0.0005
h_preliminary
h_preliminary + 0.0005
h_preliminary + 0.0010
```

The `Dltau=0.013` cells are reused from the main grid, so the two additional
steps add 60 cells.  The three fitted critical fields are extrapolated
linearly in actual `Dltau²`.  The two Binder-ratio trends toward or away from
`0.5` are recorded as a diagnostic; closeness to `0.5` is not used to select
the fit or discard a step.  If the three points do not support a linear
`Dltau²` description, add `FixedDltau=0.010` at the three largest sizes
instead of forcing the extrapolation.

### Conditional large sizes

`L=48` is the planned triangular maximum and `L=32` the planned honeycomb
maximum, compared with `L=20` for both in PRE.  Do not add a larger size
unless either condition occurs after the planned grid is complete:

1. changing the finite-size fit from `Lmin=16` to `Lmin=24` moves `h_c` by
   more than half of its combined standard error; or
2. removing the largest planned size moves `h_c` by more than half of its
   combined standard error.

The only conditional sizes are triangular `L=56` and honeycomb `L=36`.
Each first uses three fields at the fitted center and `h_c±0.0005`, with
requested `Dltau=0.013`.  No conditional size is started if its conservative
wall estimate would cross the challenge deadline.

## Per-cell statistical budget

The initial production budget is:

```text
nprocs = 32
nWarm = 10000
NmBin = 32
NSwep = 2000
NmMeaConfg = 10
discard_initial_bins = 1
trim_extrema = true
statistics_mode = "bin_sem"
```

Every cell therefore has 2,048,000 rank-level formal measurements before
bin filtering.  The following acceptance gates are applied before fitting:

- all 32 bins and all 32 distinct rank seeds are present;
- the first/second-half combined z-score is at most 3 for both m² and Q;
- no nonfinite bin is present;
- for `L≥40`, target `SEM(Q)≤1.0×10⁻⁴` on triangular and
  `SEM(Q)≤1.5×10⁻⁴` on honeycomb.

A cell that fails only the SEM target is repeated with `NSwep=4000` under a
new output directory.  Failed and extended runs are never silently merged;
their manifests identify the accepted budget.

## Finite-size and time-step analysis

For each lattice and time step, fit the PRE form

```text
Q_L(h) =
    Q*
    + a1(h−h_c)L^yt
    + a2(h−h_c)²L^(2yt)
    + b1 L^yi
    + b2 L^(2yi)
    + c1(h−h_c)L^(yt+yi)
```

with the 3D Ising values used by PRE:

```text
yt = 1.587
yi = −0.815
```

`Q*` is fitted independently for triangular and honeycomb lattices because
the metric factor and chosen aspect ratio can change its value.

The result table includes:

- fits with `Lmin=12,16,20,24`;
- fits with and without `a2`, `b2`, and `c1`;
- bootstrap uncertainty and fit quality;
- the `Dltau²→0` extrapolation;
- `R=h_c(triangular)/h_c(honeycomb)`;
- `R−√5` and its propagated uncertainty.

No fit is selected only because its central value is closer to `√5`.

## Server layout and measured cost

The target partition is `xhacnormalb`.  A read-only probe on 2026-07-29
showed 128 CPU cores and about 513.5 GB memory per node.

Each cell requests:

```text
32 CPU cores
64 GB memory
one MPI rank per core
```

Four cells can fit on one node.  Arrays use a concurrency limit of eight
cells, allowing roughly two fully occupied nodes without releasing all
cells at once.

The unoptimized honeycomb pilot at `L=28`, `h=2.1325`, and actual
`Dltau=0.012974435727889014` completed the QMC phase in
`459.50855588912964` seconds:

| Quantity | Measured value |
|---|---:|
| MPI ranks | 32 |
| peak step RSS | about 16.0 GB |
| update cycles per rank | 5,000 |
| mean cluster size | 50,616.97 |
| mean cluster fraction | 0.03189845 |
| local acceptance | 0.0459153 |
| `m²` | 0.03610317(31) |
| Binder `Q` | 0.55052(32) |

The formal bins constructed 640,000 clusters across all ranks.  The measured
wall time already includes the current allocation behavior and is therefore
the conservative basis for the deadline estimate.

Linear scaling from the measured pilot puts the present 74,000-cycle
honeycomb `L=28` budget at about 1.89 cell-hours.  Scaling the verified
triangular benchmark by actual spacetime volume gives:

| Triangular size | Raw cell-hours | 30% safety |
|---:|---:|---:|
| 24 | 0.34 | 0.45 |
| 28 | 0.54 | 0.71 |
| 32 | 0.81 | 1.06 |
| 40 | 1.59 | 2.06 |
| 48 | 2.74 | 3.56 |

The full triangular main grid through `L=48` is about 40.9 raw cell-hours, or
53.2 cell-hours with the 30% safety factor.  At eight concurrent cells its
scheduler running time is about 6.7 hours, excluding queueing.  The honeycomb
main grid through `L=32` is about 50.3 raw cell-hours, or about 65.4
cell-hours with the same safety factor.

The pilot error scales only to roughly `SEM(Q)≈6.6×10⁻⁴` under the initial
32-rank, 32-bin, 2,000-sweep budget.  Therefore the main grid is a crossing
and correction scan.  Any precision extension is concentrated on the three
largest sizes and the fields nearest the crossing and uses the same validated
32-rank update path.

Initial requested cell wall limits:

```text
minimum-size extreme cells:       01:00:00
maximum-size extreme cells:       06:00:00
intermediate main-grid cells:     04:00:00
conditional large-size cells:     only if deadline permits
```

The first production submission contains the smallest and largest approved
sizes:

```text
minimum: triangular L=8, honeycomb L=10
maximum: triangular L=48, honeycomb L=32
seven h values per lattice and size
FixedDltau=0.013
```

The minimum-size and maximum-size arrays are submitted together so the small
results become available while the deadline-critical large cells are already
running.

## Completion criteria

The challenge calculation is complete only when:

1. every accepted cell has a complete manifest, bins, seeds, metadata, and
   recorded output hash;
2. the critical fields are stable under declared `Lmin` and correction-term
   variations;
3. the `Dltau²→0` extrapolation is statistically resolved;
4. the individual field and ratio uncertainty targets are met;
5. the fifth decimal is unchanged by every accepted analysis variant;
6. the ratio comparison reports both `R−√5` and its uncertainty, regardless
   of whether the result supports or excludes exact `√5`.

No production job is submitted and no Git operation is performed without a
separate explicit confirmation.
