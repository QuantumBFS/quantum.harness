# Challenge 73 — Resolvent Route: Results

Date: 2026-07-30
Plan: [`Challenge 73 - PLAN-2026-07-30 Resolvent Route.md`](Challenge%2073%20-%20PLAN-2026-07-30%20Resolvent%20Route.md)
Code: `tracks/qmc/solutions/LlmNewtonGaussTuring` @ branch `c73-continuation`
Superseded in part: [`Challenge 73 - Final Report.md`](Challenge%2073%20-%20Final%20Report.md) §3.3, §3.4

---

## 0. What this delivers

Phases **P0–P3** of the plan are complete, plus requirement **C** (the
`Δ ≠ 0` mixed component, planned as part of P6). The Fukui–Hatsugai–Suzuki
(FHS) Wilson-loop production route is retired to the role of oracle.

| plan phase | status | evidence |
|---|---|---|
| P0 matrix-free core + identity test | done | `tests/test_identity.cpp`, 244 assertions, `ctest` green |
| P1 `scan_curvature`, rerun `L = 2,3,4` | done | 235 `Ω` points per size, `results/resolvent/curvature_square_L{2,3,4}_z2even.csv` |
| P2 ℤ₂ sector, reach `L = 5` (`N = 25`) | done | 23 `Ω` points, `dim = 16 777 216`, 41:55 wall, 1.32 GB peak |
| P3 chain + inverse moments | done | `M₀…M₃`, `v*`, `M₁/M₂` in every CSV row |
| C: `Δ ≠ 0` mixed curvature | done | `results/resolvent/delta_component_square_L{3,4}_full.csv` |
| P4 SSE `χ_F` estimator | **not started** | would contend with the running Challenge 148 jobs |
| P5 iPEPS `⟨σˣ⟩` at `D = 2…6` | **not started** | same |
| P6 `k = 0` momentum sector | **not needed so far** | ℤ₂ alone reached `L = 5` inside the memory budget |

The headline correction stands: **the published `L = 4` critical-region
curvature carries 10–28 % error for `Ω ≥ 3.0`**, and the error is FHS `θ`-grid
discretisation, not statistical noise. The exact values replace it.

---

## 1. The identity, and why the 2D grid disappears

For `H(θ,λ) = R_x(θ) H₀(λ) R_x(θ)†` with `H₀` real symmetric in the `σᶻ`
basis and `R_x(θ) = exp(−i(θ/2)ΣᵢXᵢ)`, the real-gauge Berry connection is

```
A_θ = ½⟨ΣᵢXᵢ⟩   (independent of θ),      A_λ = 0,
```

so the curvature is a single resolvent matrix element,

```
F_θλ = −½ ∂⟨ΣX⟩/∂λ = ⟨b_X|(H₀−E₀)⁻¹|b_λ⟩,
  b_X = Q(ΣᵢXᵢ)|0⟩,   b_λ = Q(∂_λH₀)|0⟩,   Q = 1 − |0⟩⟨0|.
```

With `λ = Ω` (so `∂_Ω H₀ = −ΣX`) this collapses to one negative-definite
number per point:

```
F_θΩ = −⟨b_X|(H₀−E₀)⁻¹|b_X⟩ = ½ ∂²E₀/∂Ω² ≤ 0.
```

Consequences for the code: no `θ` axis, no Wilson loop, no complex arithmetic,
no gauge fixing, and no `θ`-discretisation error. One ground-state Lanczos plus
one projected CG solve per `Ω` point replaces a full 2D plaquette grid.

Writing `φ = (H₀−E₀)⁻¹b_X` and `ω_n = E_n − E₀`, the same solve yields the
inverse moments of the `ΣX` spectral function,

```
M_p = Σ_{n≠0} |⟨n|ΣX|0⟩|² / ω_nᵖ
M₀ = ⟨(ΣX)²⟩ − ⟨ΣX⟩²    (sum rule)
M₁ = −F_θΩ = ⟨b_X|φ⟩
M₂ = χ_F    = ⟨φ|φ⟩       (free — no extra work)
M₃          = ⟨φ|(H₀−E₀)⁻¹|φ⟩   (one more CG solve)
```

