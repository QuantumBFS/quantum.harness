# FloIM: non-Markovian many-body Floquet heat transport

> **Status: ✅ Complete — final challenge submission** (2026-07-30). Comprehensive report: `docs/2026-07-30-comprehensive-report.html`.

## Team

| | |
|---|---|
| **Team name** | FloIM |
| **Members** | 李泓翰；孙志杰；马卓成；郝笑阳 |
| **Challenge** | [#123: Many-body dissipative Floquet system beyond the Markovian model](https://github.com/QuantumBFS/quantum.harness/issues/123) |
| **Track** | `mps` |

## Scientific goal

Mickiewicz, Link, and Strunz introduced a Floquet influence-functional
(Floquet-IF) construction for periodically driven, strongly damped open
quantum systems. Their single-spin example resolves the asymptotic heat-current
density into a continuous part and discrete harmonic weights. FloIM first
builds a strict, auditable single-spin baseline and then explores how
interactions redistribute this spectral weight in a driven Ising chain.

The many-body prototype currently studies a **boundary-coupled chain**,

$$
H_{\mathrm{sys}}(t)
=J\sum_{i=1}^{N-1}\sigma_z^{(i)}\sigma_z^{(i+1)}
+\sum_{i=1}^{N}
\left[(h_z+A\cos(\omega_d t))\sigma_z^{(i)}
+h_x\sigma_x^{(i)}\right],
$$

with bath coupling \(S=\sigma_z^{(1)}\). This is not yet the collective
common-bath model \(S=\sum_i\sigma_z^{(i)}\) proposed in the challenge. Results
must therefore be described as boundary-bath many-body evidence, not as a
solution of the collective-coupling problem.

## Two implementation layers

### Strict single-spin reference

[`../reproduction/floquet_spin_boson/`](../reproduction/floquet_spin_boson/)
contains the reviewer-facing reference implementation:

- versioned UniformTEMPO influence-functional caches;
- matrix-free augmented Floquet operators and physical steady-state checks;
- ordered two-time correlations in the Floquet steady state;
- separate continuous heat-current spectra and integrated delta-peak weights;
- fail-closed convergence gates, resumable checkpoints, tests, and plots.

This layer uses compression tolerance `1e-10`. At the current pinned
UniformTEMPO revision the strict runs reach bond dimension `χ=279`; the paper
reports `χ=235`, so the local result is a validation against author data rather
than a claim of bitwise reproduction of the authors' environment.

### Many-body research prototype

This directory contains the spatial augmented-MPS extension:

- `src/augmented_tempo.jl`: boundary memory tensor plus spatial Liouville MPS;
- `src/redfield_ising.jl`: many-body Redfield-Magnus comparison model;
- `test/`: small-system wiring checks, Trotter/rank diagnostics, correlation
  prototypes, and heat-current research runs;
- `plot/`: plotting entry points for the exploratory Fig. 3 and `N=4` spectra;
- `augmented_tempo_notes.md`: implementation audit, measured diagnostics, and
  unresolved numerical work.

The bath memory bond `χ_b` is attached only to site 1, while spatial
entanglement is truncated by an independent MPS bond `χ_s`. The old M4a/M4b
research scripts use compression tolerance `1e-7` and finite correlation
windows; they are exploratory evidence and do not supersede the strict
single-spin checkpoints.

## Current evidence

| Challenge stage | Current status | Auditable evidence |
|---|---|---|
| Single-spin transient, paper Fig. 2 | Complete strict two-panel validation | [`20260730-fig2`](../reproduction/floquet_spin_boson/validation/20260730-fig2/) |
| Single-spin heat spectrum, paper Fig. 3 | 2 of 6 frequencies pass the strict gates | [`longitudinal ωd=5`](../reproduction/floquet_spin_boson/validation/20260729-fig3-longitudinal-wd5/), [`transversal ωd=1`](../reproduction/floquet_spin_boson/validation/20260730-fig3-transversal-wd1/) |
| Six-point Fig. 3 research prototype | Implemented at `1e-7`; strict replacement is incomplete | `test/m4a_fig3_reproduction.jl` and `augmented_tempo_notes.md` |
| Boundary-coupled `N=4` spectrum | One exploratory point implemented; compact tracked checkpoint pending | `test/m4b_heat_current_n4.jl` and `augmented_tempo_notes.md` |
| Redfield-Magnus benchmark | Solver and small-system checks implemented; heat-spectrum error map pending | `src/redfield_ising.jl`, `test/m3_redfield_check.jl` |
| Collective common-bath chain | Not implemented | Open research scope |

The strict Fig. 2 transient curves agree with the author curves to below
`2.8e-4` maximum absolute error. For the two strict Fig. 3 points, all physical
eigenvalue, residual, positivity, \(C(0)\), and correlation-tail gates pass; reference
maximum errors are `1.38e-4` (longitudinal `ωd=5`) and `1.44e-4`
(transversal `ωd=1`). The remaining Fig. 3 points and a strict Fig. 5 scan must
not be described as reproduced until their convergence evidence is recorded.

## Reproduce the verified checks

From the repository root:

```bash
STRICT=tracks/mps/solutions/reproduction/floquet_spin_boson
FLOIM=tracks/mps/solutions/FloIM

# Full strict single-spin test suite
OPENBLAS_NUM_THREADS=1 JULIA_NUM_THREADS=1 \
  julia --project="$STRICT/envs/current" "$STRICT/test/runtests.jl"

# Deterministic plotting tests
python -m pytest -q scripts/tests/test_floquet_plot_results.py

# Instantiate the many-body prototype and run its small merged-bond check
julia --project="$FLOIM/env_floquet" -e 'import Pkg; Pkg.instantiate()'
OPENBLAS_NUM_THREADS=1 JULIA_NUM_THREADS=1 \
  julia --project="$FLOIM/env_floquet" "$FLOIM/test/test_merged_bonds.jl"
```

Production-like numerical runs require the extracted author data from
[Zenodo record 19593671](https://zenodo.org/records/19593671). Raw author data,
large correlations, steady states, influence-functional caches, and generated
result directories remain gitignored.

## Remaining work

1. Finish the other four strict Fig. 3 frequencies and the strict Fig. 5 scan.
2. Record convergence in time step, IF compression/rank, eigensolver tolerance,
   correlation window, frequency grid, integration bandwidth, and harmonic
   cutoff.
3. Add a compact, machine-readable checkpoint for the boundary-coupled `N=4`
   spectrum, including energy balance and spatial-rank diagnostics.
4. Compare Floquet-IF and Redfield heat-current spectra for identical
   many-body parameters.
5. Implement or explicitly scope out the collective coupling
   \(S=\sum_i\sigma_z^{(i)}\).

## References

- K. Mickiewicz, V. Link, and W. T. Strunz, “Exact Floquet Dynamics of
  Strongly Damped Driven Quantum Systems,” *Phys. Rev. Lett.* **136**, 200201
  (2026), [DOI 10.1103/5z1m-122d](https://doi.org/10.1103/5z1m-122d),
  [arXiv:2511.08754v3](https://arxiv.org/abs/2511.08754v3).
- V. Link, H.-H. Tu, and W. T. Strunz, “Open Quantum System Dynamics from
  Infinite Tensor Network Contraction,” *Phys. Rev. Lett.* **132**, 200403
  (2024).
