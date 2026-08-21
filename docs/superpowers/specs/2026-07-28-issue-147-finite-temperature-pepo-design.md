# Issue 147 Finite-Temperature PEPO Design

## Goal

Build a reproducible finite-temperature PEPO solver for challenge issue 147.
The solver will compute the free-energy density, internal-energy density, and
specific heat of the 10 by 10 transverse-field Ising model near its quantum
critical field, quantify all numerical errors, and validate the results against
same-lattice QMC data.

The first delivery target is a credible hackathon MVP. Susceptibility and a
tanTRG or LTRG comparison are explicitly deferred.

## Fixed physical setup

Use Pauli matrices, not spin operators, with

```text
H = - sum_<i,j> sigma_z(i) sigma_z(j) - h sum_i sigma_x(i).
```

The fixed choices are:

- J = 1;
- 10 by 10 square lattice with open boundaries and N = 100;
- h/J in {2.5, 3.0, 3.5};
- beta J from 0.1 through 1.0;
- default internal delta_beta = 0.025, with published checkpoints at every
  multiple of 0.1;
- required observables f(beta), u(beta), and C(beta); and
- global Z2 spin-flip symmetry preserved by the construction and monitored,
  without requiring block-sparse tensors in the MVP.

The h/J = 3.0 branch is the first production path. Once it completes, the same
code and configuration expand to h/J = 2.5 and 3.5.

## Chosen method and software boundary

Use a finite PEPO built by second-order Trotter imaginary-time evolution and
compressed variationally after every gate layer. The implementation owns the
thermal PEPO convention, gate application, compression objective,
normalization bookkeeping, and thermodynamic estimators.

Use Python with:

- quimb for finite two-dimensional tensor-network primitives, local gate
  application, boundary-MPS contraction, and optimizer integration;
- cotengra for contraction-path planning and cost rehearsal; and
- JAX for automatic differentiation and optional A800 execution.

PEPSKit.jl is not the primary stack because its strongest path targets infinite
periodic PEPS and CTMRG, while this challenge fixes a finite open 10 by 10
lattice. It remains an optional later contraction cross-check.

The repository already exposes quimb and JAX as installable tools. Installation
belongs to the implementation plan, after this design is approved.

## Thermal PEPO representation

Represent the unnormalized thermal operator

```text
R(beta) = exp(-beta H)
```

rather than the normalized density matrix. Each bulk tensor has two physical
operator legs and four spatial virtual legs. Boundary tensors omit the virtual
legs that would cross the open edge.

At beta = 0, R is the product identity and has bond dimension D = 1. A step has
the data flow

```text
R_D(beta)
  -> apply one palindromic second-order Trotter step
  -> provisional higher-bond PEPO R_tilde(beta + delta_beta)
  -> local-SVD initial compression
  -> environment-aware variational compression
  -> R_D(beta + delta_beta).
```

The gate schedule separates horizontal-even, horizontal-odd, vertical-even,
vertical-odd, and transverse-field terms into commuting layers. The full step
is palindromic to retain second-order Trotter accuracy.

The variational target minimizes the normalized Frobenius error

```text
||R_tilde - R_D||_F^2 / ||R_tilde||_F^2
```

using a boundary-MPS approximation to the complete environment. Local SVD
provides a stable starting point but is not the final compression rule.

After every accepted step, rescale the PEPO to a safe numerical range and add
the removed scale to a logarithmic normalization ledger. The ledger is part of
every checkpoint and is required to reconstruct log Z.

## Components

The implementation is divided by responsibility:

| Component | Responsibility |
| --- | --- |
| `model` | Open-boundary TFIM terms, Pauli convention, and local gates |
| `pepo` | Finite PEPO leg convention, dimensions, and boundary tensors |
| `evolve` | Trotter schedule and sequential beta evolution |
| `compress` | Local-SVD seed, environment loss, and variational optimizer |
| `contract` | Boundary-MPS contraction, chi convergence, and path rehearsal |
| `thermo` | log Z, f, u, C, numerical differentiation, and error propagation |
| `checkpoint` | Atomic save, resume, progress, and invalid-point state |
| `reference` | Small-system ED and 10 by 10 QMC reference interfaces |

These boundaries keep the thermal algorithm independent of the contraction
backend and keep reference generation independent of PEPO code.

## Thermodynamic estimators

Tracing every local input/output physical pair turns the PEPO into a scalar 2D
network. Contract it to obtain

```text
Z = Tr R(beta)
f = -log(Z) / (beta N).
```

Local Hamiltonian insertions, with reusable row and column environments, give

```text
u = Tr[H R(beta)] / (N Z).
```

For 10 by 10 production data, evaluate the specific heat from a dense and
uniform internal-energy curve:

```text
C(beta) = -beta^2 d u / d beta.
```

Use a cubic five-point local polynomial as the production differentiation
default, with one-sided fits at the endpoints. Compare it with quadratic
five-point and cubic seven-point fits and include their spread in the reported
C uncertainty. This avoids the quadratic number of explicit H^2 term pairs on
100 sites.

