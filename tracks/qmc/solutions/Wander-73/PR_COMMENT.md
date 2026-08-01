@ChanceSiyuan, here is our current progress on #73.

We first derived an exact finite-volume Ward identity for any
unitary-conjugacy orbit,

$$
F_{a\phi}=\partial_a\langle G\rangle.
$$

For the Kolodrubetz rotation this gives
$F_{s\phi}/V=(1/4)\partial_s m_X$ up to the orientation convention. It also
organizes the QGT into an infrared hierarchy:
$\omega^{-2}\rightarrow\omega^{-1}\rightarrow\omega^0$.

We then implemented and cross-checked four estimators with ED, including Ward,
spectral, Wilson-loop, and opposite-rate dynamic routes. The spectral and Ward
values agree to $8.9\times10^{-16}$ on the test sweep. A separate C++17
sign-free SSE-QMC implementation agrees with finite-temperature ED for seven
observables within $1.14$ combined standard errors.

The completed 272-task equilibrium production campaign at $\beta=4L$ gives
two headline results:

1. On $L=6,12,24$, the magnetic exponents are
   $3.0224(392)$, $1.9733(110)$, and $0.9597(213)$. Their adjacent gaps are
   $1.0491(319)$ and $1.0137(223)$, both compatible with the predicted $z=1$.
2. The thermal background-free quotient is
   $Q_F(6)=1.1485(900)$. It lies $0.22\sigma$ from the Ward weak-divergence
   reference $1.1288$ and $4.42\sigma$ from the earlier finite-cusp reference
   $0.7513$.

Our claim is deliberately limited: the fixed-triplet quotient passes its
preregistered discriminator, but flexible corrected-power fits are not yet
decisive. The next steps are larger $L$, higher-statistics aspect-ratio checks,
iPEPS finite-correlation-length scaling, and a thermodynamic finite-rate test.

The full public-safe derivation, numbers, audits, and limitations are in this
PR's progress report. We would especially welcome your feedback on the
unitary-orbit interpretation and on which iPEPS observable should be treated
as the primary Challenge #73 endpoint.
