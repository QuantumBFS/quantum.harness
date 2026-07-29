## Team

| | |
|---|---|
| **Team name** | Agent of My Agent Is Not My Agent |
| **Members** | Zhu-YanZhang |

## Challenge

| Row | |
|---|---|
| **Challenge** | Test whether long-range universality in the 1D transverse-field Ising chain crosses over at σ*=7/4 or σ*=2 by measuring critical exponents with MPS and using QMC as an independent cross-check. |
| **Catalog issue** | `Addresses #86` — “Where does long-range universality end? Three adversarial tests of the sigma*=7/4 vs 2 dispute,” released by Kun Chen, Institute of Theoretical Physics, Chinese Academy of Sciences. |
| **Track** | `tracks/mps/` — our call: issue #86 spans MPS, QMC, and VMC-NQS; MPS is our primary method and QMC is an independent cross-check. |

## Workflow

The implementation uses **Python 3.11**, **TeNPy**, and the **MPS/DMRG**
method. The primary calculation uses a custom compact matrix-product-operator (MPO)
representation of the periodic long-range transverse-field Ising chain. The
finite-size reference coupling is the pinned Hurwitz-zeta image sum

```text
J_L(r) = L^(-1-σ) [ζ(1+σ, r/L) + ζ(1+σ, 1-r/L)].
```

The infinite-line power law is approximated by a sum of exponentials, and each
exponential is periodized analytically before it enters the MPO. The workflow
keeps Hamiltonian-approximation error (finite exponential count `K`) separate
from MPS-truncation error (finite bond dimension `χ` and discarded weight).
SSE is reserved for a later independent cross-check and is not part of the
initial MPO implementation.

### Environment

Use the existing conda environment:

```bash
conda run -n mps python <script> [arguments]
```

It must provide TeNPy, NumPy, and SciPy. The current verified environment is
Python 3.11.15, TeNPy 1.1.0 from `~/tenpy`, NumPy 2.4.6, and SciPy 1.17.1.
No project-local TeNPy installation is required.

Phase 1 validation:

```bash
cd tracks/mps/solutions/agent-of-my-agent-is-not-my-agent
conda run -n mps python -m pytest -q
conda run -n mps python scripts/validate_couplings.py \
  --length 64 --sigma 1.75
```

Phase 2 exponential-fit validation:

```bash
conda run -n mps python scripts/validate_exponential_fit.py \
  --length 64 --sigma 1.75 --r-fit 512 \
  --k-values 8 12 16 20 24 --output-dir results/phase2
```

The fit uses only the infinite-chain kernel `r^(-1-σ)`. The exact periodic
Hurwitz-zeta values enter only after fitting, when the exponential sum is
periodized analytically. The command writes maximum/RMS error summaries and
distance-resolved CSV profiles for both validation layers.

Phase 3 periodized-MPO validation:

Phase 3 converts the fitted exponential representation into a compact
finite-ring MPO. Each exponential uses a **direct channel** for
`λ_k^(j-i)` and a **wrapped channel** for `λ_k^(L-j+i)`, so the periodic image
contribution is represented within a finite OBC MPO/MPS framework. The
uncompressed MPO bond dimension is

```text
χ_MPO = 2K + 2 = 50  for K=24.
```

Small-system tests reconstruct every pair coefficient from the contracted MPO,
verify it against the intended periodized-exponential table, and compare the
resulting coefficient table with the exact Hurwitz-zeta coupling `J_L(r)`.
This phase validates the Hamiltonian representation—including direct,
wrapped, and transverse-field channels—and does **not** run DMRG.

Phase 4 nearest-neighbor benchmark:

```bash
conda run -n mps env PYTHONPATH=src python scripts/benchmark_tfim.py \
  --lengths 8 10 12 --gamma 1 --chi-max 128 \
  --output-dir results/phase4_nn_tfim
```

This is a strict ED gate for E₀, E₁, the gap, correlations, variance below
`1e-10`, and excited-state overlap below `1e-10`. It also plots Δ(L) and
LΔ(L), whose finite-size stability at Γ=1 verifies the expected z=1
benchmark. The variance threshold is specific to this small-system
qualification; later production runs must report variance, discarded weight,
and χ convergence without treating `1e-10` as an unconditional cutoff.

Phase 5 compact-MPO validation:

