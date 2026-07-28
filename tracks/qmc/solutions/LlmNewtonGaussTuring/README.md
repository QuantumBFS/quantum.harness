## Team

| | |
|---|---|
| **Team name** | LlmNewtonGaussTuring |
| **Members** | Xeri Chen |

## Challenge

| Row | |
|---|---|
| **Challenge** | Test whether the triangular/honeycomb transverse-field Ising critical-field ratio is exactly $\sqrt{5}$ using sign-free SSE QMC, preregistered finite-size scaling, and a sealed verdict gate. |
| **Catalog issue** | Addresses #148, released by Xiao-Yan Xu, Shanghai Jiao Tong University. |
| **Track** | `tracks/qmc/solutions/LlmNewtonGaussTuring/` |

## Implementation contract

- `make_honeycomb()` preserves the historical site and bond ordering while
  using equal-length graph bonds in the stored embedding.
- `smallest_momentum_vectors()` enumerates every symmetry-related shortest
  non-zero torus momentum from the geometry rather than a fixed search box.
- `SSEParams::stage4_estimators` enables propagation-averaged equal-time
  observables and the exact Dirichlet-spacing estimator for the Blote-Deng
  space-time Binder ratio.
- Production cells use distinct deterministic 64-bit seeds for every
  `(lattice,L,h,initial_state,replica)` and include both hot and cold starts.
- `config_checked=false` is represented by `consistency_failures=-1`; zero is
  reported only when the O(M) world-line validation actually ran.
- `run_stage4.py` writes one atomic raw file and manifest per cell, records
  source/build/host provenance and SHA-256 hashes, and refuses incomplete or
  mismatched collections.

The frozen physical and statistical choices are in [`PROTOCOL.md`](PROTOCOL.md).

## Berry-curvature conventions (Challenge 73)

The shared code also serves Challenge 73. Its rotated Hamiltonian is

$$
H(\theta,\Omega)=R_x(\theta)H(0,\Omega)R_x^\dagger(\theta),\qquad
R_x(\theta)=e^{-i\theta\sum_iX_i/2}.
$$

With $A_\mu=i\langle\psi|\partial_\mu\psi\rangle$, the normalized-overlap
Wilson loop has phase $\arg W=-\int F_{\theta\Omega}\,d\theta\,d\Omega$.
`wilson_phase`, `flux`, and `F12` are therefore distinct quantities; `F12`
includes division by oriented plaquette area.

For the one-dimensional chain, the thermodynamic-limit oracle is

$$
\frac{F_{\theta\Omega}}{N}=-\frac{J^2}{2\pi}
\int_0^\pi\frac{\sin^2k\,dk}
{(J^2+\Omega^2-2J\Omega\cos k)^{3/2}}.
$$

For an even periodic chain, the same-size oracle uses antiperiodic
Jordan-Wigner momenta $k_m=(2m+1)\pi/N$:

$$
\frac{F_{\theta\Omega}^{(N)}}{N}=-\frac{J^2}{2N}\sum_{m=0}^{N-1}
\frac{\sin^2 k_m}{(J^2+\Omega^2-2J\Omega\cos k_m)^{3/2}}.
$$

FHS plaquettes are compared to this finite-$N$ oracle under grid refinement.
All four ground-state corners must converge. The historical
`dthetah_diagonal` API is only a prefactor-weighted ZZ expectation in the
unrotated ensemble, not a generalized force.

## Build and validation

```bash
cmake -S . -B build-production -DCMAKE_BUILD_TYPE=Release
cmake --build build-production --parallel 8
ctest --test-dir build-production --output-on-failure
```

The suite covers lattice invariants, Lanczos residuals, rotation/FHS/Jordan-
Wigner identities, SSE analytic limits and ED comparisons, synthetic scaling,
and the complete atomic cell/manifest/collection path.

## Resumable Challenge 148 scan

The paper-matched aspect ratio is $\beta h/L=c_\tau=1$; selected finite-
temperature checks use $c_\tau=2$.