`M₂` costing nothing is what makes `L = 5` affordable: the 200-vector Lanczos
chain needs 26.8 GB at `N = 25`, the CG route needs 1.3 GB.

---

## 2. Implementation

New modules in `src/`, all matrix-free (precomputed `O(dim)` diagonal plus a
single-bit-flip gather; no stored matrix):

| file | contents |
|---|---|
| `matfree.{hpp,cpp}` | `SymOperator` interface, `TFIMOperator`, `apply_sum_sx/sz`, `z2_parity_expectation`, BLAS-1 helpers, OpenMP thread control |
| `hilbert.{hpp,cpp}` | `TFIMOperatorZ2` (spin-flip sector, `dim = 2^{N−1}`), sector `ΣX`, sum rule, expansion back to the full basis |
| `lanczos_real.{hpp,cpp}` | real symmetric Lanczos ground state (two-pass when reorthogonalisation exceeds the memory budget), `lanczos_chain`, `chain_spectrum`, `inverse_moment` |
| `cg.{hpp,cpp}` | `projected_cg` on `Q = 1 − |0⟩⟨0|`, reprojecting every iteration |
| `resolvent.{hpp,cpp}` | the driver: `resolvent_curvature`, `resolvent_curvature_z2`, `resolvent_curvature_generic` with a `BasisHooks` struct |

Tools: `tools/scan_curvature.cpp` (production scan, 47-column CSV),
`tools/analyze_resolvent_scaling.py`, `tools/analyze_delta_component.py`.

The gather form of the off-diagonal term parallelises without atomics:

```cpp
double value = diag[state] * x[state];
for (int site = 0; site < N; ++site)
    value -= Omega * x[state ^ (std::size_t{1} << site)];
y[state] = value;
```

The plan's `core/` + `routes/` directory split was **not** adopted: it would
have renamed `lattice.cpp` and `berry.cpp`, which Challenge 148 also compiles.
The module decomposition is the plan's; the directory layout stays flat.

---

## 3. Validation

Five checks, each comparing quantities that share no code path.

| # | check | scope | result |
|---|---|---|---|
| 1 | vs. dense `compute_berry_curvature_response_ed` | `N ≤ 10` | machine precision |
| 2 | vs. FHS Wilson loop under grid refinement | `L = 2,3` | abs err `4.54e−5 → 6.17e−6 → 1.22e−6 → 2.87e−7` for step `0.2 → 0.1 → 0.05 → 0.025`, i.e. `O(step²) → exact` |
| 3 | vs. Jordan–Wigner analytic oracle | 1D chain | machine precision |
| 4 | projected CG vs. independent Lanczos chain | `L = 2,3,4`, 235 points each | max rel mismatch `1.5e−12` (`F`), `3.3e−12` (`χ_F`), `2.8e−11` (sum rule) |
| 5 | `F` vs. `½ ∂²E₀/∂Ω²` (5-point stencil) | all four sizes | see below |

Check 5 is the one that survives to production size, because `E₀` comes from
Lanczos alone and `F` from the CG solve:

```
  L       h   pts  median rel err   max rel err  expected O(h^4)
  2   0.025   215        3.50e-08      5.55e-07         3.91e-07
  3   0.025   215        4.86e-08      2.66e-07         3.91e-07
  4   0.025   215        5.97e-08      8.56e-07         3.91e-07
  5   0.050     9        2.39e-05      4.71e-05         6.25e-06
```

Every entry is at the stencil truncation floor. At `L = 5` the Lanczos chain
does not fit in memory, so check 5 is the independent cross-validation there.

**Solver diagnostics**, all 728 production points:

```
  L   N       dim  pts  max F mism  max chi mism  max sum-rule  max cg it  min|<P>|  gs ok  cg ok   wall s
  2   4         8  235    6.61e-16      1.07e-15      1.99e-14          2  1.000000      1      1      0.0
  3   9       256  235    2.68e-14      4.99e-14      2.48e-13         12  1.000000      1      1     24.3
  4  16     32768  235    1.49e-12      3.29e-12      2.84e-11         27  1.000000      1      1    483.6
  5  25  16777216   23          --            --            --         38  1.000000      1      1   2515.0
```