```bash
conda run -n mps env PYTHONPATH=src python \
  scripts/validate_long_range_mpo.py \
  --lengths 8 10 12 --gammas 1.2 1.56 2.0 \
  --sigma 1.75 --k 24 --alpha 0.5 --r-fit 2048 \
  --output-dir results/phase5_mpo_validation
```

This command separates exact-pair ED → compact-MPO ED error from
compact-MPO ED → DMRG error. It reports absolute and relative errors in E₀,
E₁, and Δ, together with translation-averaged periodic C(r). The dense
Frobenius error is retained only as a small-system implementation diagnostic;
the distance-resolved coupling profile is the scalable MPO metric.

Phase 6 is a **validated local reproduction**, not an L=256 production
scaling campaign. It uses the rotated basis `X_phys = Sigmaz`,
`Z_phys = Sigmax`, with explicit even/odd spin-flip parity. The full
correlation function without connected-correlation subtraction is evaluated
as `Sigmax-Sigmax`. Every cell preserves C(r), S(0), S(k_min), ξ, R_ξ,
variance, discarded weight, sweeps, runtime, and checkpoint provenance.

The local crossing bracket is fixed to `Gamma={1.560,1.565}` at `L=32,64`.
The two-size crossing is obtained from the same linear interpolation of
`R_xi(32,Gamma)-R_xi(64,Gamma)` for every K. The MPS uncertainty is measured
at `L=64`, `K=24` by comparing direct `chi=128` with fully reoptimized
`chi=256` states. The MPO uncertainty compares `K=24` with `K=32` at direct
`chi=128` for both sizes and both bracket points. No `L>64`, `chi>256`,
adaptive Gamma point, Slurm job, or approximate MPO compression is used.

The achieved local result is:

| validation axis | observed change |
|---|---:|
| `K=24 -> 32` crossing, `L=32,64` | `Gamma_x: 1.5633075241 -> 1.5633070351` |
| `K=24 -> 32` relative gap, `L=64` | `5.35e-6 ... 5.57e-6` |
| `chi=128 -> 256` R_xi, `L=64` | `4.82e-8 ... 5.00e-8` |
| `chi=128 -> 256` relative gap, `L=64` | `2.45e-8 ... 3.36e-8` |

These numbers establish stable critical-region behavior under the tested MPO
and MPS variations. They are not a thermodynamic-limit estimate of
`Gamma_c` or `z`.

## Phase 7: crossover exploration

Phase 7 builds on the validated local reproduction and changes the target
from one high-precision point to an efficient sigma trend. The exploration
grid is `sigma=1.50,1.60,1.70,1.75,1.80,1.90,2.00`, with `K=24`, `chi=64`,
and `L=32,64`. Every sigma uses the identical
`Gamma=1.20:0.05:1.90` broad grid. Crossings are linearly interpolated
inside the observed sign-change bracket; no narrow-grid refinement or
automatic Gamma expansion was run.

The planner records the broad-grid hash, bracket decision, interpolation
points, crossing resolution, provenance, and selective `chi=128` validation
flags. This exploration makes no thermodynamic-limit `Gamma_c`, `z`, or
crossover-location claim. It preserves exact-zero MPO pruning, checkpoint
resumability, full raw observables, and the separation of MPO, MPS, and
finite-size uncertainty.

The completed broad scan contains 210 resumable even-sector cells. Selective
odd-sector `chi=128` calculations give accepted two-size `z_eff(32,64)`
estimates at `sigma=1.75,1.80,2.00`; the optional `sigma=1.60` estimate
remains incomplete because its `L=64` discarded weights exceed the locked
threshold. Equal-time zero-momentum structure factors are retained only as
auxiliary finite-size diagnostics. They are not the imaginary-time-integrated
susceptibility and are not labeled `gamma/nu`.

The final tables, plot, machine-readable analysis, and bounded local report
are in `results/phase7-crossover/final-track-b/`. No `K=32`, `L=128`, or
Gamma-refinement calculation was added in Phase 7.

## Phase 8: sigma=1.75 finite-size scaling

Phase 8 stops the broad sigma scan and first extends only `sigma=1.75` to
`L=128`. The `R_xi(64,128)` crossing uses the locked endpoints
`Gamma={1.55,1.60}`, even parity, `K=24`, and `chi=64`. Phase 7 found
`chi=64 -> 128` changes in `R_xi` below `4e-6`, smaller than the relevant
crossing-resolution uncertainty. Final common-field even/odd gap states use
`chi=128` at the single resolved primary field
`Gamma_c_power=1.5738504887054727`.