```bash
uv run --script tools/run_stage4.py plan \
  --run-id c148-triangular-stage4 --lattice triangular \
  --sizes 6,8,10,12,14,16,18,20 \
  --fields 4.74,4.75,4.76,4.77,4.78,4.79,4.80 \
  --thermal 5000 --bins 200 --sweeps-per-bin 25

uv run --script tools/run_stage4.py run-local \
  --run-spec ../../../../results/c148-triangular-stage4/run_spec.json \
  --workers 12 --collect

uv run --script tools/analyze_stage4.py \
  ../../../../results/c148-triangular-stage4/c148-triangular-stage4_bins.csv \
  --bootstrap 500 --protocol-window narrow --l-min 6 \
  --robustness-matrix --enforce-protocol --label narrow
```

Protocol enforcement admits only the frozen field windows, minimum sizes, and
correction exponents, and also enforces the hot/cold sampling gates. The
robustness command writes every registered window/$L_{\min}$/$\omega$/mixed-
term result, including explicit failed variants, to one CSV. The companion
crossing and standardized-residual figures are written beside the fit tables.

The analysis also writes bin-growth, independent-chain-spread, and 10%/20%
discarded-prefix diagnostics. Compare matched finite-temperature runs with:

```bash
uv run --script tools/compare_ctau.py \
  ../../../../results/<c-tau-1>/<c-tau-1>_bins.csv \
  ../../../../results/<c-tau-2>/<c-tau-2>_bins.csv \
  --output-prefix ../../../../results/<comparison>/<comparison> \
  --protocol-window narrow --l-min <registered-L-min> \
  --hc-shift-budget <registered-budget> --enforce
```

Pointwise observable shifts are reported but are not gates because changing
the space-time aspect ratio changes the finite-size scaling functions. The
hard gate distinguishes fitted critical-field consistency from sufficient
resolution: the 95% upper bound on the fitted shift must fit inside the
registered absolute finite-temperature budget.

Generated data remain Git-ignored. Historical Stage 3/4 pilot uncertainties
are invalid because those runs reused seeds across fields and resampled bins as
independent. New claims must come from freshly generated manifests and raw bins
using the current pipeline. `scan_stage4` remains only as a historical
monolithic rerun entry point.

## Stage 5 cost model

Use completed cell manifests and one accepted fit to estimate a larger grid:

```bash
uv run --script tools/estimate_stage5.py <run-directory> \
  --fit-csv <accepted-fit.csv> --observable xi \
  --target-error <registered-hc-error> \
  --future-sizes 24,32,40,48,56,64 --field-count 7 \
  --chains 4 --workers 16 --output-prefix <results-prefix>
```

The output fits measured median cell wall time to a power law in $L$ and shows
both a same-statistics pilot and an optimistic production estimate. It assumes
ideal worker scaling and the $L^{1/\nu}$ critical-slope gain; it excludes
autocorrelation growth, failed systematic gates, queueing, and I/O, so it is a
planning lower bound rather than a precision forecast.

## ParaToric independent-route qualification

ParaToric is an optional, separately pinned dependency. Configure its core and
tests first, then point this project at the generated package config:

```bash
cmake -S . -B build-paratoric-audit -DCMAKE_BUILD_TYPE=Release \
  -DCM_ENABLE_PARATORIC_AUDIT=ON \
  -Dparatoric_DIR=<paratoric-build>/cmake \
  -DBoost_DIR=<boost-root>/lib/cmake/Boost-1.88.0 \
  -DBoost_USE_STATIC_LIBS=OFF
cmake --build build-paratoric-audit --target paratoric_crosscheck

uv run --script tools/run_paratoric_crosscheck.py \
  --executable build-paratoric-audit/paratoric_crosscheck \
  --output <results-directory> \
  --case square:3:3.04438 --case triangular:2:4.76 \
  --chains 4 --thermal 200000 --samples 50000 --between 100 \
  --boost-lib <boost-root>/lib
```

The tool writes raw chains, the full/even-sector diagnostics, and the required
`cross-method-check.csv`. These are normalization checks only. The honeycomb
target starts at $L=4$ because ParaToric's triangular $L=2$ periodic plaquettes
are degenerate, and no independent thermodynamic-limit result is yet accepted.