`⟨P⟩ = 1` for the global spin flip at every point. This matters: on the **full**
`2^N` basis at `L = 4, Ω = 0.5` the near-degenerate ℤ₂ doublet is returned as a
mixture (`⟨P⟩ = 0.219`), and while `E₀` still matches to 12 digits and `F` to
`1.6e−9`, `χ_F` is wrong by three orders of magnitude (439.6 vs 0.256) and CG
does not converge. Working in the ℤ₂-even sector removes this entirely, and
`z2_parity_expectation` is an `O(dim)` diagnostic that detects it. The Ritz gap
does **not** detect it — it read 7.76 there because the second Ritz value was
itself unconverged.

---

## 4. Corrected curvature density vs. the published FHS tables

Exact `F/N` against Final Report §3.2/§3.3. The exact column has no `θ`
discretisation error, so the difference *is* the FHS grid error.

**`L = 2`** (fine FHS grid, `dθ = 0.04`, `dΩ = 0.10`): 0.5–5.2 % — acceptable.
**`L = 3`** (same grid): 0.5–7.8 % — acceptable.
**`L = 4`** (coarse FHS grid, `dθ = 0.10`, `dΩ = 0.25`):

| `Ω` | exact `F/N` | published FHS | abs diff | rel diff |
|---|---|---|---|---|
| 1.000 | −0.129093 | −0.1282 | 0.0009 | 0.7 % |
| 2.000 | −0.155310 | −0.1478 | 0.0075 | 4.8 % |
| 2.500 | −0.196742 | −0.1914 | 0.0053 | 2.7 % |
| 2.544 | −0.195046 | −0.1848 | 0.0102 | 5.3 % |
| **3.000** | **−0.103777** | −0.1330 | 0.0292 | **28.2 %** |
| **3.044** | **−0.094629** | −0.0803 | 0.0143 | **15.1 %** |
| **3.500** | **−0.037559** | −0.0479 | 0.0103 | **27.5 %** |
| **3.544** | **−0.034702** | −0.0303 | 0.0044 | **12.7 %** |
| **4.000** | **−0.017192** | −0.0205 | 0.0033 | **19.2 %** |
| **5.000** | **−0.006083** | −0.0067 | 0.0006 | **10.1 %** |

The error is worst exactly where the physics is — at and above `Ω_c`. The
`L = 2, 3` numbers stand; only the `L = 4` critical-region grid is superseded,
and it was cheaper to recompute exactly than to re-measure.

---

## 5. New size: `L = 5` (`N = 25`)

ℤ₂-even sector, `dim = 16 777 216`, `--no-chain --m3-cg`, 6 threads,
41:55 wall for 23 points, 1.32 GB peak RSS, ≤ 38 CG iterations everywhere.

| `Ω` | `E₀/N` | `F/N` | `χ_F/N` | `v*` | `M₁/M₂` |
|---|---|---|---|---|---|
| 1.00000 | −2.12566204 | −0.12908261 | 0.01728498 | 1.5212 | 7.4679 |
| 2.00000 | −2.51133404 | −0.14607457 | 0.02566683 | 1.2484 | 5.6912 |
| 2.50000 | −2.81237834 | −0.19327854 | 0.05329980 | 0.8663 | 3.6263 |
| 2.65000 | −2.92006293 | −0.20751822 | 0.06589264 | 0.7791 | 3.1493 |
| 2.70000 | −2.95801115 | −0.20528814 | 0.06684816 | 0.7735 | 3.0710 |
| 3.00000 | −3.20532406 | −0.12028354 | 0.03467035 | 1.0741 | 3.4693 |
| **3.04438** | **−3.24418383** | **−0.10650148** | **0.02932353** | **1.1679** | **3.6319** |
| 3.50000 | −3.66057850 | −0.03374555 | 0.00550813 | 2.6948 | 6.1265 |
| 4.00000 | −4.13520028 | −0.01482593 | 0.00156936 | 5.0486 | 9.4471 |
| 5.00000 | −5.10455124 | −0.00549376 | 0.00035638 | 10.5943 | 15.4152 |

