# Learning-Induced Metal-Insulator Transition

This standalone Challenge #122 module tests an open question: whether changing
the physical measurement axis drives a transition between localized and
extended Majorana states in the Born tensor network of a monitored surface
code. The result is deliberately labeled exploratory.

## Model and symmetry classes

The measured qubit axis is

\[
\sigma^{\theta,\phi}
=\sin\theta\cos\phi\,X+\sin\theta\sin\phi\,Y+\cos\theta\,Z.
\]

The effective real monitoring strength is
\(J=\operatorname{atanh}(\cos\theta)\), while the dual complex coupling obeys
\(\exp[-(J_d+i\phi_d)]=\tanh[(J+i\phi)/2]\). Each circuit row is implemented
as conditional Gaussian measurements followed by real-orthogonal Majorana
rotations.

The validation stage uses the special XY line, \(\theta=\pi/2\), whose
single-particle evolution decomposes into class-D blocks. The open stage uses
\(\theta=0.45\pi\); nonzero \(\phi\) removes that decomposition and realizes
the generic DIII cut. The two scans must not be interpreted as the same
symmetry class.

## Computation

All physics evolution runs in Rust:

- `rand_xoshiro::Xoshiro256PlusPlus` supplies deterministic,
  coordinate-separated random streams;
- a real antisymmetric \(2L\times2L\) covariance matrix represents each pure
  Gaussian trajectory;
- measurement updates use the exact rational covariance formula;
- an orthogonal polar projection after each circuit period removes accumulated
  roundoff from \(\Gamma^2=-I\) without changing the Born sampling rule;
- orthogonal rotations act as \(\Gamma\mapsto R\Gamma R^T\);
- conditional binary entropy provides the Rao-Blackwellized record
  free-energy estimator;
- complex QR stabilization produces temporal Lyapunov spectra.

Python does not perform Monte Carlo evolution. It validates frozen hashes,
fits entanglement models, performs hierarchical stream/block bootstrap,
creates plots, and renders bilingual HTML/PDF reports.

## Observables and claims

Entanglement arcs are compared using constant, logarithmic,
squared-logarithmic, mixed, and Page-augmented models. The Casimir fit is

\[
\gamma_1(L)=f_\infty L-\frac{\pi(c_{\rm eff}\alpha)}{6L}+\frac{a}{L^3}.
\]

The directly measured candidate is \(c_{\rm eff}\alpha\). Spatial parity
correlations give a scaling dimension \(\Delta\); the leading temporal
Lyapunov gap \(g\) gives \(\alpha=gL/(2\pi\Delta)\). A standalone
\(c_{\rm eff}\) is published only when alpha estimates remain positive and
stable across declared windows. The entanglement coefficient called `c` is a
diagnostic and is never substituted for the Casimir central charge.

Possible machine-readable states are:

- `xy_reproduced_diii_candidate`
- `xy_reproduced_diii_inconclusive`
- `validation_failed`

IID-sign trajectories are always marked nonphysical and never enter a
physical estimator.

## Runtime and resume policy

Production targets 60 minutes. New ordinary tasks stop at 55 minutes. Up to
30 minutes of scientific reserve is allowed only for a declared reason; no
new work begins at 85 minutes, leaving five minutes for atomic finalization.
Each completed stream is written with `flush`, `sync_all`, atomic rename, and
SHA-256 registration. Resume validates the schema, exact stage subsection,
seed, mode, block continuity, and hash before reuse. Partial blocks are never
added to `raw/blocks.csv`.

The approved coarse scans are:

- XY: `theta_pi=0.5`,
  `phi_pi=[0.18,0.21,0.24,0.25,0.27,0.30]`;
- DIII: `theta_pi=0.45`,
  `phi_pi=[0.06,0.10,0.14,0.18,0.22,0.26,0.30,0.34]`;
- coarse widths `L=[8,12,16,24]`, four streams, burn-in `12L`, measurement
  depth `40L`, and block depth `5L`.

Python writes and hashes `processed/refinement_request.json`; Rust refuses an
unregistered or changed request.

## Commands

```bash
make setup
make test
make run-test
make run-pilot
make run-production
```

`run.sh` stops immediately if an oracle, simulation, analysis, or report
verification step fails. A successful result contains `manifest.json`,
stream JSON files, `raw/blocks.csv`, `summary.json`, ten plots per language,
and coexisting English/Chinese HTML and PDF reports.

## Output inventory

`manifest.json` is the audit ledger. It records the validated configuration,
deterministic seeds, task states, runtime decisions, reserve reasons, and
SHA-256 for every stable artifact. `summary.json` contains only frozen
analysis facts. Both language reports embed the same summary hash and numeric
fact model.
