# Shastry-Sutherland dimer calibration gate

Status: solver-independent implementation and finite-size benchmark, not a
bulk-gap SDP result.

## Question this gate answers

Challenge 88 Target 2 asks for the infinite-volume bulk gap of

```text
H_SS(g) = sum_dimer S_i dot S_j + g sum_square-NN S_i dot S_j
```

at `g=0` and `g=0.80`, with no state-symmetry restriction. Before assembling
the state-polynomial SDP, the code needs an independently checkable answer to
three lower-level questions:

1. Does the lattice contain the intended orthogonal-dimer covering rather than
   every diagonal or a duplicate set of dimers?
2. Does `S_i dot S_j` use the Pauli coefficient `1/4`?
3. Does the implementation reproduce the exact `g=0` product-singlet point?

This gate answers those questions. It does not certify `g=0.80`.

## Geometry convention

The square-lattice unit cell has period `(2,2)`. The two representative dimer
templates are

```text
anchor (0,0) mod (2,2): (x,y) -- (x-1,y+1)
anchor (0,1) mod (2,2): (x,y) -- (x+1,y+1)
```

Every site has exactly one diagonal partner and both diagonal orientations
occur. Horizontal and vertical square-nearest-neighbour bonds remain
one-site-translation invariant.

`GenericGapModel.PauliInteractionTemplate` now supports a periodic anchor
selector. Its default is period `(1,1)` with residue `(0,0)`, so the existing
Square `J1-J2` model and its instantiated terms are unchanged.

## Exact `g=0` oracle

For one occupied dimer singlet,

```text
<sigma_i^a> = 0
<sigma_i^a sigma_j^b> = -delta_ab
<S_i dot S_j> = -3/4
```

and distinct dimers factorize. Therefore

```text
ground-state energy per site = -3/8
local singlet-to-triplet gap  = 1
<P_s> = <1/4 I - S_i dot S_j> = 1.
```

`ShastrySutherlandOracle.jl` evaluates arbitrary canonical Pauli-word moments
in this product state using exact integers/rationals. This is stronger than
checking only the three headline constants: it can be used as a coefficient
oracle for assembled moment, stationarity, and gap matrices.

## Finite-torus cross-check

`scripts/shastry_sutherland_ed.py` independently builds the spin Hamiltonian
in fixed-total-`S^z` sectors and diagonalizes it with sparse Lanczos:

```bash
python3 scripts/shastry_sutherland_ed.py --g 0 --json
python3 scripts/shastry_sutherland_ed.py --g 0.8 --json
```

Committed evidence must be generated directly rather than transcribed:

```bash
python3 scripts/shastry_sutherland_ed.py --g 0 \
  --output evidence/shastry_sutherland_4x4_g0.json
python3 scripts/shastry_sutherland_ed.py --g 0.8 \
  --output evidence/shastry_sutherland_4x4_g0p8.json
```

The reported

```text
E_min(Sz=1) - E_min(Sz=0)
```

is a periodic finite-cluster diagnostic. It is not an upper or lower
certificate for the infinite-volume bulk gap. Its uses are limited to
Hamiltonian normalization, regression testing, and choosing an initial
threshold range for the SDP.

Local `4x4` results:

```text
g=0.0: E0/N = -0.3749999999999998, Sz=1 gap = 0.9999999999999956
g=0.8: E0/N = -0.4641107782903617, Sz=1 gap = 0.5339620879667581
```

The `g=0` values reproduce the exact answer within eigensolver tolerance. At
`g=0.8`, the ground-state and triplet residual norms are below `2e-14`. The
full outputs are retained in
`evidence/shastry_sutherland_4x4_g0.json` and
`evidence/shastry_sutherland_4x4_g0p8.json`.

## End-to-end `M/G/K` check

At patch level `L=1`, degree `d=2`, and `gamma=1`, the exact symbolic primal
assembly has:

```text
positive matrix M: 703 x 703
gap matrix K:        7 x 7
stationarity G:      3 canonical real equalities
assembly SHA-256:
49fc969420749383aef8d561f3d25b2318143071d016e826c6360cd15f9fb466
```

Evaluating every assembled entry in the exact dimer-product functional gives
all three stationarity equalities exactly zero, minimum eigenvalue
`-3.72e-15` for `M` (roundoff), and minimum eigenvalue `0` for `K`. Repeating
the assembly at the false threshold `gamma=1.1` gives a gap-matrix minimum
eigenvalue of exactly `-0.1` numerically. Thus the gate accepts the known
threshold and detects an overclaim.

## Next integration step

The `g=0` end-to-end correctness gate now passes. Freeze its geometry,
normalization, assembly hash, and sign convention as a regression oracle.

An attempted `55 x 55` degree-one scout relaxation was deliberately retired:
it remained feasible at `g=0, gamma=5` and `g=0.8, gamma=10`, so it cannot
resolve the desired scale. The negative result and no-repeat decision are in
`evidence/shastry_sutherland_degree1_scout_negative.md`.

The full existing basis has passed exact solver-free preflight at
`L=1, d=2, g=4/5, gamma=1/2`:

```text
Hamiltonian Pauli terms:       42
positive matrix M:        703 x 703
gap matrix K:               7 x 7
stationarity G:                  3
scalar moments:             74,602
problem SHA-256:
d2eacd968fbe4c0095287583a4dcd0b2c9c3d01e4501a4f51762988b0c718839
assembly SHA-256:
c7d1e375001422ed5ff823f47e9dc8c72f0e11c153f9c2e9e3e9eee56d7824f8
```

This is ready for an optimizer-free MOF build on a high-memory CPU node. No
GPU is needed. Based on its larger moment inventory than the already profiled
Square build, it should not be treated as a laptop/local-memory job.

Next, instantiate the same unrestricted state-polynomial relaxation at
`g=0.80`. Use the finite-torus value only to seed a coarse threshold scan
(for example values bracketing `0.53`); do not constrain the scan to that
finite-size number. Only a solver result with the correct status semantics and
an auditable certificate can be reported as a bulk-gap upper bound.
