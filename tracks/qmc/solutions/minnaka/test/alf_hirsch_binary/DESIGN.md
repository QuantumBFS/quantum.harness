# ALF Binary Hirsch Projector-QMC Test Design

## Goal

Create a pinned local ALF 2.4 checkout that can select the exact two-valued
Hirsch spin Hubbard--Stratonovich (HS) transformation at run time, then
reproduce the documented 4x4 half-filled Hubbard projector-QMC energy using
six independent single-threaded MPI ranks.

The numerical target is the ALF reference result

`E = -13.618 +/- 0.002`

for the unshifted Hubbard energy convention.

## Fixed physical setup

The simulated Hamiltonian is

`H = -t sum_<ij>,sigma (c^dagger_i,sigma c_j,sigma + h.c.)
     + U sum_i n_i,up n_i,down`,

with:

- a 4x4 square lattice;
- periodic boundary conditions in both directions;
- `t = 1`;
- `U = 4`;
- `N_up = N_down = 8`;
- real arithmetic and the spin HS channel;
- projector mode with `Theta = 10`;
- symmetric Trotter decomposition with `Dtau = 0.05`;
- central measurement window `Beta = 1`;
- `Ltau = 0`;
- no adiabatic switching.

The left and right projector boundary states remain ALF's stock real
non-interacting determinants. ALF opens the 4x4 free-electron shell by applying
a real `Delta = 0.01` dimerization only while constructing these boundary
determinants. The propagated Hamiltonian itself remains the uniform periodic
Hubbard Hamiltonian.

## Upstream source and isolation

Use the official `ALF-QMC/ALF` repository, branch `ALF-2.4`, pinned to commit

`ff5600df97877ef1d080432d0068e157ff520ecd`.

All new material lives under:

`test/alf_hirsch_binary/`

The directory contains:

- `ALF/`: pinned nested upstream checkout, ignored by the outer repository;
- `patches/`: a reproducible patch against the pinned commit;
- `tests/`: analytical and real-executable regression tests;
- `run/`: prepared inputs and raw MPI output;
- `results/`: analyzed energy, diagnostics, provenance, and timing;
- `README.md`: exact build, test, and run commands.

The ALF checkout uses its own branch `codex/hirsch-binary`. The outer
QuanHarness working tree's unrelated modified and untracked files must not be
staged, edited, or cleaned.

## Selected implementation

Modify `Hamiltonian_Hubbard_Plain_Vanilla_smod.F90` by adding the input
parameter:

`Hirsch_binary = .false.`

The default `.false.` path must retain the original four-valued operator
construction and sampling behavior. With
`Hirsch_binary = .true.`, the interaction uses the exact identity

`exp[(Dtau*U/2) (n_up - n_down)^2]
 = (1/2) sum_(s=+/-1) exp[s*lambda (n_up - n_down)]`,

where

`lambda = acosh(exp(Dtau*U/2))`.

The ALF operators are configured as:

- field type `1`, so the auxiliary field is exactly `s = +/-1`;
- up-spin coupling `g_up = +lambda`;
- down-spin coupling `g_down = -lambda`;
- the existing `alpha = -1/2`, which cancels between the two spin flavors.

This feature is intentionally restricted to repulsive `U > 0`.  The pinned
ALF 2.4 Plain Vanilla module has no adiabatic-switching parameter or code
path, so binary mode is nonadiabatic by construction. Selecting binary
Hirsch fields with unsupported interaction parameters must terminate before
sampling with a precise error message.

The generated `info` file must record:

- `HS transformation: binary Hirsch spin`;
- the numerical value of `lambda`;
- the existing lattice, projector, particle-number, and Trotter parameters.

Keeping the original four-valued path available through the same executable
provides a direct installation and regression control without maintaining a
duplicated Hamiltonian module.

## Test strategy

Implementation follows red-green-refactor.

