# Challenge #73 progress report: Ward identities and critical scaling on Ising unitary orbits

## Team

| Field | Value |
|---|---|
| **Team name** | Wander (漫步者) |
| **Members** | Chenxi Wan, Yedi Shen, Junkai Wang |
| **Challenge** | Progress toward [#73](https://github.com/QuantumBFS/quantum.harness/issues/73) |
| **Track** | QMC, with ED validation and an iPEPS extension planned |

This is a public progress report, not a claim that Challenge #73 is complete.
It is complementary to [PR #191](https://github.com/QuantumBFS/quantum.harness/pull/191):
the emphasis here is an exact unitary-orbit reduction, an equilibrium
SSE-QMC scaling audit, and a controlled comparison between two competing
critical behaviors.

## Main analytical result

Consider a locally nondegenerate ground state of

$$
H(\lambda^a,\phi)
=
U(\phi)H(\lambda^a,0)U^\dagger(\phi),
\qquad
U(\phi)=e^{-i\phi G},
$$

where the Hermitian generator $G$ is independent of $\lambda^a$. Direct
differentiation gives

$$
\partial_\phi H=-i[G,H],
\qquad
A_\phi=\langle G\rangle,
\qquad
\boxed{F_{a\phi}=\partial_a\langle G\rangle}.
$$

The last equality is exact at finite volume. It identifies Berry curvature
with one leg tangent to an exact unitary-conjugacy orbit as a mixed equilibrium
response rather than an independent second inverse-frequency moment.

The corresponding quantum-geometric-tensor hierarchy is

| Component | Infrared kernel | Interpretation |
|---|---:|---|
| physical--physical | $\omega^{-2}$ | first imaginary-time moment |
| physical--orbit | $\omega^{-1}$ | mixed static response |
| orbit--orbit | $\omega^0$ | equal-time generator covariance |

Thus every exact orbit leg removes one adiabatic energy denominator. At a
quantum critical point it removes one factor of the correlation time
$\xi^z$ from the singular scaling.

## Application to the two-dimensional TFIM

For the Kolodrubetz rotation, using

$$
G_X=\frac14\sum_i X_i,
$$

the curvature density obeys, up to the orientation convention for $\phi$,

$$
\boxed{
\frac{F_{s\phi}}{V}
=
\frac14\,\partial_s m_X
}.
$$

Both the tuning operator and the connected part of $G_X$ project onto the
3D-Ising energy operator. Standard hyperscaling therefore predicts

$$
\frac{F_{s\phi}^{\mathrm{sing}}}{V}
\sim
\xi^{\alpha/\nu}
\sim
|s-s_c|^{-\alpha},
\qquad
\frac{\alpha}{\nu}=0.17474944\ldots,
$$

whereas the physical metric retains the additional infrared time scale,

$$
\frac{g_{ss}^{\mathrm{sing}}}{V}
\sim
\xi^{1+\alpha/\nu}
=
\xi^{1.17474944\ldots}.
$$

This predicts a weak divergence of the orbit curvature, rather than a finite
cusp. The numerical problem is difficult because the exponent is small and a
large analytic background is present.

For the laser-phase orbit,

$$
H(h,\phi)
=
-J\sum_{\langle ij\rangle}Z_iZ_j
-h\sum_iZ_i
-\Omega\sum_i(\cos\phi\,X_i+\sin\phi\,Y_i),
$$

with $G_Z=\frac12\sum_iZ_i$, the second Ward identity is

$$
\boxed{
\frac{F_{h\phi}}{V}
=
\frac12\,\chi_{ZZ}
}.
$$

The magnetic channel supplies a numerically cleaner calibration because all
three infrared moments diverge with well-separated powers.

## Computations completed

### 1. Exact diagonalization and estimator audit

On a $2\times2$ open square cluster:

- spectral curvature and the Ward derivative agree to a maximum absolute
  error of $8.9\times10^{-16}$ over the tested parameter sweep;
- centered Wilson plaquettes show the expected second-order convergence;
- an opposite-velocity real-time protocol extrapolates to
  $F_{s\phi}=0.58944799$, compared with the spectral value $0.58945615$.

These checks fix signs, normalizations, overlap phases, and the dynamic
response convention. They do not by themselves test thermodynamic critical
scaling.

### 2. Independent SSE-QMC implementation and ED cross-check

We implemented a dependency-free C++17 sign-free stochastic-series-expansion
sampler with diagonal and quantum-cluster updates. The analysis uses blocked
delete-one jackknife estimates and records the imaginary-time primitives
needed for the static responses and quantum metrics.

On the same $2\times2$ open cluster, seven independent observables agree with
finite-temperature ED within a maximum of $1.14$ combined standard errors.
The cross-check includes the energy, transverse magnetization, both Ward
curvatures, two physical quantum metrics, and the pure-orbit metric.

### 3. Production scaling campaign

The production campaign contains 272 independent SSE-QMC tasks at
$\beta=4L$. All tasks completed and passed the manifest coverage check. The
primary uncertainty analysis merges four consecutive compact blocks, treats
different sizes as independent, and retains same-size cross-observable
covariance.

No account names, login details, hostnames, or private infrastructure paths are
included in this public report.

## Result A: magnetic infrared-moment staircase

The background-free $L=6,12,24$ estimates are

| Quantity | Measured exponent | 3D-Ising prediction |
|---|---:|---:|
| $g_{hh}/V$ | $3.0224\pm0.0392$ | $2.963702388$ |
| $F_{h\phi}/V$ | $1.9733\pm0.0110$ | $1.963702388$ |
| $g_{\phi\phi}/V$ | $0.9597\pm0.0213$ | $0.963702388$ |

The adjacent exponent gaps are

$$
\Delta\kappa_1=1.0491\pm0.0319,
\qquad
\Delta\kappa_2=1.0137\pm0.0223.
$$

Both are compatible within two standard deviations with the predicted
dynamical spacing $z=1$. This is the cleanest numerical realization in the
current work of the hierarchy

$$
\omega^{-2}\longrightarrow\omega^{-1}\longrightarrow\omega^0.
$$

## Result B: background-free thermal discriminator

The thermal Ward-curvature densities are

| $L$ | $F_{s\phi}/V$ |
|---:|---:|
| 6 | $0.235970\pm0.001555$ |
| 12 | $0.309877\pm0.002311$ |
| 24 | $0.394755\pm0.004041$ |

The additive-background-free quotient is

$$
Q_F(6)
=
\frac{\bar F(24)-\bar F(12)}
{\bar F(12)-\bar F(6)}
=
1.1485\pm0.0900.
$$

For this fixed size triplet:

- Ward weak-divergence prediction:
  $2^{\alpha/\nu}=1.128768$;
- earlier finite-cusp reference:
  $2^{-0.41262528}=0.751255$;
- measured distance from Ward reference: $0.22\sigma$;
- measured separation from finite-cusp reference: $4.42\sigma$.

The preregistered thermal discriminator therefore passes. This is evidence
for the Ward weak-divergence scenario on the specified triplet, not yet a
precision determination of the asymptotic exponent.

## Robustness and claim boundary

- Reblocking from one to two and from two to four compact blocks increases the
  largest reported error by factors $1.071$ and $1.063$, respectively.
- Auxiliary $\beta/L=6$ checks differ from the primary $\beta/L=4$ values by
  at most $2.056\sigma$, with no monotonic drift in $\beta$.
- Flexible seven-size corrected-power fits are not independently decisive.
  The full-size AICc favors the Ward form by $1.78$, whereas deleting $L=6$
  favors the cusp form by $0.92$.

Accordingly, the present strong claims are limited to:

1. the exact finite-volume Ward identity and denominator descent;
2. the magnetic exponent staircase and its $z=1$ spacing;
3. the fixed, background-cancelling thermal quotient and its rejection of the
   quoted finite-cusp reference on $L=6,12,24$.

We do **not** yet claim a precision asymptotic thermal exponent, a completed
iPEPS finite-correlation-length scaling analysis, or a thermodynamic
finite-rate result.

## Remaining work for Challenge #73

1. extend the equilibrium campaign to $L=32,48$ and improve the
   $\beta/L=6$ statistics;
2. vary the critical-field estimate and the size triplet to test quotient
   stability;
3. compute the physical metric and Ward curvature with converged iPEPS and
   organize the results by the measured correlation length $\xi_D$;
4. compare the Ward estimator with a mixed-overlap Wilson plaquette in iPEPS;
5. extend the finite-rate ED check to a controlled finite-size or tensor-network
   scaling study;
6. treat the ordered phase with a ground-space Wilson loop rather than a
   scalar Berry phase when the orbit exchanges broken-symmetry sectors.

## References

- M. Kolodrubetz, *Measuring Berry curvature with quantum Monte Carlo*,
  [Phys. Rev. B 89, 045107 (2014)](https://doi.org/10.1103/PhysRevB.89.045107),
  [arXiv:1310.2644](https://arxiv.org/abs/1310.2644).
- M. Kolodrubetz, D. Sels, P. Mehta, and A. Polkovnikov,
  *Geometry and non-adiabatic response in quantum and classical systems*,
  [Physics Reports 697, 1 (2017)](https://doi.org/10.1016/j.physrep.2017.07.001),
  [arXiv:1602.01062](https://arxiv.org/abs/1602.01062).
- A. F. Albuquerque *et al.*, *Quantum critical scaling of fidelity
  susceptibility*,
  [Phys. Rev. B 81, 064418 (2010)](https://doi.org/10.1103/PhysRevB.81.064418),
  [arXiv:0912.2689](https://arxiv.org/abs/0912.2689).

Addresses #73 without closing it.
