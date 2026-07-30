# Higher-dimensional fermions: direct complex-wave-function VMC and auditable scaling

Lei Wang's question on Quantum Harness PR #262 creates a useful distinction
between two computational objects: a signed or complex path-integral measure,
and a direct variational wave function.  Ranger uses the second object and
turns its practical high-dimensional complexity into a reproducible
multi-size measurement.

## Path-integral complexity baseline

For indistinguishable fermions in two or more spatial dimensions, exchange
generically contributes positive and negative path-integral sectors.  In a
magnetic field, the corresponding weights acquire complex phase.  Absolute-
weight reweighting introduces

\[
\langle s\rangle_{|w|}=\frac{Z_F}{Z_{|w|}}
\sim e^{-\beta V\Delta f},
\]

so the average-sign signal can decrease exponentially with inverse
temperature and volume.  The generic complexity result is due to
[Troyer and Wiese (2005)](https://doi.org/10.1103/PhysRevLett.94.170201).
Restricted-path and fixed-node methods encode a nodal constraint
([Ceperley, 1991](https://doi.org/10.1007/BF01030009)); fixed-phase methods
provide the complex-wave-function analogue
([Ortiz, Ceperley, and Martin, 1993](https://doi.org/10.1103/PhysRevLett.71.2777)).

These results define the baseline against which the Ranger computational
route should be understood.

## Ranger's direct-wave-function route

The implementation represents a complex, exchange-antisymmetric variational
state directly.  Fermionic exchange and magnetic phase are architectural
properties of `Psi_theta`.  The Markov chain samples

\[
p_\theta(R)=\frac{|\Psi_\theta(R)|^2}{Z_\theta}\ge 0,
\qquad
Z_\theta=\int dR\,|\Psi_\theta(R)|^2,
\]

and evaluates local estimators such as

\[
E_{\rm loc}(R)=\frac{H\Psi_\theta(R)}{\Psi_\theta(R)}.
\]

This is the direct fermionic neural-VMC setting exemplified by
[FermiNet](https://doi.org/10.1103/PhysRevResearch.2.033429).  The variational
estimator therefore operates without path-integral average-sign reweighting.
Its scientific scope is the direct complex wave function; generic
path-integral sign/phase complexity remains the complementary baseline.

## Measurable high-dimensional complexity

The direct sampler converts the relevant computational questions into
observable diagnostics:

- nodal and complex-phase expressivity;
- convergence from independent seeds;
- local-energy and bridge-weight variance;
- tangent-overlap integrated autocorrelation time;
- raw, bridge, and autocorrelation-adjusted effective sample sizes;
- block-resolved estimator uncertainty;
- completion, memory, and wall time per effective sample.

Neural sign structure can remain demanding even with a positive sampling
density ([Szabo and Castelnovo, 2020](https://doi.org/10.1103/PhysRevResearch.2.033075)).
Ranger therefore promotes every one of these quantities from performance
metadata to a versioned scientific result.

## New algorithms that extend the calculation

### Projector-free strict-LLL tangent

An `O(N^2)` holomorphic quadrupole acts directly on particle coordinates.
Overlap, Hamiltonian, quantum metric, Berry curvature, stiffness, and pole
frequency are estimated from coordinate samples.  At `N=8`, the method
reaches a sector associated with 319,770 Fock states while bypassing storage
of that dense many-body vector.

### Bounded common bridge

Ground and tangent states share

\[
q(R)\propto |\Psi_0(R)|^2+\alpha|\Psi_T(R)|^2.
\]

The same configuration stream supports both self-normalized estimators and
provides bridge ESS, balance, tangent IAT, adjusted ESS, and paired block
errors.  This makes overlap mismatch visible and quantitatively controlled.

### Failure-preserving multi-size protocol

The scaling campaign combines two independently verified chains at each of
`N=4,8` with 80 preregistered XH5 chains at `N=10,12`.  Every seed and scheduler
status is retained.  Each terminal record includes its source commit, Slurm
identity, sampling diagnostics, resource accounting, and a SHA-256 binding to
its readable configuration.

An `afterany` finalizer captures accounting, exports every terminal record,
validates identity uniqueness and schema compliance, and writes a hashed
manifest.  A deadline-snapshot tool preserves active scheduler states through
the same outcome-blind contract.

## Comparable-statistics decision

Local anchors and XH5 production records originate from distinct hardware.
The report keeps wall time and memory as descriptive provenance and bases the
tested-size classification on comparable statistics:

- completion fraction;
- adjusted ESS fraction;
- bridge ESS fraction;
- autocorrelation;
- local-energy variance.

When all report gates pass, the strongest finite-range language is:

> No exponential sampling collapse is resolved over the tested sizes.

This is a tested-range statement about the direct-wave-function estimator.
Asymptotic complexity and path-integral average-sign behavior remain separate
research questions with their own observables.

## Public evidence

- `results/fermion_scaling/summary.json`: machine-readable aggregation
- `results/fermion_scaling/chains.tsv`: human-readable per-chain table
- `results/fermion_scaling/records/`: individual records
- `results/fermion_scaling/configurations/`: readable hash-bound configs
- `schemas/fermion-scaling-chain-v1.schema.json`: record contract
- `hpc/xh5/`: array, exporter, snapshot, and finalizer workflow

Together these artifacts answer the higher-dimensional question with a
computational method, a measurable complexity definition, and an auditable
experimental protocol.
