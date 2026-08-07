# Issue #158: interim theorem and public-data audit

Date: 2026-07-29

## Executive conclusion

The audit now separates two questions that should not be conflated.

First, at the theorem/model level, the apparent loopholes can be closed.  For
the two-dimensional classical XY model with positive interaction

$$
J(R)=\frac{c_\infty}{|R|^4},
$$

the lattice dispersion satisfies

$$
E(k)
=
\frac{\pi c_\infty}{2}|k|^2\log\frac1{|k|}
+O(|k|^2).
$$

The resulting infrared integral diverges as $\log\log L$.  A direct
classical Bogoliubov argument excludes field-defined spontaneous
magnetization, while the recurrent-walk theorem of Ioffe, Shlosman and
Velenik excludes symmetry breaking in every infinite-volume Gibbs state.  A
separate block-averaging argument then proves that the actual zero-field
Monte Carlo observable also obeys

$$
\lim_{L\to\infty}\left\langle |M_L|^2\right\rangle=0.
$$

The normalized minimum-image torus interaction converges in $\ell^1$ to this
fixed infinite-volume interaction.  It therefore does not define a different
thermodynamic phase, although its lowest-momentum finite-size correction is
only relatively $O(1/\log L)$.

Second, at the data-analysis level, the currently public data do not support
the claim that a nonzero thermodynamic intercept has been established.  On
the registered window $L\ge64$, logarithmically decaying models fit the
published $M^2$ estimates much better than the corresponding inverse-log
ordered models.  Effective logarithmic exponents remain positive at the
largest available sizes.  However, source-matched model preference weakens
or changes sign when only the largest few sizes are retained.  Complete
synchronized bin means or jackknife replicas are unavailable, so a definitive
covariance-aware joint analysis cannot yet be performed.

The strongest defensible statement is therefore:

$$
\boxed{
\text{true finite-temperature LRO is excluded; the precise asymptotic
correlation law is not yet numerically established.}
}
$$

The candidate

$$
g(r)\sim[\log r]^{-p(T)}
$$

is consistent with the theorem and with several observed finite-size
signatures, but it remains a spin-wave/RG hypothesis rather than a theorem
proved in this audit.

## 1. Sources and reproducibility status

The audit uses:

- [Issue #158](https://github.com/QuantumBFS/quantum.harness/issues/158);
- [Bruno, Phys. Rev. Lett. 87, 137203 (2001)](https://doi.org/10.1103/PhysRevLett.87.137203);
- [Ioffe, Shlosman and Velenik, arXiv:math/0110127](https://arxiv.org/abs/math/0110127);
- [Yao et al., arXiv:2411.01811](https://arxiv.org/abs/2411.01811);
- [the public Zenodo record](https://zenodo.org/records/17206870);
- [the data request posted in Issue #158](https://github.com/QuantumBFS/quantum.harness/issues/158#issuecomment-5105643323).

The Zenodo table contains run-level estimates and marginal standard errors.
It does not contain the synchronized bin means, joint jackknife replicas, or
full cross-observable covariance needed to reconstruct the covariance of
$M^2$, $M^2_{k_{\min}}$, and derived residual quantities.

The extended analysis protocol was locked before the extended scripts were
run.  It is explicitly labeled *retrospectively locked*, rather than a true
prospective preregistration, because earlier exploratory fits had already
inspected the data.

## 2. The theorem-to-model chain

### 2.1 Exact normalization and marginal coefficient

For total coupling normalized to four,

$$
\sum_{R\ne0}J(R)=4,
$$

the square-lattice Epstein sum gives

$$
c_\infty
=
\frac{6}{\pi^2G}
=
0.6637008046138535\ldots,
$$

where $G$ is Catalan's constant.  Hence

$$
\rho_{\log}
=
\frac{\pi c_\infty}{2}
=
1.0425387859782584\ldots.
$$

Splitting the lattice sum at $|R|\asymp |k|^{-1}$ gives

$$
E(k)
=
\sum_{R\ne0}J(R)[1-\cos(k\cdot R)]
=
\rho_{\log}|k|^2\log\frac1{|k|}
+O(|k|^2).
$$

The logarithmic coefficient is positive.  Lattice anisotropy and
short-distance corrections enter only the nonlogarithmic $O(k^2)$ term.

### 2.2 Direct classical no-order proof

For the finite-volume Gibbs measure, introduce

$$
D_k
=
\sum_x e^{ik\cdot x}\frac{\partial}{\partial\theta_x},
\qquad
A_k
=
\sum_xe^{-ik\cdot x}\sin\theta_x.
$$

Periodic integration by parts and Cauchy--Schwarz give

$$
\left\langle|A_k|^2\right\rangle
\left\langle D_{-k}D_kH\right\rangle
\ge
T\left|\left\langle D_kA_k\right\rangle\right|^2.
$$

For positive ferromagnetic coupling,

$$
\left\langle D_kA_k\right\rangle=Nm_{L,h}
$$

and

$$
\left\langle D_{-k}D_kH\right\rangle
\le
N[h+E_L(k)].
$$

Parseval's identity then yields

$$
1
\ge
Tm_{L,h}^2
\frac1N\sum_k\frac1{h+E_L(k)}.
$$

After taking $L\to\infty$ at fixed $h>0$, followed by $h\downarrow0$,

$$
\int\frac{d^2k}{h+E(k)}
\longrightarrow\infty,
$$

and more specifically

$$
m_h^2
\lesssim
\frac1{T\log\log(1/h)}
\longrightarrow0.
$$

Thus the conclusion does not depend on applying Bruno's quantum commutator
proof to a classical rotor by analogy.

### 2.3 All Gibbs states and the measured $M^2$

With

$$
p(R)=J(R)/4,
$$

the associated random walk obeys

$$
1-\widehat p(k)=E(k)/4.
$$

Its recurrence integral diverges:

$$
\int_{\rm BZ}\frac{d^2k}{1-\widehat p(k)}
\asymp
\int_0^\epsilon\frac{dk}{k\log(1/k)}
=\infty.
$$

Theorem 2 of Ioffe--Shlosman--Velenik therefore makes every
infinite-volume Gibbs state $SO(2)$-invariant.

To connect that statement to the diagonal torus observable, fix a square
block $Q_R$ and define

$$
B_{R,x}
=
\frac1{|Q_R|}\sum_{u\in Q_R}S_{x+u}.
$$

Because the full magnetization is the average of all translated block
magnetizations,

$$
M_L=\frac1{L^2}\sum_xB_{R,x}.
$$

Jensen's inequality and torus translation invariance give

$$
\left\langle|M_L|^2\right\rangle_L
\le
\left\langle|B_{R,0}|^2\right\rangle_L.
$$

Take a local weak subsequential limit $\mu$ at fixed $R$.  Its
translation-ergodic components are Gibbs states, hence $SO(2)$-invariant and
have zero vector magnetization.  The mean ergodic theorem then gives

$$
\lim_{R\to\infty}
\left\langle|B_{R,0}|^2\right\rangle_\mu=0.
$$

Therefore

$$
\boxed{
\lim_{L\to\infty}
\left\langle|M_L|^2\right\rangle_L=0.
}
$$

This closes the possible escape route that Bruno's theorem concerns
$\langle M\rangle$ while the simulations measure $\langle|M|^2\rangle$.

### 2.4 Minimum-image convergence

Extend the minimum-image interaction by zero outside its representative
square:

$$
J_L^{\rm MI}(R)
=
c_L|R|^{-4}\mathbf 1_{R\in Q_L\setminus\{0\}}.
$$

The omitted tail is $O(L^{-2})$, implying

$$
c_L-c_\infty=O(L^{-2})
$$

and

$$
\sum_R
\left|J_L^{\rm MI}(R)-J(R)\right|
=O(L^{-2}).
$$

Consequently,

$$
\sup_k
\left|E_L^{\rm MI}(k)-E(k)\right|
=O(L^{-2}).
$$

At $k_{\min}=2\pi/L$, the leading kernel is
$O(L^{-2}\log L)$, so the relative convention effect may be

$$
O(1/\log L).
$$

This is large enough to matter for intercept fits but too small to define a
different thermodynamic model.

## 3. High-precision lattice-kernel check

An independent numerical evaluation used an exact one-dimensional reduction
of the infinite axial lattice sum and high-precision polylogarithms.

| Quantity | Result |
|---|---:|
| Analytic $\rho_{\log}$ | $1.0425387859782584$ |
| Fitted slope, largest six sizes | $1.0425387750974222$ |
| Relative difference | $-1.04\times10^{-8}$ |
| Last local slope, $L=65536$ | $1.0425387857852382$ |

For the normalized minimum-image kernel at $\sigma=2$ and $L=4096$,

$$
\frac{E_{\rm MI}-E_{\rm PI}}{E_{\rm PI}}
=
-0.0227643,
$$

while

$$
\log L\,
\frac{E_{\rm MI}-E_{\rm PI}}{E_{\rm PI}}
=
-0.18935.
$$

The normalization check also gives

$$
(c_L-c_\infty)L^2\longrightarrow1.13243\ldots.
$$

These calculations confirm the marginal kernel and the predicted slow
minimum-image finite-size correction; they do not reveal a theorem/model
mismatch.

## 4. Public-data audit

### 4.1 Data rule and registered models

For each $(\beta,L)$ in the $\sigma=2$ table, the primary row is the run with
the largest published sample count.  Additional equal-length $L=512$ runs
are reserved for run-to-run covariance checks rather than silently combined.

The locked scalar comparison used

$$
\ell=\log L
$$

and the equal-parameter-count models

$$
\mathrm{O2}:\quad
M^2=g_0+\frac{a_1}{\ell}+\frac{a_2}{\ell^2},
$$

$$
\mathrm{D2}:\quad
M^2=A\ell^{-p}+B\ell^{-p-1},
\qquad p>0.
$$

The main registered window was $L\ge64$, with window scans and largest-size
holdouts reported separately.

### 4.2 Scalar results at $L_{\min}=64$

| $\beta$ | $p$ from D2 | D2 $\chi^2/\mathrm{dof}$ | D2 GOF | O2 $\chi^2/\mathrm{dof}$ |
|---:|---:|---:|---:|---:|
| 1 | $0.31641$ | $2.987$ | $0.00146$ | $80.62$ |
| 2 | $0.10219$ | $1.203$ | $0.288$ | $77.51$ |
| 4 | $0.04418$ | $0.808$ | $0.595$ | $40.91$ |
| 8 | $0.02054$ | $0.435$ | $0.901$ | $33.82$ |

At this window, D2 is acceptable for $\beta=2,4,8$ and is still imperfect
for $\beta=1$.  O2 fails very strongly at every temperature.  The conclusion
is not merely that D2 has a smaller information criterion: the ordered O2
form is rejected by its residual structure at the published precision.

The final doubling-size effective logarithmic exponents,

$$
p_{\rm eff}(L_1,L_2)
=
-\frac{\log[M^2(L_2)/M^2(L_1)]}
        {\log[\log L_2/\log L_1]},
$$

are:

| $\beta$ | Largest doubling pair | $p_{\rm eff}$ |
|---:|---:|---:|
| 1 | $4096\to8192$ | $0.27291\pm0.00469$ |
| 2 | $4096\to8192$ | $0.09263\pm0.00153$ |
| 4 | $2048\to4096$ | $0.04170\pm0.00024$ |
| 8 | $2048\to4096$ | $0.01970\pm0.00014$ |

Within the available range these quantities remain positive and roughly
stable; they do not display a drift toward zero that would be expected from a
clean finite plateau.

### 4.3 Source-matched shifted-log comparison

A post-lock check of the paper source identified the ordered fit as

$$
\mathrm{OP}:\quad
M^2=g_0+\frac{a}{\log(L/L_0)}.
$$

It was compared with the equal-parameter-count decay form

$$
\mathrm{DP}:\quad
M^2=A[\log(L/L_0)]^{-p}.
$$

Define

$$
\Delta\mathrm{AICc}
=
\mathrm{AICc}_{\rm OP}-\mathrm{AICc}_{\rm DP},
$$

so positive values favor DP.

| $\beta$ | $\Delta\mathrm{AICc}$ at $L_{\min}=64$ | OP GOF | DP GOF | DP $p$ |
|---:|---:|---:|---:|---:|
| 1 | $37.47$ | $9.21\times10^{-9}$ | $0.0333$ | $0.33169$ |
| 2 | $37.66$ | $3.82\times10^{-7}$ | $0.401$ | $0.10371$ |
| 4 | $4.91$ | $0.161$ | $0.549$ | $0.04451$ |
| 8 | $12.94$ | $0.0371$ | $0.903$ | $0.02062$ |

This comparison favors decay on the $L\ge64$ window.  However, it becomes
weak or changes sign after retaining only the largest sizes.  For example:

| $\beta$ | $\Delta\mathrm{AICc}$ at $L_{\min}=192$ | at $256$ | at $384$ |
|---:|---:|---:|---:|
| 1 | $0.40$ | $0.30$ | $-0.98$ |
| 2 | $-0.15$ | $-0.43$ | $-0.07$ |
| 4 | $4.99$ | $1.88$ | $0.31$ |
| 8 | $0.92$ | $1.09$ | $0.70$ |

This is the main finite-size caution.  On the broader, reasonably populated
window, the decay model is preferred and often has much better GOF.  On the
largest-only windows, the number and logarithmic lever arm of data points are
too small to discriminate these flexible shifted-log forms.

The fitted OP intercept also drifts downward as $L_{\min}$ is increased.  For
example, the fitted $g_0$ changes from $0.2607$ to $0.2281$ at $\beta=1$ and
from $0.6320$ to $0.6119$ at $\beta=2$ over the available window scan.  A
positive finite-window intercept is therefore not itself a thermodynamic
lower bound.

### 4.4 Synthetic identifiability

Two thousand replicas were generated per temperature and per truth model on
$L\ge64$, using the published marginal errors.

For the exact O2 and D2 families used in the locked test:

- AICc selected the generating family in $100\%$ of replicas.
- Under D2 truth, a wrong O2 fit produced a positive, nominally significant
  $g_0$ in $100\%$ of replicas.
- Nevertheless, that wrong O2 model passed its chi-square GOF test in $0\%$
  of replicas and was selected by AICc in $0\%$ of replicas.

This corrects an overly broad preliminary intuition that the two hypotheses
must be statistically indistinguishable at the published precision.  For
these particular fixed correction families they are distinguishable.  The
remaining ambiguity comes from the choice of asymptotic corrections and the
shrinking number of points in large-$L_{\min}$ windows, not from Gaussian
measurement noise alone.

The exercise also makes a narrower but important point: a highly significant
positive intercept can be generated by fitting the wrong asymptotic family.
It must be accompanied by absolute GOF, window stability, and predictive
checks.

### 4.5 Joint covariance sensitivity

A sensitivity scan posited a constant within-size correlation

$$
\rho
=
\operatorname{Corr}(M^2,M^2_{k_{\min}})
\in[-0.8,0.8].
$$

Across this entire assumed range, the equal-parameter-count joint decay model
was favored over the joint ordered model.  The ranges of
$\Delta\mathrm{AICc}$ were:

| $\beta$ | Minimum | Maximum |
|---:|---:|---:|
| 1 | $647.5$ | $1973.6$ |
| 2 | $678.8$ | $1940.8$ |
| 4 | $320.8$ | $931.3$ |
| 8 | $267.7$ | $799.9$ |

These large differences reflect severe misspecification of the simple
ordered joint form.  They are not a replacement for a true covariance-aware
analysis.  At $\beta=1$, even the decaying joint form has poor absolute GOF,
showing that additional corrections are needed.

### 4.6 Residual-magnetization construction

The paper's residual observable

$$
M_r^2=M^2-bM^2_{k_{\min}}
$$

was reconstructed using the reported $b=149,175,152,154$ and
$\omega=0.4$, with $\rho$ scanned from $-0.8$ to $0.8$.

The result is not a uniform independent confirmation of order:

| $\beta$ | Range of $\Delta\mathrm{AICc}_{\rm ord-decay}$ | Interpretation |
|---:|---:|---|
| 1 | $62.28$ to $67.32$ | strongly favors decay |
| 2 | $-0.41$ to $-0.37$ | essentially tied |
| 4 | $2.51$ to $2.70$ | mildly favors decay |
| 8 | $-0.86$ to $-0.81$ | essentially tied |

The uncertainty in the data-selected coefficient $b$ cannot be propagated
from the released table.  Subtracting a lowest-mode contribution can flatten
the curve while leaving a leading factor such as $(\log L)^{-p}$ intact.
Consequently, a positive residual at every simulated size is not a positive
thermodynamic lower bound.

## 5. What is settled and what remains open

### Settled by the present audit

1. The $\sigma=2$ lattice kernel has the positive
   $k^2\log(1/k)$ term required by the infrared theorem.
2. The classical XY conclusion does not rely on a questionable
   quantum-to-classical limiting argument.
3. The normalized minimum-image interaction has the same infinite-volume
   Gibbs specification as the fixed $R^{-4}$ interaction.
4. No infinite-volume Gibbs state breaks $SO(2)$.
5. The zero-field diagonal torus quantity
   $\langle|M_L|^2\rangle$ must vanish.
6. A fitted positive intercept from the public finite-size data cannot be the
   true thermodynamic limit.

### Not settled by the present audit

1. Whether the low-temperature correlation has the exact asymptotic form

   $$
   g(r)\sim[\log r]^{-p(T)}.
   $$

2. The full covariance-aware joint likelihood for
   $M^2$, $M^2_{k_{\min}}$, $\xi/L$, and the residual construction.
3. The effect of the uncertainty and data-selection procedure used to choose
   the subtraction coefficient $b$.
4. Whether additional logarithmic corrections, vortex effects, or a long
   crossover produce the finite-size curvature seen especially at
   $\beta=1$.

## 6. Requested minimal data package

No per-sweep spin configurations are needed.  The minimum useful release is:

1. synchronized thermalized bin means for each $(\beta,L,\text{seed})$;
2. columns for $M^2$, every $M^2_{k_{\min}}$ component used, energy, and any
   quantity entering $\xi/L$ or the residual observable;
3. bin length, number of discarded sweeps, number of retained bins, seed,
   and run identifier;
4. alternatively, synchronized delete-one-bin jackknife replicas;
5. the precise estimator and selection procedure for $b$, including its
   uncertainty;
6. the mapping between these records and the rows in the Zenodo summary
   table.

This package is sufficient for covariance-aware joint fitting, bootstrap
model comparison, and reproduction of all derived uncertainties.

## 7. Recommended next decision

The next public response should avoid claiming that the public Monte Carlo
data alone have proved the full logarithmic-decay law.  The sharper and more
defensible response is:

> The theorem-to-model audit excludes a positive thermodynamic magnetization,
> including the zero-field torus $M^2$ observable.  Reanalysis of the public
> summary data favors logarithmic decay over the published ordered ansatz on
> reasonably populated fit windows, while the largest-only fits remain
> correction- and window-sensitive.  Synchronized binned data are required
> for the final covariance-aware numerical comparison.

That conclusion is stronger than “the theorem is probably correct,” but more
careful than claiming that the exact log-QLRO form has already been proved.