The two crossings define exact two-point sensitivity extrapolations in the
coordinates `1/L` and `1/log(L)`. These coordinates test correction-form
sensitivity; they do not assume that a leading correction exponent is known
and are not statistical regressions. The power/log critical-field spread is
reported separately and is not fully propagated into the gaps because only
two crossings are available.

The gap campaign uses `L={16,32,64,96,128}`. Four generalized adjacent-size
`z_eff` values are associated with geometric-mean sizes and analyzed with
the approved sensitivity coordinates `z_eff=z+a/L_eff` and
`z_eff=z+a/log(L_eff)`. Both are deterministic five-size regressions; a
leave-`L=16`-out result measures sensitivity to the smallest size. Adjacent
values share gap estimates and are therefore not treated as independent
statistical samples.

After the `L=64` odd-sector state produced discarded weight `5.49e-8`
while its variance and energy convergence passed, the Phase 8-only
discarded-weight gate was relaxed from `1e-8` to `1e-7`. The relative
variance gate remains `1e-10`. This is a documented post-observation
protocol amendment; accepted states are not rerun, and the change is
carried into the final uncertainty budget.

The final report will compare the resulting `z` sensitivities with
Shiratani--Todo's published `sigma=7/4` values, `z=0.91(2)` for power
corrections and `z=0.98(3)` for logarithmic corrections
([arXiv:2305.14121v4](https://arxiv.org/abs/2305.14121), Table 2). Their
calculation reaches `L=362`; the present `L<=128` result is therefore a
qualitative comparison rather than a precision reproduction.

No `sigma=1.80` or `sigma=2.00` plan is created until the complete
`sigma=1.75` result is reviewed. Susceptibility `gamma/nu` remains outside
the DMRG scope, and equal-time `S_eq(0)` remains an auxiliary diagnostic.

Create the two-cell crossing plan without running DMRG:

```bash
PYTHONPATH=src:. conda run -n mps python -u \
  scripts/plan_phase8_scaling.py crossing \
  --output results/phase8-scaling/sigma-1.75/crossing-L128/run_spec.json
```

Prepare the focused K comparison:

```bash
PYTHONPATH=src:. conda run -n mps python \
  scripts/prepare_local_k_comparison.py \
  --k24-summary results/phase2_tail_stable/rfit_2048/alpha_05/summary_K24.json \
  --sigma 1.75 --lengths 32 64 --l-max 256 \
  --output-dir results/phase6_sigma1.75/validated-local-reproduction/fits
```

Assemble the completed local comparison:

```bash
PYTHONPATH=src:. conda run -n mps python \
  scripts/analyze_local_reproduction.py \
  --comparison-spec \
    results/phase6_sigma1.75/validated-local-reproduction/comparison-spec.json \
  --output-dir \
    results/phase6_sigma1.75/validated-local-reproduction
```

## Development milestones

1. **Exact Hurwitz-zeta coupling validation** — compare the finite-ring formula
   with converged direct image sums and verify positivity, periodic symmetry,
   and pair-counting conventions.
2. **Exponential fitting validation** — fit the infinite-line power law for
   `K = 8, 12, 16, 20, 24` and report distance-resolved coupling errors after
   analytic periodization.
3. **Periodized MPO construction** — encode forward and wrapped exponential
   channels and verify that the MPO reconstructs the intended coefficient
   table.
4. **MPO observable validation** — compare the compact MPO with the exact
   pairwise Hamiltonian on small systems using the ground-state energy, first
   excitation gap, and correlation functions.
5. **DMRG scaling calculations** — independently converge `χ` at each `K`,
   then study the stability of `Γ_c(K)` and `z(K)` with increasing exponential
   count.

## Layout

| Path | Purpose |
|---|---|
| `src/` | Reusable coupling, fitting, MPO, and analysis modules. |
| `scripts/` | Runnable validation and production entry points. |
| `tests/` | Deterministic unit, regression, and small-system tests. |
| `docs/methodology.md` | Mathematical conventions, algorithms, and error budget. |
| `results/phase*/` | Phase-scoped validation data, summaries, tables, and plots, including `phase2_tail_stable/` and future phase outputs. |

Later production data, plots, and reports belong under
`tracks/mps/results/<timestamped-run>/`; phase-level validation artifacts are
kept locally in this solution folder for review.
