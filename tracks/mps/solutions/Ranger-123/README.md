# Floquet-IF Many-body: N=2,3

## Submission

- Team: Ranger
- Members: Chenxi Wan, Yedi Shen, Junkai Wang
- Challenge: #123
- Track: MPS
- Completed scope: reproducible collective common-bath calculations for
  \(N=2,3\), plus a quantitative non-Markovian–Floquet-Markov benchmark.

This repository is a reproducible implementation of the two- and three-spin
part of [QuantumBFS/quantum.harness issue #123](https://github.com/QuantumBFS/quantum.harness/issues/123).
It combines exact symmetry reduction, a public uniform influence-functional
solver, frequency-resolved bath heat currents, and a Floquet-Markov benchmark.

The production backend is
[UniformTEMPO.jl](https://github.com/uniformTEMPO/UniformTEMPO.jl), pinned to
revision `b76a018c32e5415989761d902b1b0e95f1a337da`. The Python layer projects
the physical model into its symmetry sectors, runs Julia, caches the uniform
process tensor atomically, inserts operators into the extended process-tensor
state, separates coherent delta peaks from the decaying correlation, and
records every convergence comparison in JSON.

## Completed results

- Exact \(N=2\) singlet/triplet reduction, dark singlet, bright gaps, and
  transition weights.
- Exact \(N=3\) reflection \(6\oplus2\) reduction and the
  \(J\)-independent embedded single-spin odd sector.
- A converged six-point \(N=3\) heat-spectrum grid for
  \(J/\Omega=0.25,0.5,1\) in both reflection sectors.
- A converged \(3\times3\) \(N=2\) calibration grid comparing uniform TEMPO
  with Floquet-Markov/QRT using state, correlation, and heat-spectrum errors.
- Floquet matrix-element, collective-variance, counterterm, and normalization
  diagnostics.
- Full convergence of the two bounded-normalization model variants.
- Compression convergence of both Kac-normalized variants, with their
  remaining timestep/phase refinement explicitly marked as cluster work.
- An independent single-spin smoke test and a coarse UniformTEMPO–OQuPy
  cross-check.
- A pole-resolved, fixed-frequency \(N=1,2,3\) heat-valve pre-scan and
  three-point \(N=3\) UniformTEMPO go/no-go pilot. The pilot rejects—not
  confirms—the dark-channel hypothesis: the quasienergy gap collapses while
  the observable transfer-pole residue increases.

The main \(N=2\) and \(N=3\) results do **not** require a cluster. The failed
heat-valve pilot does not justify a cluster-scale nine-point continuation.
Only the optional full Kac refinement does. The project makes no \(N=4\),
thermodynamic-limit, continuum, or critical-exponent claim.

## Reproduce

Python 3.12 and Julia 1.12 are the recorded production versions.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[dev,nonmarkov]'
julia --project=julia -e 'using Pkg; Pkg.instantiate()'

# Exact and legacy validation baselines
PYTHON_BIN=.venv/bin/python scripts/run_baselines.sh
PYTHON_BIN=.venv/bin/python scripts/run_pt_baselines.sh

# Resumable production calculation and strict audit
PYTHON_BIN=.venv/bin/python scripts/run_paper_extension.sh all

# Independent backend checks
.venv/bin/python scripts/run_uniform_validation.py

# Software and result verification
.venv/bin/python -m pytest -q
.venv/bin/ruff check src tests scripts/run_uniform_validation.py
.venv/bin/mypy src
.venv/bin/python -m floquet_if_manybody.cli audit results
.venv/bin/python -m floquet_if_manybody.cli paper-audit results/paper

# Pole-resolved heat-valve pilot. The audit intentionally exits nonzero
# because the dark-channel claim gates are not met.
.venv/bin/python -m floquet_if_manybody.cli heat-valve --pilot
.venv/bin/python -m floquet_if_manybody.cli \
  heat-valve-audit results/heat-valve
```

The production command is resumable. Its cache is content-addressed by the
physical model, numerical controls, projected operators, solver revision, and
source revision. Cache files are excluded from the research archive.

The upstream harness excludes machine-generated `results/` data from Git.
The commands above reproduce those local files. This submission commits the
publication figures, reports, test suite, and compact validation snapshots;
`validation/ARTIFACT_PROVENANCE.json` records hashes for the audited local
artifact set.

To continue the Kac variants on a cluster:

```bash
FULL_KAC=1 PYTHON_BIN=.venv/bin/python \
  scripts/run_paper_extension.sh models
```

## Result guide

| Artifact | Meaning | Status |
|---|---|---|
| `figures/n2_exact.*` | Interacting-triplet gaps and bright weights | Exact |
| `figures/n3_exact.*` | Collective cat gap and weight | Exact |
| `figures/paper/n3_sector_heat.*` | \(N=3\) even/odd heat spectra | 6/6 converged |
| `figures/paper/n3_odd_difference.*` | Odd-sector \(J\)-invariance residual | Exact zero on the projected grid |
| `figures/paper/error_maps.*` | Uniform TEMPO vs Floquet-Markov/QRT | 9/9 converged |
| `figures/paper/dark_diagnostics.*` | Floquet matrix elements, heat, and \(\mathrm{Var}(S)\) | Converged heat plus exact Floquet diagnostic |
| `figures/paper/model_variants.*` | Bounded/Kac and counterterm comparison | Bounded converged; Kac compression-audited |
| `figures/heat-valve/heat_valve_hero.*` | Quasienergy collapse tested against exact transfer-pole residues | Pilot complete; dark-channel claim rejected |
| `docs/heat-valve-result-zh.md` | Fixed-frequency go/no-go evidence and independent claim audit | 3/3 \(N=3\) pilot points; full grid intentionally not run |
| `validation/*.json` | Artifact provenance and independent backend checks | Diagnostic validation |

See [the Chinese report](docs/report-zh.md),
[the heat-valve pilot result](docs/heat-valve-result-zh.md),
[theory conventions](docs/theory.md), [numerical methods](docs/methods.md), and
the [completion matrix](docs/completion-matrix.md).

This integrated project is distributed under the repository's
AGPL-3.0-or-later license. Third-party solvers retain their own licenses.
