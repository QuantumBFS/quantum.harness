# Issue 147: 4x4 Exact-Diagonalization Calibration Design

**Date:** 2026-07-28

**Status:** Approved for implementation planning

## Goal

Produce a symmetry-complete, full-spectrum thermodynamic reference for the
4x4 open-boundary transverse-field Ising model at `h/J = 3.0`. This reference
will calibrate and freeze the thermodynamic PEPO compression weights and
tolerances before any 10x10 PEPO/QMC validation run.

The calculation is an exact finite-cluster reference. Its only physics bias is
the 4x4 open cluster; symmetry projection and diagonalization must introduce no
approximation.

## Fixed physical setup

- Hamiltonian: `H = -J sum_<i,j> sigma_z(i) sigma_z(j) - h sum_i sigma_x(i)`.
- Coupling and operator convention: `J = 1`, Pauli matrices with eigenvalues
  `+1` and `-1`.
- Lattice: 4x4 square lattice with open boundary conditions.
- Local Hilbert space: one spin-1/2 per site, with no basis constraint.
- Initial field: `h = 3.0`. Fields `h = 2.5` and `h = 3.5` are deferred until
  the `h = 3.0` calibration is accepted.
- Thermal grid: `beta J = 0.025, 0.050, ..., 1.000`.
- Observables: `z = log(Z)/N`, internal energy per site `u`, and heat capacity
  per site `C`.

## Chosen route

Use explicit `D4 x Z2` orbit projectors and SciPy/LAPACK dense symmetric
eigenvalue solves. `D4` is the point group of the open square and `Z2` is the
global spin flip. The complete thermal trace includes the five `D4` irreducible
representations `A1`, `A2`, `B1`, `B2`, and `E`, at both spin-flip parities.

This custom route is preferred over QuSpin because it keeps representation
multiplicities, sector manifests, and failure checks explicit while fitting the
existing Python package. QuSpin is not installed and would still require custom
general-basis maps. FTLM or TPQ is rejected for this calibration because a
stochastic thermal trace is not an exact full-spectrum oracle.

## E-representation reduction

The `E` irrep is two-dimensional. Rather than diagonalize its full isotypic
subspace, first apply the `E` character projector and then resolve a fixed axis
reflection. Diagonalize only its `+1` reflection component and record
`spectral_multiplicity = 2`; a quarter-turn maps it to the omitted `-1`
component, on which the symmetry-invariant Hamiltonian has the same spectrum.
Assembly restores that second copy exactly.

The `+1` and `-1` reflection components must have identical spectra on local
test clusters. The implementation must not infer multiplicity from a filename
or irrep label during assembly; it reads the explicit manifest field and
verifies the recovered total state count. This reduction is expected to lower
the largest matrix dimension from about 16384 to about 8192, reducing matrix
memory by about four and dense eigensolver work by about eight.

## Components

### Symmetry basis

`qh147/symmetry_ed.py` owns:

- the eight `D4` site permutations;
- global spin-flip action;
- configuration orbits under `D4 x Z2`;
- orthonormal bases for all one-dimensional irreps;
- one reduced component and multiplicity metadata for `E`;
- sector dimension and completeness bookkeeping.

It does not own thermal observables, cluster submission, or result assembly.

### Hamiltonian and eigensolver

`qh147/ed.py` owns the sparse computational-basis TFIM Hamiltonian and the
projection `H_sector = Q.T @ H @ Q`. It checks the projected block before
calling the real symmetric LAPACK eigenvalue solver. Eigenvectors are not
requested because exact thermodynamics only needs eigenvalues.

### One-sector runner

`qh147/run_ed.py` runs one `(h, irrep, parity)` unit. It prints the sector
dimension, Hermiticity residual, matrix-memory estimate, and dense-work estimate
before diagonalization. A successful task atomically writes its spectrum and
manifest; an interrupted or failed task cannot leave a success manifest.

### Thermodynamic assembly

`qh147/ed_thermo.py` validates and merges all ten logical sectors for one field,
restores declared spectral multiplicities, and calls the existing
`thermal_from_spectrum` implementation. It refuses partial or inconsistent
inputs and writes no thermodynamic curve until the complete spectrum is valid.

## Per-sector result contract

Each result directory contains:

- `eigenvalues.npz`: sorted finite eigenvalues for the stored reduced block;
- `manifest.json`: status, field, irrep, spin-flip parity, matrix dimension,
  recovered sector dimension, spectral multiplicity, Hermiticity residual,
  wall time, peak memory, code commit, dependency versions, and spectrum hash.

Assembly requires:

- exactly one successful result for each of the ten logical sectors;
- identical lattice, boundary, `J`, field, and Pauli conventions;
- matching file hashes and finite, sorted spectra;
- a recovered state-count sum of exactly `2^16 = 65536`.

Missing, duplicate, corrupt, or convention-mismatched results are hard errors.

## Correctness tests

Only small tests run locally before the cluster calculation:

1. Every `D4` action is a valid site permutation and commutes with the 2x2 and
   3x3 open-boundary Hamiltonians.
2. Sector bases are orthonormal, distinct sectors are orthogonal, and recovered
   sector dimensions sum to `2^N`.
3. The two reduced `E` components have equal spectra and multiplicity recovery
   neither drops nor duplicates states.
4. The union of all recovered 2x2 and 3x3 sector spectra matches direct dense
   diagonalization eigenvalue by eigenvalue with absolute tolerance `1e-10`.
5. Thermodynamics from the sector union matches thermodynamics from the direct
   spectrum across the declared beta grid.
6. Tests require explicit failure for a missing or duplicate sector, a bad
   hash, a non-Hermitian projection, or inconsistent physical conventions.

The 4x4 result is not verified by a second expensive full-spectrum solve. Its
runtime acceptance checks are sector dimensions, Hermiticity, complete
manifests, hashes, and the recovered total state count.

## Compute placement and execution order

Native Windows runs only the small correctness tests. The 4x4 full spectrum
runs as a CPU-only job on a live-selected SCNet partition; no GPU is requested.

Before submission, select the account-specific SCNet profile, run the SSH
precheck, and probe live partitions. The partition is chosen only after that
probe. The initial resource envelope is 32 CPU cores, 128 GiB memory, and six
hours per sector task, subject to scheduler limits and live availability.

Execution order for `h = 3.0` is:

1. Rehearse all ten logical sectors and record dimensions, matrix memory, and
   dense-work estimates.
2. Run `A1,+` as a measured timing probe.
3. Predict each remaining wall time as
   `t_target = t_probe * (D_target / D_probe)^3`.
4. Stop for resource re-ratification if the largest reduced `E` block is
   predicted to exceed six hours.
5. Complete the remaining one-dimensional irreps, then the two reduced `E`
   sectors.
6. Assemble the complete spectrum and produce the `h = 3.0` thermal curve.

Every sector is independently resumable. Scheduler completion alone is not
success; a valid spectrum and success manifest are required.

## Calibration handoff

The accepted `h = 3.0` curves become the exact finite-cluster target for tuning
the thermodynamic PEPO compression loss. Weight and tolerance choices are
frozen only after their PEPO errors in `z`, `u`, and `C` are measured against
this reference. The later `h = 2.5` and `h = 3.5` ED runs test the frozen
choices; they are not used to retune them.

## Out of scope

- 10x10 PEPO evolution or boundary contraction;
- 10x10 QMC reference data;
- fields other than `h = 3.0` during the initial calibration;
- eigenvectors, correlation functions, or level statistics;
- GPU eigensolvers or distributed dense diagonalization;
- changing the existing PEPO compression implementation before the exact
  reference is available.
