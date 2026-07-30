# Phase 7 long-range crossover scan design

## Objective

Map the finite-size critical behavior of the periodic long-range
transverse-field Ising chain across
`sigma = 1.50,1.60,1.70,1.75,1.80,1.90,2.00`. The scan is exploratory: it
estimates the two-size crossing `Gamma_x(sigma)` and effective dynamic
exponent `z_eff(32,64)` without claiming a thermodynamic-limit crossover
point.

## Fixed physics setup

The Hamiltonian is

```text
H = -sum_{i<j} J_L(j-i;sigma) Z_i Z_j - Gamma sum_i X_i,
```

where `J_L` is the pinned periodic Hurwitz-zeta image sum. TeNPy evaluates
the Hamiltonian in the rotated parity basis:

```text
X_phys = Sigmaz
Z_phys = Sigmax.
```

Ground states use the even spin-flip sector and first excitations use the
odd sector. The correlation observable is the full physical correlation
function without connected-correlation subtraction. The exploration scan
uses `K=24`, `chi=64`, and `L=32,64`. Exact-zero MPO pruning, HDF5
checkpoints, and the validated custom periodized exponential MPO remain
enabled. Approximate MPO compression remains forbidden.

## Two-pass Gamma protocol

### Pass 1: common broad grid

Every sigma uses the identical preregistered grid

```text
Gamma = 1.20, 1.25, ..., 1.90.
```

The planner stores both the ordered values and their content hash. For each
point it calculates the even-sector state and records

```text
D_sigma(Gamma) = R_xi(32,Gamma) - R_xi(64,Gamma).
```

No literature value or expected critical field can change this grid.

### Deterministic bracket decision

After all broad-grid cells for one sigma are complete, adjacent points are
examined in ascending Gamma order. A bracket is an interval
`[Gamma_j,Gamma_{j+1}]` satisfying either an endpoint zero or a strict sign
change in `D_sigma`.

- Exactly one bracket: generate the refinement record.
- No bracket: mark the sigma `unresolved_no_bracket`.
- More than one bracket: mark the sigma `unresolved_multiple_brackets`.
- Missing or failed broad cells: mark the decision `incomplete`.

Unresolved or incomplete cases require review. The planner does not extend
the grid, select a preferred crossing, or launch additional calculations.

### Pass 2: fixed bracket refinement

For the unique observed broad bracket, the refinement grid is

```text
Gamma_refine = Gamma_left, Gamma_left + 0.01, ..., Gamma_right.
```

Because the broad spacing is exactly `0.05`, this always contains six
points. Existing endpoint results are reused after provenance validation.
The final crossing uses linear interpolation between the adjacent refined
points that uniquely straddle zero:

```text
Gamma_x = Gamma_a
          - D_sigma(Gamma_a)
            * (Gamma_b - Gamma_a)
            / (D_sigma(Gamma_b) - D_sigma(Gamma_a)).
```

The decision record preserves the broad bracket, refinement grid, final
interpolation points, their `R_xi` values and signed differences, and
`Gamma_x`. It also records the interpolation resolution

```text
delta_Gamma_grid = (Gamma_b - Gamma_a) / 2,
```

which is `0.005` for the planned refined grid. This is a conservative
grid-resolution indicator, not a statistical error bar. Later comparisons
must report a sigma-to-sigma crossing drift alongside both points'
`delta_Gamma_grid` values so sub-resolution changes are not overinterpreted.
Multiple or absent refined brackets are reported as unresolved. There is no
adaptive optimization of `Gamma_x`.

## Gap and effective-exponent protocol

Odd-sector calculations are added only at the two final refined
interpolation points `Gamma_a` and `Gamma_b`, for both sizes. The gap

```text
Delta(L,Gamma) = E_odd(L,Gamma) - E_even(L,Gamma)
```

is linearly interpolated to the common `Gamma_x`. The exploration estimate
is the gap-based pairwise effective dynamical exponent

```text
z_eff(32,64) = -log[Delta(64,Gamma_x)/Delta(32,Gamma_x)] / log(2).
```

This is a DMRG gap-slope diagnostic, not a QMC aspect-ratio estimator. Raw
endpoint energies and gaps remain authoritative. A nonpositive gap,
missing sector, or provenance mismatch makes `z_eff` unavailable rather
than triggering an automatic retry with larger `chi`.

## Selective chi validation flags

`chi=64` remains the exploration default. A completed cell is retained but
marked `needs_chi128_validation` if any of these deterministic checks fail:

- the DMRG engine reports non-convergence or reaches its sweep cap;
- the relative variance
  `variance / max(E^2,1)` exceeds `1e-10`;
- maximum discarded weight exceeds `1e-8`;
- `R_xi`, `xi`, `S(0)`, or `S(k_min)` is nonfinite, or the second-moment
  expression has `S(0) < S(k_min)`;
- an odd-sector energy is not above its matching even-sector energy;
- either endpoint gap or the gap interpolated to `Gamma_x` is nonpositive.

Flags are collected per observable and per sector. They propose selective
`chi=128` validation at the affected sigma/size/Gamma only; they do not
silently replace the `chi=64` result, trigger a rerun, alter the Gamma grid,
or block unrelated sigma values.

## Resumability and provenance

The scan has three immutable artifacts:

1. a broad-grid run specification;
2. one refinement-decision record per sigma;
3. a targeted-gap run specification derived from accepted refinement
   records.

Each cell has a stable identifier derived from sigma, size, Gamma, sector,
K, and chi. Successful compatible cells are skipped on resume; failed,
missing, or incompatible cells remain visible. Every manifest records:

- `sigma`, `L`, `Gamma`, parity sector, `K`, `chi`, `alpha`, and `r_fit`;
- exponential-fit identifier, coefficient hash, and broad-grid hash;
- MPO/operator convention, active channels, lattice, and pruning state;
- checkpoint and current code hashes;
- energy, variance, discarded weight, sweeps, reached chi, and timing;
- for even states, full `C(r)`, `S(0)`, `S(k_min)`, `xi`, and `R_xi`.
- validation flags and the measurements that triggered each flag.

The collector requires consensus on shared settings and preserves every
planned cell as `success`, `failed`, `missing`, or `pending`.

## Compute boundary

The broad pass contains `7 * 2 * 15 = 210` even-sector cells. If every sigma
has one bracket, refinement contains 84 size-point cells, of which 28
endpoints already exist from the broad pass, leaving at most 56 new
even-sector cells. Targeted gaps add 28 odd-sector cells.

Before any DMRG cell runs, the planner must calculate wall-time and memory
estimates from the measured local `sigma=1.75` timing records, scaled to
`chi=64`. The estimate reports broad, refinement, and gap stages separately.
No large scan begins until the generated plan and estimate are reviewed.

## Later refinement and validation

Only after the exploration result is reviewed may a narrow sigma region be
rescanned with `K=24`, `chi=128`, and optionally `L=128` when the measured
trend justifies its cost. `K=32` and `chi=256` are reserved for a few
representative systematic checks. They are not production defaults and
cannot be selected based on agreement with a published crossover value.

The final interpretation keeps MPO, MPS, and finite-size/sigma-resolution
uncertainties separate. The validated local result indicates that the last
category is expected to dominate, but each uncertainty remains auditable.