For 2 by 2, 3 by 3, and the symmetry-resolved 4 by 4 reference calculation,
also evaluate

```text
C = beta^2 (expect(H^2) - expect(H)^2) / N.
```

Agreement between the derivative and fluctuation forms is a required small-
system validation before production C data are accepted.

## Error budget and validation

Separate rather than combine the numerical errors:

1. Trotter error: compare delta_beta = 0.05 and 0.025 at representative
   parameter points. Retry at 0.0125 if the change is not below 0.1 percent for
   u and 0.5 percent for C.
2. Contraction error: increase boundary-MPS dimension chi at fixed D until
   successive values change u by less than 0.1 percent and log Z / N by less
   than 1e-4.
3. PEPO truncation error: run D in {4, 6, 8} and show convergence at least at
   beta J = 0.1 and 0.5.
4. Differentiation error: vary local polynomial order and window; compare with
   the fluctuation estimator on small systems.
5. Reference error: retain QMC statistical errors and require them to be small
   enough to resolve the PEPO-QMC discrepancy.

Validation has three levels:

- 2 by 2 and 3 by 3 complete diagonalization for fast exact tests;
- 4 by 4 full finite-temperature spectrum on SCNet, decomposed by global Z2
  and square-lattice point-group symmetry; and
- sign-problem-free QMC on the same 10 by 10 open lattice for production truth.

QMC free energy is reconstructed from its internal-energy curve using the
exact beta = 0 anchor:

```text
log Z(beta) = N log 2 - N integral_0^beta u(beta') d beta'.
```

The engineering MVP passes when every required field has complete curves, D
convergence, QMC errors, a reported lowest stable temperature, resource data,
and a one-command smoke test. The research performance target at beta J = 0.8
is relative error below 1 percent for u and below 3 percent for C. Missing that
performance target does not invalidate an honest challenge result, but the
error and stability limit must be reported without interpreting an unconverged
curve as physics.

## Local and cluster execution

Native Windows runs only fast exact tests, analysis, and plotting, each below
10 minutes. SCNet owns the 4 by 4 full-spectrum calculation, 10 by 10 PEPO,
QMC references, and convergence scans.

One (h, D, delta_beta) tuple forms one sequential beta chain so every point can
warm-start from the previous checkpoint. Different h and D branches are
independent Slurm jobs. Once a PEPO checkpoint exists, measurement jobs at
different chi values can run independently without repeating evolution. QMC
reference points are also independently parallelizable.

Before the first nontrivial contraction, use cotengra rehearsal to estimate the
largest intermediate tensor, FLOPs, and memory. Select CPU or A800 resources
from those estimates and the active SCNet profile; do not discover feasibility
by running an oversized production job.

Each accepted beta point atomically saves:

- the PEPO and logarithmic normalization ledger;
- compression and contraction residuals;
- thermodynamic estimates;
- wall time and peak memory; and
- enough optimizer state to resume from that point.

Long jobs emit approximately 10 to 50 progress records and are monitored until
the first valid beta point is produced.

## Failure handling

Stop the current branch rather than silently continue when any of the following
occurs:

- NaN, infinity, or non-positive Z;
- a compression residual that repeatedly rises;
- boundary-MPS failure to converge at the configured chi;
- a normalized Hermiticity residual
  `||R - R^dagger||_F / ||R||_F` above 1e-6; or
- an internal-energy increment more than five times the preceding nonzero
  increment, which triggers a finer-step retry before the point can be
  accepted.

Retry from the last accepted checkpoint, first with a larger optimization
budget and then with delta_beta halved. If the retry policy fails, mark the
point invalid and report the previous point as the method's lowest stable
temperature.

## Tests and reproducibility

Fast tests cover tensor-leg conventions, gate decomposition, exact 2 by 2 and
3 by 3 thermodynamics, normalization-ledger reconstruction, checkpoint resume,
and CPU/GPU agreement on a tiny instance. The 4 by 4 ED and 10 by 10 QMC checks
are cluster validations rather than fast tests.

After environment setup, this one command must run the smoke test and generate
a small example result:

```text
python -m qh147.smoke
```

Every production result records the full physical and numerical configuration,
random seeds, dependency versions, Git commit, raw curves and error estimates,
convergence data, wall time, peak memory, and the associated checkpoints.

Implementation will live inside the solution directory of the team registered
for issue 147. Registration metadata and the team directory name are outside
this scientific design. Source, configurations, tests, documentation, and
small reference data are committed. Large checkpoints, logs, and production
data remain under the track results area and are gitignored.

## Deferred scope

The MVP does not include block-sparse Z2 tensors, uniform susceptibility,
tanTRG or LTRG comparison, PEPSKit cross-validation, observable-targeted
compression, or a METTS implementation. Each can be added after the required
PEPO and QMC pipeline passes.