Full 23-point grid in `results/resolvent/curvature_square_L5_z2even.csv`.

**Critical region across all four sizes** (`Ω_c = 3.04438` at `J = 1`):

| `L` | peak `\|F\|/N` | at `Ω` | peak `χ_F/N` | at `Ω` | `F/N` at `Ω_c` | max CG it |
|---|---|---|---|---|---|---|
| 2 | 0.192948 | 1.3604 | 0.032517 | 1.3908 | −0.054631 | 2 |
| 3 | 0.187654 | 2.1514 | 0.040118 | 2.2118 | −0.078649 | 12 |
| 4 | 0.196894 | 2.4815 | 0.052593 | 2.5355 | −0.094553 | 27 |
| 5 | 0.207519 | 2.6489 | 0.066867 | 2.6939 | −0.106501 | 38 |

Both peaks drift monotonically toward `Ω_c`. `χ_F/N` peaks closer to `Ω_c` than
`|F|/N` at every size and is the sharper pseudo-critical marker.

**`1/L` extrapolation of `F/N`.** With four sizes the residual is now
meaningful, and it shows where a `1/L` form fails:

| `Ω` | `L=2` | `L=3` | `L=4` | `L=5` | `F_∞` | RMS resid |
|---|---|---|---|---|---|---|
| 1.000 | −0.179073 | −0.130272 | −0.129093 | −0.129083 | −0.086398 | 8.6e−3 |
| 2.000 | −0.149310 | −0.183207 | −0.155310 | −0.146075 | −0.156066 | 1.5e−2 |
| 2.500 | −0.095152 | −0.160560 | −0.196742 | −0.193279 | −0.274214 | 7.8e−3 |
| 3.000 | −0.057143 | −0.084125 | −0.103777 | −0.120284 | −0.156862 | 3.5e−3 |
| 3.044 | −0.054631 | −0.078649 | −0.094553 | −0.106501 | −0.137980 | 2.1e−3 |
| 3.500 | −0.034983 | −0.039910 | −0.037559 | −0.033746 | −0.036373 | 2.4e−3 |
| 4.000 | −0.022384 | −0.020837 | −0.017192 | −0.014826 | −0.011006 | 1.1e−3 |
| 5.000 | −0.010495 | −0.007716 | −0.006083 | −0.005494 | −0.001992 | 9.9e−5 |

Residuals reach `1.5e−2` in and below the critical region — comparable to the
extrapolated values themselves. **The Final Report §3.4 `1/L` fit is not valid
there.** Deep in the paramagnetic phase (`Ω ≥ 4`) the fit is well behaved.

---

## 6. Finite-size scaling indicators

Measured at `Ω_c`, four sizes:

| `L` | `M₁/M₂` | `\|F\|/N` | `χ_F/N` | `Ω_c − Ω*(χ_F)` |
|---|---|---|---|---|
| 2 | 9.069308 | 0.054631 | 0.006024 | 1.653551 |
| 3 | 5.890843 | 0.078649 | 0.013351 | 0.832567 |
| 4 | 4.463529 | 0.094553 | 0.021183 | 0.508867 |
| 5 | 3.631946 | 0.106501 | 0.029324 | 0.350491 |

| quantity | fitted `L^p` | log-RMS | expected | identification |
|---|---|---|---|---|
| `M₁/M₂` (mean response gap) | **−0.9999** | 1.1e−2 | −1.0000 | `−z`, `z = 1` exactly |
| `Ω_c − Ω*(χ_F peak)` | −1.6951 | 2.1e−3 | −1.5874 | `−1/ν` |
| `\|F\|/N` at `Ω_c` | 0.7317 | 3.0e−2 | 0.1747 | `α/ν = 2/ν − (d+z)` |
| `χ_F/N` at `Ω_c` | 1.7316 | 4.1e−2 | 0.1747 | `2/ν − (d+z)` |

The first row is the clean one. `M₁/M₂ = ⟨b|(H−E₀)⁻¹|b⟩ / ‖(H−E₀)⁻¹b‖²` is a
spectral-weight-averaged excitation energy; it fits `L^{−0.9999}` over
`L = 2…5` with log-RMS `1.1e−2`. That is the dynamical exponent `z = 1` of the
(2+1)D Ising class, recovered from four small clusters, and it is the one
indicator already asymptotic at these sizes.