1. Before modifying ALF, a real-input smoke test sets
   `Hirsch_binary = .true.` and must fail because the pinned upstream program
   does not recognize the parameter.
2. An analytical regression test evaluates all four local occupation states
   `(n_up,n_down) = (0,0), (1,0), (0,1), (1,1)` and verifies the binary sum
   against the interaction propagator to near machine precision.
3. After implementation, the same real-input smoke test must run the compiled
   MPI executable and verify from `info` that:
   - binary Hirsch mode was selected;
   - the reported `lambda` satisfies
     `cosh(lambda) = exp(Dtau*U/2)`;
   - the lattice, filling, `Theta`, `Dtau`, and `Beta` are the approved values.
4. A short six-rank run checks finite observables, average sign near one,
   acceptance statistics, and Green-function precision before the production
   workload.
5. The original four-valued mode receives a short regression smoke so the new
   branch is shown not to remove the stock path.

No final success claim may rely only on source inspection; it requires a fresh
compiled executable and completed runtime tests.

## Build and parallel execution

Load Intel oneAPI using:

`source /opt/intel/oneapi/setvars.sh`

Build ALF with Intel MPI and MKL. Production execution uses six concurrent
single-rank MPI jobs on six physical cores with:

- `OMP_NUM_THREADS = 1`;
- `MKL_NUM_THREADS = 1`;
- one independent ALF random walker per job;
- six distinct seeds taken from ALF's standard seed file.

Hyperthreads are not used.

ALF reduces observables across all ranks within one MPI communicator before
writing a bin.  A grouped `mpirun -np 6` run with `NBin=7` therefore writes
seven averaged rows rather than 42 inspectable chain-level rows.  Production
uses six independent run directories so that all chain bins remain
available. The workload is:

- six independent one-rank MPI jobs;
- `NBin = 7` per job;
- `NSweep = 2000` per bin;
- 42 aggregate bins and 84,000 aggregate sweeps.

With `Beta = 1`, the number of imaginary-time slices is

`Ltrot = Beta/Dtau + 2*Theta/Dtau = 420`.

Each sweep visits the 16x420 space-time field lattice in both imaginary-time
directions. A short timing run is completed first and its measured rate is
used to estimate the production wall time. If the estimate unexpectedly
exceeds ten minutes locally, the result is reported before enlarging the
local run; the approved six-rank production parameters are not silently
changed.

## Analysis and acceptance criteria

The final analysis combines the 42 MPI bins and reports:

- total, kinetic, and interaction energies with statistical errors;
- mean sign;
- field-update acceptance;
- Green-function and phase precision diagnostics;
- equilibration bins omitted by the analysis;
- wall time and aggregate field-update rate;
- ALF commit, local patch hash, compiler/MPI versions, and run parameters.

The primary numerical acceptance criteria are:

- `sigma_E <= 0.004`; and
- `abs(E - (-13.618)) <= 2*sqrt(sigma_E^2 + 0.002^2)`.

The result is also compared with the exact finite-size value near
`-13.6224`. A difference at the few-millihartree level is interpreted in the
context of the finite `Dtau = 0.05`; no zero-time-step extrapolation is part
of this test.

A run is not accepted if any of the following occurs:

- average sign materially below one at half filling;
- non-finite observables;
- poor Green-function precision relative to the statistical error;
- fewer than 42 completed aggregate bins;
- an input or `info` file inconsistent with the approved setup;
- a failed analytical, build, or executable regression test.

## Deliverables

On completion, `test/alf_hirsch_binary/results/` contains:

- `summary.json`: machine-readable parameters, energy, diagnostics, and time;
- `summary.md`: concise human-readable result;
- `energy_bins.csv`: the aggregate bin-level energy data;
- `run.log`: production standard output and timing;
- `provenance.txt`: exact source, compiler, MPI, and patch identifiers.

The `README.md` provides one command each for rebuilding, testing, running the
six-rank production job, and repeating the analysis.
