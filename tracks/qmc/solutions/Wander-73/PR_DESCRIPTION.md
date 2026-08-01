## Team

| | |
|---|---|
| **Team name** | Wander (漫步者) |
| **Members** | Chenxi Wan, Yedi Shen, Junkai Wang |

## Challenge

| Row | Value |
|---|---|
| **Challenge** | Determine when the Berry curvature of the 2D TFIM is genuine second-moment quantum geometry and when it is constrained to an equilibrium response by a unitary-orbit Ward identity. |
| **Catalog issue** | Progress toward #73, proposed by @ChanceSiyuan; this PR does not close the issue. |
| **Track** | QMC, with ED validation and an iPEPS extension planned. |

## What this PR adds

- A public progress report deriving the exact finite-volume identity
  $F_{a\phi}=\partial_a\langle G\rangle$ for a unitary-conjugacy orbit.
- The infrared hierarchy
  $\omega^{-2}\rightarrow\omega^{-1}\rightarrow\omega^0$ for physical,
  mixed physical--orbit, and pure-orbit QGT components.
- ED validation of the spectral, Ward, Wilson-loop, and opposite-rate dynamic
  estimators.
- A sign-free SSE-QMC calculation comprising 272 completed production tasks
  at $\beta=4L$.
- Two numerical results: a magnetic exponent staircase compatible with
  adjacent spacing $z=1$, and a background-free thermal quotient that is
  $0.22\sigma$ from the Ward prediction and $4.42\sigma$ from the quoted
  finite-cusp reference.

## Headline results

| Test | Result | Interpretation |
|---|---:|---|
| magnetic exponent gaps | $1.0491(319)$ and $1.0137(223)$ | both compatible with $z=1$ |
| thermal quotient $Q_F(6)$ | $1.1485(900)$ | Ward reference: $1.1288$ |
| separation from cusp reference | $4.42\sigma$ | passes the preregistered discriminator |
| ED Ward agreement | $8.9\times10^{-16}$ max absolute error | convention and implementation check |

## Claim boundary

The strong numerical claim is the fixed, additive-background-free quotient on
$L=6,12,24$, not a precision asymptotic exponent. Flexible corrected-power
fits are not independently decisive. Higher-statistics $\beta/L=6$, larger
$L$, iPEPS finite-correlation-length scaling, and thermodynamic finite-rate
scaling remain to be completed.

This work is complementary to #191: it focuses on the exact orbit reduction
and the equilibrium critical-scaling audit.

## Checks

- Markdown whitespace and display-math delimiter checks pass.
- Public-content scan contains no credentials, account names, hostnames,
  scheduler identifiers, or private filesystem paths.
- Numerical values were cross-checked against the accepted jackknife analysis
  summary before publication.

Addresses #73 without closing it.