The pseudo-critical drift gives an effective `1/ν = 1.695` against the 3D Ising
value `1.5874` (ν = 0.629971) — a very clean power law (log-RMS `2.1e−3`) with
a 6.8 % exponent offset, which is what corrections to scaling at `L ≤ 5` permit.

**The amplitude exponents are not exponent estimates.** At these sizes the
`χ_F` peak still sits at `Ω* = 2.694 ≪ Ω_c = 3.044`, so `Ω_c` lies on the
disordered side of the finite-size crossover and the fitted powers are
drift-dominated. Four sizes spanning `L = 2…5` cannot determine exponents. The
QMC route (P4) is what would settle them.

---

## 7. Quantity #5 — leading finite-rate corrections

For a linear ramp of `Ω` at rate `v = dΩ/dt`, the leading adiabatic-perturbation
results are `P_ex = v²M₂ + O(v⁴)`, `ΔE = v²M₁ + O(v⁴)`, breakdown rate
`v* = M₂^{−1/2}`. All are inverse moments of the same spectral function, so
they come from the CG solution already computed.

| `L` | `Ω` | `M₁ = −F` | `M₂ = χ_F` | `M₃` | `v*` | `M₁/M₂` | `M₂/M₃` |
|---|---|---|---|---|---|---|---|
| 3 | 3.044 | 0.707845 | 0.120160 | 0.021087 | 2.8848 | 5.8908 | 5.6983 |
| 4 | 3.044 | 1.512841 | 0.338934 | 0.080365 | 1.7177 | 4.4635 | 4.2174 |
| 5 | 1.000 | 3.227065 | 0.432124 | 0.058396 | 1.5212 | 7.4679 | 7.3999 |
| 5 | 2.500 | 4.831964 | 1.332495 | 0.399182 | 0.8663 | 3.6263 | 3.3381 |
| 5 | 3.044 | 2.662537 | 0.733088 | 0.218727 | 1.1679 | 3.6319 | 3.3516 |
| 5 | 3.500 | 0.843639 | 0.137703 | 0.025333 | 2.6948 | 6.1265 | 5.4357 |
| 5 | 5.000 | 0.137344 | 0.008910 | 0.000623 | 10.5943 | 15.4152 | 14.3071 |

`v*` has a minimum near the pseudo-critical field and rises steeply on both
sides, and it falls with `L` at `Ω_c` (`2.88 → 1.72 → 1.17` for `L = 3,4,5`) —
the adiabatic window closes as the system grows, as expected when the gap
scales as `L^{−z}`.

**Stated plainly, per the plan's risk table:** this is the leading order of a
perturbative expansion, not a finite-rate simulation. It gives the
adiabatic-response coefficients and the rate at which adiabaticity breaks down.
The full non-perturbative dynamics still requires TDVP or QAQMC. **Quantity #5
is not "complete".**

---

## 8. Requirement C — longitudinal field `Δ ≠ 0`

`∂_Δ H₀ = ΣᵢZᵢ`, so `F_θΔ = ⟨b_Z|φ⟩` with the *same* `φ`: one extra
matrix-vector product, not a second solve. `ΣᵢZᵢ` is odd under the spin flip,
so these runs must use the full `2^N` basis, and `F_θΔ ≡ 0` at `Δ = 0` by
symmetry.

Sweeps at `L = 3` (dim 512) and `L = 4` (dim 65 536), 31 `Δ` values × 4 `Ω`
each, all converged. `L = 4`, `Ω = Ω_c`:

| `Δ` | `⟨ΣX⟩` | `F_θΩ` | `F_θΔ` | antisym err |
|---|---|---|---|---|
| ±0.010 | 13.965833 | −1.551441 | ∓1.859166 | 7.0e−12 |
| ±0.020 | 13.912187 | −1.654063 | ∓3.441117 | 2.0e−12 |
| ±0.050 | 13.622730 | −2.043727 | ∓5.587845 | 2.8e−11 |
| ±0.200 | 12.310895 | −2.079893 | ∓3.142901 | 7.0e−12 |
| ±0.500 | 10.949131 | −1.710692 | ∓1.754431 | 2.0e−12 |

