# Benchmark Numbers

Reference ground-state values for canonical QMB problems. Skills cite this card to compare a calculation against authoritative numbers — only when one exists. For most concrete problems users bring (specific finite sizes, non-canonical parameters), no published benchmark exists; in that case verification falls to limits and internal consistency.

Convention: All values use the harness `S`-operator convention from `conventions.md`. Pauli-σ values differ by a factor of 4 per bilinear.

## 1D Heisenberg chain (S=1/2, NN, J > 0)

| Quantity | Value | Source |
|---|---|---|
| `E/N` (thermodynamic limit) | `-ln 2 + 1/4 ≈ -0.443147` | Bethe ansatz; Hulthén (1938). |
| Spin gap | 0 (gapless) | Bethe ansatz. |
| Two-spinon dispersion | `ω(q) = (π/2) J |sin q|` | des Cloizeaux–Pearson (1962). |

For finite N with OBC, `E/N` converges to the thermodynamic value with corrections `~ 1/N²`. ED comparison: N=20 OBC `E ≈ -8.6826` (`E/N ≈ -0.4341`).

## 2D Heisenberg square lattice (S=1/2, NN, J > 0)

| Quantity | Value | Source |
|---|---|---|
| `E/N` (thermodynamic limit) | `-0.66944(2)` | QMC, Sandvik (1997). |
| Staggered moment `m†` | `0.3070(3)` | QMC, Sandvik (1997). |
| Spin-wave velocity `c` | `1.657(2)` | QMC, various. |

## 2D Heisenberg triangular lattice (S=1/2, NN, J > 0)

| Quantity | Value | Source / status |
|---|---|---|
| `E/N` (thermodynamic limit) | `-0.5445(4)` | DMRG cylinders, Capponi et al. (varies by extrapolation method). |
| Staggered moment | `~ 0.205` | Coplanar 120° order; DMRG / VMC. |

Less tightly constrained than the square lattice; report as a range.

## 2D J1-J2 square lattice (S=1/2, J1=1, J2 variable)

| Region | `E/N` (typical) | Status |
|---|---|---|
| `J2/J1 ∈ [0, 0.4]` | Néel order | Continuous from J2=0 case. |
| `J2/J1 ∈ [0.45, 0.55]` | Disputed (gapless QSL? VBS? Z2 QSL?) | Active research; do not claim a single value. |
| `J2/J1 ∈ [0.6, 1.0]` | Stripe AFM | Order parameter changes character. |

For verification at any specific (`L`, `J2/J1`), report the converged value and bond-dim trend rather than claiming a benchmark match.

## 2D Heisenberg kagome lattice (S=1/2, NN, J > 0)

| Quantity | Value | Source / status |
|---|---|---|
| `E/N` (thermodynamic limit) | `-0.4386(5)` to `-0.4395(5)` | DMRG cylinders, Yan-Huse-White (2011); Depenbrock et al. (2012). |
| Ground-state nature | Spin liquid (gapped Z2 favored) | Disputed: gapless vs gapped; active research. |

Treat as a range. A spin-liquid-versus-VBS distinction is not closed.

## 1D Hubbard chain (half-filled, S=1/2 fermions)

| Quantity | Value | Source |
|---|---|---|
| `E/N` at `U/t = 0` | `-4/π ≈ -1.27324` | Free fermions, half-filled. |
| `E/N` (general U) | Lieb-Wu integral equations | Lieb & Wu (1968); evaluated numerically. |
| Charge gap | `Δ_c > 0` for `U > 0` | Mott insulator at any U > 0 in 1D. |
| Spin sector | Gapless (Heisenberg-like at large U) | |

For U/t = 4: `E/N ≈ -0.5727`. For U/t = 8: `E/N ≈ -0.3275`. (Lieb-Wu numerical evaluation.)

## 2D Hubbard square lattice

Highly contested at intermediate `U/t` and finite doping. Recent benchmarks (e.g., simons-collaboration 2017, 2020) report consensus only at half-filling and weak doping for select parameters. Do not cite a single benchmark; consult the multi-method literature for the specific (`U/t`, doping, lattice size) requested.

At half-filling, `U → ∞` limit: maps to 2D Heisenberg with `J = 4t²/U`, hence `E/N → -0.66944 × J / t = -2.6778 t² / U`.

## Anderson impurity

| Quantity | Value | Source |
|---|---|---|
| Symmetric Anderson Kondo scale | `T_K ~ 0.41 √(U Γ / 2) exp(-π U / 8 Γ)` | Haldane (1978), particle-hole symmetric case. |
| Wilson ratio | 2 (universal) | Numerical RG. |

## How to use this file

- Cite as `knowledge-base/benchmark-numbers.md#<lattice>-<model>` from skills' Verification sections.
- If your problem isn't here, **don't fabricate a benchmark**. Report the converged value with the limit/symmetry checks satisfied, and note that no authoritative benchmark was used.
- For frontier or contested problems, report the literature *range* and the residual uncertainty.
