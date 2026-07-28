## Team

| | |
|---|---|
| **Team name** | LlmNewtonGaussTuring |
| **Members** | Xeri Chen |

## Challenge

| Row | |
|---|---|
| **Challenge** | Is the ratio of transverse-field Ising critical points on the triangular and honeycomb lattices exactly √5? Determine whether $R = h_c^{\triangle}/h_c^{\hexagon} = \sqrt{5}$ holds by sharpening both critical fields with sign-free QMC (SSE with cluster updates), using a pre-registered finite-size scaling analysis and a sealed verdict gate. |
| **Catalog issue** | Addresses #148 — "Is the ratio of transverse-field Ising critical points on the triangular and honeycomb lattices exactly √5?", released by Xiao-Yan Xu, Shanghai Jiao Tong University. |
| **Track** | `tracks/qmc/solutions/LlmNewtonGaussTuring/` — the issue specifies `Method: Quantum Monte Carlo`. |

## Implementation contract

- `make_honeycomb()` is the single honeycomb constructor.  It preserves the
  historical site and bond ordering exactly while correcting only the
  primitive vectors and basis embedding, so all three graph bonds have equal
  length.  Index-based Stage 1-3 code remains compatible.
- `smallest_momentum_vectors()` enumerates every shortest non-zero torus
  momentum using a geometry-derived finite bound; square, triangular, and
  honeycomb structure factors average all symmetry-related directions.
- `SSEParams::stage4_estimators = true` enables propagation-averaged equal-time
  observables and the analytic Dirichlet-spacing estimator for the Blote-Deng
  space-time Binder ratio.  The default measurement path remains available for
  exact reruns of the earlier equal-time workflow.
- Scan cells use distinct 64-bit seeds for every `(lattice,L,h,replica)` and
  workers return results to the main thread for deterministic CSV ordering.

## Berry-curvature conventions (Challenge 73)

The rotated Hamiltonian is

$$
H(\theta,\Omega)=R_x(\theta)H(0,\Omega)R_x^\dagger(\theta),\qquad
R_x(\theta)=e^{-i\theta\sum_iX_i/2}.
$$

With $A_\mu=i\langle\psi|\partial_\mu\psi\rangle$, the normalized-overlap
Wilson loop has phase $\arg W=-\int F_{\theta\Omega}\,d\theta\,d\Omega$.
`BerryCurvature::wilson_phase`, `flux`, and `F12` therefore denote three
different quantities; `F12` includes division by the oriented plaquette area.

For the one-dimensional chain, the thermodynamic-limit oracle is

$$
\frac{F_{\theta\Omega}}{N}=-\frac{J^2}{2\pi}
\int_0^\pi\frac{\sin^2k\,dk}
{(J^2+\Omega^2-2J\Omega\cos k)^{3/2}}.
$$

## Build and validation

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j 8
ctest --test-dir build --output-on-failure
```

The suite includes lattice safety and compatibility checks, physical Lanczos
residuals, explicit rotation/FHS/Jordan-Wigner identities, SSE exact limits,
and synthetic validation of the Python scaling analysis.

## Stage 4 scan

The paper's physical continuous-time length is `L`, which maps to the quantum
inverse temperature `beta = L / h` in this Hamiltonian convention.

```bash
./build/scan_stage4 triangular 5000 200 25 12 _trial 20 6
./build/scan_stage4 honeycomb 5000 200 25 12 _trial 20 10

uv run --script tools/analyze_stage4.py triangular_stage4_trial_bins.csv \
  --bootstrap 500 --h-min 4.74 --h-max 4.80 --label narrow
uv run --script tools/analyze_stage4.py honeycomb_stage4_trial_bins.csv \
  --bootstrap 500 --h-min 2.11 --h-max 2.15 --label narrow
```

Generated data remain Git-ignored.  Historical Stage 3/4 pilot uncertainties
are not reusable after the seed and bootstrap audit; any new claim must be
derived from freshly generated raw bins with the current analysis pipeline.