Two independent checks:

- **Antisymmetry** `F_θΔ(−Δ) = −F_θΔ(Δ)`, exact and free of any differencing:
  satisfied to `≤ 3.8e−11` at every point.
- **Derivative identity** `F_θΔ = −½ ∂⟨ΣX⟩/∂Δ`, central differences with
  `h = 0.001`: agreement to `1e−7 … 4e−5`, i.e. the `O(h²)` truncation floor.
  At `Δ = 0` both sides vanish to `4.4e−10` (`L=4`) and `1.1e−11` (`L=3`).

The sharp peak of `F_θΔ` at small `|Δ|` is physical: `Δ` mixes the
near-degenerate ℤ₂ doublet, so `∂⟨ΣX⟩/∂Δ` is large on the scale of the
finite-size splitting and collapses once `Δ` dominates it. At `L = 4` and
`Ω ≥ 2` the full-basis ground state is still a clean parity eigenstate at
`Δ = 0` (`⟨P⟩ = 1` even where the Ritz gap is `0.015`); the mixing problem of
§3 is confined to smaller `Ω`.

---

## 9. Cost ledger

| size | basis | `dim` | points | wall | peak RSS | threads |
|---|---|---|---|---|---|---|
| `L=2` | ℤ₂ even | 8 | 235 | < 1 s | — | 1 |
| `L=3` | ℤ₂ even | 256 | 235 | 24 s | — | 1 |
| `L=4` | ℤ₂ even | 32 768 | 235 | 484 s | — | 1 |
| `L=5` | ℤ₂ even | 16 777 216 | 23 | 2515 s | 1.32 GB | 6 |
| `L=3` `Δ≠0` | full | 512 | 124 | 17 s | — | 1 |
| `L=4` `Δ≠0` | full | 65 536 | 124 | 523 s | — | 1 |

`L = 4` at 235 points includes the 200-iteration Lanczos chain, which is the
dominant cost; `L = 5` drops it (`--no-chain`) and adds one CG solve for `M₃`.

Reproduction:

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j2
ctest --test-dir build -R 'identity|curvature'

for L in 2 3 4; do
  ./build/scan_curvature --geometry square --L $L --sector z2even --m3-cg \
    --omega-min 0.25 --omega-max 6.0 --domega 0.025 \
    > results/resolvent/curvature_square_L${L}_z2even.csv
done
./build/scan_curvature --geometry square --L 5 --sector z2even --no-chain \
  --m3-cg --threads 6 --omega-list 1.0,1.5,2.0,2.40,2.45,2.50,2.55,2.60,2.65,\
2.70,2.75,2.80,2.85,2.90,2.95,3.00,3.04438,3.05,3.10,3.15,3.5,4.0,5.0 \
  > results/resolvent/curvature_square_L5_z2even.csv

uv run --script tools/analyze_resolvent_scaling.py
uv run --script tools/analyze_delta_component.py
```

---

## 10. Not done, and why

- **P4 (SSE `χ_F` estimator, `L = 6…20`)** and **P5 (iPEPS `⟨σˣ⟩` at
  `D = 2…6`)** are not started. Both are ~1 day of compute on this workstation
  and would contend with the running Challenge 148 jobs. They are what would
  turn §6's indicators into actual exponent estimates and close the two
  "partial" rows of the plan's requirement-coverage table.
- **P6 momentum sector** was not needed: the ℤ₂ sector alone reached `L = 5`
  within 1.32 GB. It remains the route to `L = 6` (`N = 36`) if wanted, though
  `2³⁵` amplitudes is 275 GB and out of reach here regardless.
- **Cross-validation matrix**: the `SSE` and `iPEPS` columns are still empty at
  every row. The ED columns (dense response, FHS, resolvent CG, Lanczos chain)
  are complete for `1D N=6`, `square L=3`, `square L=4`; at `square L=5` only
  the CG column exists, cross-checked by `½∂²E₀/∂Ω²` instead of the chain.
