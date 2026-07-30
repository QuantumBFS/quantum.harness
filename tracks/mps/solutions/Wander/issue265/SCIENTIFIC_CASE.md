# Scientific Case: What Did the Machine-Discovered Burgers Equation Actually Discover?

## Executive answer

The machine-discovered equation

\[
\partial_t U+aU\partial_xU=D_{\rm cl}\partial_x^2U
\tag{1}
\]

is a remarkably accurate description of the public weak-domain-wall
trajectory of the infinite-temperature isotropic Heisenberg chain over the
available hydrodynamic window.  Our reproducible audit finds
\(a\simeq0.230\), \(D_{\rm cl}\simeq1.97\), and an integrated profile error of
about \(0.167\%\).  This is a substantive discovery: a two-parameter
deterministic PDE compresses a difficult quantum many-body trajectory with
high predictive accuracy.

The same evidence does not, by itself, identify Eq. (1) as an exact,
autonomous, asymptotic equation for physical magnetization.  Four additional
questions must be answered:

1. **Field identity:** is \(U\) the physical magnetization field, a normalized
   response profile, or a chiral normal mode?
2. **Closure:** can its current be expressed locally in terms of that single
   field, or have other hydrodynamic modes and memory been integrated out?
3. **Transfer:** do the same coefficients predict unseen amplitudes,
   orientations, shapes, backgrounds, and future times?
4. **Fluctuations:** does a deterministic mean-profile equation also account
   for current correlations and full counting statistics?

The exact symmetry and averaging analysis already gives a constructive
answer to the first two questions.  At zero magnetic field, a universal local
current for physical magnetization must be odd under spin flip, whereas the
quadratic Burgers current is even.  In a stochastic or open-system
description, averaging a nonlinear current retains a covariance contribution;
zero-mean noise does not turn a fluctuating two-mode theory into Eq. (1).
Consequently, a scalar Burgers equation can be an excellent
trajectory-conditioned closure without being the complete microscopic
hydrodynamic law.

The public trajectory supplies a particularly sharp positive mechanism for
why the fit is so good.  A moment identity maps the fitted Burgers law to the
measured wall width.  In the available window,

\[
A_W=0.741842,
\qquad
\frac{A_B}{A_W}=0.999154,
\tag{2}
\]

so the scalar Burgers constitutive curve is almost exactly tangent to the
observed scale-dependent moment diffusivity.  The fit is therefore not a
numerical coincidence: it is the local tangent representation of the
hydrodynamic broadening seen by this trajectory.

The remaining universality question is now a registered prediction problem,
not a debate over one fit.  The package freezes a convergence ladder, a
\(50\!:\!150\) training interval, a \(150\!:\!200\) validation interval, a
blinded \(200\!:\!400\) confirmation interval, a broad initial-condition
matrix, current/correlation/FCS observations, and a nested competition among
scalar, independent two-Burgers, coupled two-mode, and memory/more-mode
descriptions.  The public pilot establishes the finite-window benchmark; the
tensor-network production program determines how that benchmark extends
across conditions and times.

## 1. The original discovery and the sharper research question

[Kharkov et al.](https://arxiv.org/abs/2111.02385) introduced a sparse,
interpretable machine-learning framework for discovering hydrodynamic
equations from limited quantum data.  For the \(\Delta=1\) spin-\(1/2\)
Heisenberg chain, the input was high-temperature weak-domain-wall tDMRG data
associated with the KPZ study of
[Ljubotina, Žnidarič, and Prosen](https://arxiv.org/abs/1903.01329).  For the
normalized profile

\[
U(t,x)=\frac{\langle S^z(t,x)\rangle}{\mu},
\tag{3}
\]

the search selected Eq. (1), with reported coefficients near
\(a\approx0.24\) and \(D_{\rm cl}\approx1.90\).

This discovery contains two logically separate achievements:

- **compression and interpolation:** a compact PDE reproduces the observed
  trajectory in the measured window;
- **hydrodynamic identification:** the same PDE, field, and coefficients form
  a transferable asymptotic law derived from the quantum chain.

The first achievement can be established on one high-quality trajectory.  The
second requires field identification, exact-symmetry compatibility,
cross-condition prediction, numerical convergence, and future-time
confirmation.  Issue
[#265](https://github.com/QuantumBFS/quantum.harness/issues/265) asks precisely
for this second level: explain the microscopic origin and assumptions behind
the scalar closure, or determine the regime in which the learned equation is
an effective finite-window law.

The question matters beyond this one model.  Machine discovery can identify a
low-dimensional equation even when the observed trajectory lies on a narrow
manifold of a higher-dimensional theory.  A successful hydrodynamic discovery
therefore needs both **predictive fit quality** and **closure certification**.
This PR turns that principle into an executable quantum-many-body benchmark.

## 2. Evidence levels used in this submission

To avoid moving between unlike claims, the research program uses four evidence
levels.

| Level | Meaning | Examples in this project |
|---|---|---|
| **Exact** | Follows from the Hamiltonian, a symmetry, or algebra | lattice continuity; spin-flip parity of the current; normal-mode diagonalization on the equal-coupling manifold |
| **Controlled** | Follows after an explicit expansion or stated closure | weak-wall linear response; two-mode reduction of a larger GHD hierarchy; finite-window tangent construction |
| **Empirical** | Measured on a specified dataset and window | fitted \(a,D_{\rm cl}\); profile error; width exponent; \(A_B/A_W\) |
| **Registered prediction** | Decided by held-out, converged data under frozen rules | coefficient transfer; two-mode improvement; FCS agreement; blinded future-time confirmation |

The core result becomes clearer under this separation.  The public-trajectory
Burgers fit is strong empirical evidence for a finite-window closure.  Exact
symmetry identifies what that closure cannot mean if \(U\) is interpreted as
the sole physical magnetization field.  The registered program then tests the
remaining scalar, chiral, two-mode, and memory interpretations on equal terms.

## 3. What the microscopic chain gives exactly

At the isotropic point, write the nearest-neighbour Hamiltonian as

\[
H=J\sum_j \mathbf S_j\cdot\mathbf S_{j+1}.
\tag{4}
\]

The Heisenberg equation gives the exact lattice continuity relation

\[
\frac{dS_j^z}{dt}=j_{j-1}^z-j_j^z,
\qquad
j_j^z=J\left(S_j^xS_{j+1}^y-S_j^yS_{j+1}^x\right).
\tag{5}
\]

After coarse graining this guarantees

\[
\partial_t m+\partial_x j_m=0.
\tag{6}
\]

It does not yet provide an autonomous constitutive relation
\(j_m=j_m[m]\).  The time evolution of the current generates additional
operators and correlations.  Generalized hydrodynamics similarly begins with
an extensive quasiparticle hierarchy.  A one-field PDE is obtained only after
those additional variables are closed, projected, or integrated out.  The
central research task is therefore to characterize that closure rather than
to infer exactness from conservation alone.

## 4. The field-identification gate

At zero magnetic field the equilibrium state and Hamiltonian are invariant
under global spin flip.  Physical magnetization and its current transform as

\[
m\mapsto-m,
\qquad
j_m\mapsto-j_m.
\tag{7}
\]

A local Euler current depending only on physical magnetization must therefore
obey

\[
j_m(-m)=-j_m(m),
\tag{8}
\]

and its analytic expansion near \(m=0\) has the form

\[
j_m(m)=c_1m+c_3m^3+\cdots.
\tag{9}
\]

The scalar Burgers flux is

\[
j_B(m)=\frac{a}{2}m^2,
\tag{10}
\]

which is even.  A fixed nonzero \(a\) can therefore describe physical
magnetization only after an additional piece of field information has been
identified.  Constructive possibilities include:

- a chiral normal mode rather than \(m\) itself;
- a spin-flip-odd orientation or sector label carried by the coefficient;
- expansion about a nonzero magnetic background;
- explicit spin-flip breaking in the preparation or dynamics.

This does not diminish the fit.  It tells us what the fitted coefficient
contains.  On a single oriented wall, the orientation is fixed and can be
silently encoded in \(a\).  A universal material coefficient cannot hide that
information.  This is why the confirmatory matrix includes both wall
orientations, four amplitudes, and nonzero backgrounds.

A useful conditional mapping follows from a single-chiral projection.  If
\(u_{-\sigma}=0\), \(\phi=\sigma m\), and
\(u_\sigma=2m\), then for \(U=m/\mu\)

\[
\partial_tU+2\sigma g\mu\,U\partial_xU
=D\partial_x^2U,
\qquad
a_i=2\sigma_i g\mu_i.
\tag{11}
\]

Equation (11) is a testable interpretation, not an identity assumed after the
fact.  `sector_amplitude_law` is therefore a frozen scalar competitor beside
one shared coefficient pair and independent condition-specific pairs.

## 5. Why an open fluctuating theory does not average to the deterministic PDE

The long-wavelength Heisenberg problem is also described using nonlinear
fluctuating hydrodynamics.  For one stochastic Burgers mode,

\[
\partial_tu+\frac{\sigma g}{2}\partial_xu^2
=D\partial_x^2u+\partial_x\eta,
\tag{12}
\]

averaging gives

\[
\partial_t\bar u+
\frac{\sigma g}{2}\partial_x\langle u^2\rangle
=D\partial_x^2\bar u.
\tag{13}
\]

Because

\[
\langle u^2\rangle=\bar u^2+\operatorname{Var}(u),
\tag{14}
\]

the mean equation contains the fluctuation current

\[
-\frac{\sigma g}{2}\partial_x\operatorname{Var}(u).
\tag{15}
\]

Thus \(\langle\eta\rangle=0\) removes the explicit mean noise but not the
nonlinear effect of fluctuations.  The deterministic learned equation can be
the result of a data-dependent closure of Eq. (15), but it is not obtained by
simply deleting zero-mean noise.

The two-field formulation makes the same point directly.  A symmetry-complete
candidate is

\[
\begin{aligned}
\partial_t m+\partial_x\!\left[
m\phi-D_m\partial_xm-\sqrt{2D_m\chi}\,\xi_m
\right]&=0,\\
\partial_t \phi+\partial_x\!\left[
\frac{\lambda_m}{2}m^2+
\frac{\lambda_\phi}{2}\phi^2-
D_\phi\partial_x\phi-
\sqrt{2D_\phi\chi}\,\xi_\phi
\right]&=0.
\end{aligned}
\tag{16}
\]

For the physical mean magnetization,

\[
\partial_t\langle m\rangle+
\partial_x\langle m\phi\rangle
=D_m\partial_x^2\langle m\rangle.
\tag{17}
\]

The hidden field and its covariance are precisely the information a one-field
closure must represent.

[De Nardis, Gopalakrishnan, and Vasseur](https://arxiv.org/abs/2212.03696)
proposed this two-mode nonlinear fluctuating hydrodynamic structure for
isotropic spin chains.  On the equal-coupling manifold,

\[
j_m=g m\phi,
\qquad
j_\phi=\frac{g}{2}(m^2+\phi^2),
\tag{18}
\]

the fields

\[
u_+=m+\phi,
\qquad
u_-=m-\phi
\tag{19}
\]

algebraically diagonalize the quadratic flux:

\[
j_m+j_\phi=\frac{g}{2}u_+^2,
\qquad
j_m-j_\phi=-\frac{g}{2}u_-^2.
\tag{20}
\]

The chiral fields \(u_\pm\), rather than physical \(m\) alone, are therefore
natural Burgers candidates.  The algebra in Eq. (20) is exact once the
two-field current is assumed; whether the microscopic hierarchy reaches this
two-mode manifold at accessible times is a quantitative question for
profiles, currents, responses, and FCS.

## 6. Why low-order KPZ signatures and full statistics must both be tested

The isotropic chain exhibits robust superdiffusive and KPZ-like low-order
features.  The original numerical work found KPZ scaling of the spin
structure factor, and later studies have strengthened several parameter-free
two-point relations.  In particular,
[Takeuchi et al.](https://arxiv.org/abs/2406.07150) describe the evidence as a
partial, definite emergence of KPZ structure.

Higher-order transfer statistics add independent information.  Spin flip
requires the equilibrium magnetization-transfer distribution to be even,

\[
P(\mathcal M)=P(-\mathcal M),
\qquad
\kappa_{2n+1}(\mathcal M)=0.
\tag{21}
\]

Two independent opposite-chirality Baik--Rains modes provide one mechanism
for this cancellation, but they also predict a definite even-cumulant
structure.  If their individual excess kurtosis is approximately \(0.29\),
the equally weighted two-mode sum gives approximately \(0.145\).

The 46-qubit Floquet experiment of
[Rosenberg et al.](https://arxiv.org/abs/2306.09333) reported late-time excess
kurtosis \(-0.05\pm0.02\), while the quantum generating-function calculations
of [Valli et al.](https://arxiv.org/abs/2409.14442) extended cumulant access to
later times and likewise highlighted the information carried by full counting
statistics.  These systems and protocols are not the same trajectory as the
continuous-time domain wall used by Kharkov et al.; they therefore motivate a
joint universality test rather than replace the public-profile result.

This is why the registered two-mode comparison requires one parameter set to
predict:

- mean magnetization profiles;
- local spin-current profiles;
- connected \(C^{zz}\) data;
- positive and negative pulse responses;
- the complex transfer characteristic function \(\log Z(\gamma,t)\);
- cumulants \(\kappa_1,\ldots,\kappa_4\).

A model that organizes all of these observables is scientifically stronger
than one selected from a profile alone.

## 7. The moment bridge: why constant Burgers works in the measured window

For a rising wall with plateaus \(\pm U_0\), define a normalized wall density
and width by

\[
p(x,t)=\frac{\partial_xU}{2U_0},
\qquad
W^2=\int (x-\bar x)^2p(x,t)\,dx.
\tag{22}
\]

The associated moment diffusivity is

\[
D_{\rm moment}=\frac{1}{2}\frac{dW^2}{dt}.
\tag{23}
\]

Equation (1) implies the exact profile-level identity

\[
D_{\rm moment}
=D_{\rm cl}+
\frac{a}{4U_0}\int\!\left(U_0^2-U^2\right)dx.
\tag{24}
\]

Introduce the dimensionless shape factor and effective width velocity

\[
c_f=
\frac{\int(U_0^2-U^2)dx}{U_0^2W},
\qquad
v=\frac{aU_0c_f}{4}.
\tag{25}
\]

Then

\[
D_{\rm moment}=D_{\rm cl}+vW,
\qquad
\dot W=\frac{D_{\rm cl}}{W}+v.
\tag{26}
\]

The registered microscopic moment law is

\[
D_{\rm moment}(W)=A_\infty\sqrt W,
\qquad
A_\infty=\frac{20\pi}{81}=0.775701894\ldots,
\tag{27}
\]

equivalently

\[
W(t)=1.106260504\ldots\,t^{2/3},
\qquad
D_{\rm moment}(t)=0.815874868\ldots\,t^{1/3},
\tag{28}
\]

up to finite-time corrections.

The two constitutive curves are compared through

\[
A_W=\frac{2}{3}\frac{dW^{3/2}}{dt},
\qquad
A_B=2\sqrt{D_{\rm cl}v}.
\tag{29}
\]

At a tangency width \(W_*\),

\[
D_{\rm cl}=vW_*;
\qquad
A_B=A_W.
\tag{30}
\]

The public-trajectory values in Eq. (2) satisfy this tangency relation to
about \(0.085\%\).  In addition, \(A_W/A_\infty\simeq0.95635\): the observed
window is close to, but numerically below, the registered asymptotic amplitude.
This gives a precise interpretation of the learned constants.  Over a finite
range of \(W\), a line \(D_{\rm cl}+vW\) can be nearly tangent to the curved
law \(A\sqrt W\).  Rolling fits should then flow as

\[
a(t_*)\sim t_*^{-1/3},
\qquad
D_{\rm cl}(t_*)\sim t_*^{1/3},
\tag{31}
\]

while maintaining the local tangent amplitude.

This mechanism makes a direct, testable prediction: the scalar coefficients
are locally meaningful, but their values should track the observation window
if the underlying moment law is scale dependent.

## 8. What the public trajectory establishes quantitatively

The Route-B2 audit uses the public
`yourball/pde-many-body/domain_wall_xxz/data/highT_delta=1.npy` trajectory,
converts it to the common dataset format, and applies weak- and strong-form
fits, rolling-window estimates, forward prediction, moment analysis, and
deterministic continuation.

The principal numerical anchors are:

| Quantity | Public-trajectory result | Interpretation |
|---|---:|---|
| Burgers nonlinearity | \(a\simeq0.230\) | close to the published \(\sim0.24\) value |
| Classical viscosity | \(D_{\rm cl}\simeq1.97\) | close to the published \(\sim1.90\) value |
| Integrated profile error | \(0.167\%\) | high-accuracy finite-window compression |
| Width exponent, \(t=80\ldots190\) | \(0.6802\) | close to \(2/3\) in the measured window |
| Moment-diffusivity exponent | \(0.3372\) | close to \(1/3\) in the measured window |
| Moment amplitude | \(A_W=0.741842\) | measured broadening amplitude |
| Tangent ratio | \(A_B/A_W=0.999154\) | quantitative finite-window tangent mechanism |

The same deterministic scalar equation can be evolved beyond the quantum
data.  For the rising-wall orientation it approaches the viscous Burgers
rarefaction solution,

\[
U(x,t)=
\begin{cases}
U_L, & x/t<aU_L,\\
x/(at), & aU_L<x/t<aU_R,\\
U_R, & x/t>aU_R,
\end{cases}
\tag{32}
\]

whose width grows as \(W\sim t\).  The local continuation exponent rises from
about \(0.665\) near \(t\simeq200\) to about \(0.851\) by \(t=5000\), moving
toward ballistic rarefaction rather than remaining at \(2/3\).  This is an
internal property of the learned deterministic PDE.  The later
\(x/t^{2/3}\) appearance obtained by evolving that PDE is therefore not an
independent long-time measurement of the quantum chain.

The positive conclusion is specific and strong: Eq. (1) is an accurate local
closure of the observed weak-wall response.  The asymptotic conclusion must
come from new quantum-chain data rather than from extrapolating the fitted PDE
outside its training support.

## 9. Synthetic controls validate the inference machinery

Before interpreting coefficient flow in quantum data, the pipeline was tested
on two datasets with known dynamics.

### 9.1 Constant-coefficient control

For a Cole--Hopf Burgers trajectory with ground truth
\(a=0.24\), \(D=1.9\), the global weak fit recovers

\[
a=0.239529,
\qquad
D=1.898051.
\tag{33}
\]

The instantaneous practical drift is small:

\[
\text{relative range}=0.052\%,
\qquad
\text{relative standard deviation}=0.015\%.
\tag{34}
\]

### 9.2 Scale-dependent control

For a generated trajectory with
\(D(t)\propto t^{1/3}\), the instantaneous estimator recovers

\[
\gamma=0.332998\pm1.67\times10^{-5},
\tag{35}
\]

with a \(29.446\%\) relative range and \(8.533\%\) relative standard
deviation.

These controls demonstrate the practical distinction needed by Issue #265:
the analysis can preserve an effectively constant coefficient and can recover
a KPZ-like \(1/3\) drift when it is present.  Formal information criteria are
reported in the generated summaries, but the research decision also requires
practical effect size, synthetic calibration, and converged quantum data.

## 10. The preregistered confirmatory experiment

### 10.1 Frozen time split and blindness

The data are partitioned before production:

\[
\text{training}: 50\le t\le150,
\tag{36}
\]

\[
\text{validation}: 150<t\le200,
\tag{37}
\]

\[
\text{blinded confirmation}: 200<t\le400.
\tag{38}
\]

The frozen JSON files record the three endpoint pairs as `[50,150]`,
`[150,200]`, and `[200,400]`.  The executable observation masks assign the
shared `t=150` and `t=200` slices to the earlier stage, as written in
Eqs. (36)--(38), preventing double use of either boundary.

The confirmation interval cannot select preprocessing, model class,
parameter bounds, or thresholds.  It can be opened once, through an explicit
human `--confirm-unblind` action, after convergence, Production A, and frozen
model selection have produced an eligible forecast.  Seeds, evidence hashes,
the selected model, and the unblinding action are recorded.

### 10.2 Physical-condition matrix

The registered matrix changes the information content of the experiment.  It
contains:

- wall amplitudes \(\mu=0.02,0.05,0.10,0.20\), with both orientations;
- tanh widths \(1,2,4,8\);
- erf walls, a double wall, positive and negative Gaussian pulses, and two
  sinusoidal wavelengths;
- backgrounds \(m_0=+0.05\) and \(-0.05\);
- equilibrium and positive/negative local-pulse response conditions;
- environment controls at \(\Delta=0.8\), \(\Delta=1.2\), and
  \(\Delta=1,J_2=0.1\).

The \(J_2\) convention is frozen as

\[
H=-J\sum_i\left(
S_i^xS_{i+1}^x+S_i^yS_{i+1}^y+\Delta S_i^zS_{i+1}^z
\right)
-J_2\sum_i\mathbf S_i\cdot\mathbf S_{i+2}.
\tag{39}
\]

Environment controls contextualize specificity to the isotropic integrable
point; they do not enter the restricted \(\Delta=1\) universality verdict.

### 10.3 Numerical convergence gate

Four representative conditions are evaluated on a nested ladder:

| Level | \(L\) | \(\Delta t\) | \(\chi_{\max}\) | cutoff |
|---|---:|---:|---:|---:|
| coarse | 256 | 0.05 | 256 | \(10^{-8}\) |
| medium | 384 | 0.025 | 512 | \(10^{-10}\) |
| fine | 512 | 0.0125 | 1024 | \(10^{-11}\) |

A condition advances when

\[
\frac{\|U_{\rm fine}-U_{\rm medium}\|_2}
{\|U_{\rm fine}\|_2}<0.002
\tag{40}
\]

and

\[
\max_t
\frac{|W_{\rm fine}-W_{\rm medium}|}{W_{\rm fine}}<0.003.
\tag{41}
\]

This gate is deliberately prior to model comparison.  Numerical resolution
therefore cannot be converted into an apparent scientific preference.

### 10.4 Nested model hierarchy

The analysis compares models on the same train/validation folds and observable
normalization:

1. **Gaussian diffusion:** one shared \(D_m\), no nonlinear or latent field.
2. **Shared scalar:** one pair \((a,D_{\rm cl})\) across primary conditions.
3. **Condition-specific scalar:** separate \((a_i,D_i)\) pairs.
4. **Sector/amplitude scalar:** \(a_i=2\sigma_i g\mu_i\), shared \(D\).
5. **Independent two-Burgers:** the equal-coupling stochastic two-mode
   manifold diagonalizing to \(u_\pm\).
6. **Coupled two-mode:**
   \(D_m\ne D_\phi\), \(\lambda_m\ne\lambda_\phi\), with one global,
   symmetry-constrained hidden-field initialization
   \(\phi_0=\alpha[m_0^2-\overline{m_0^2}]\).
7. **Memory or additional modes:** the registered interpretation when the
   Markov one- and two-field candidates do not organize the joint held-out
   observables.

The stochastic solver budget is frozen independently of quantum fit quality:
1,024 trajectories for screening and at least 2,048 for the final ensemble,
with common random numbers for paired comparisons.

### 10.5 Decision thresholds

The scalar universality assessment requires all of:

- leave-one-condition-out integrated error below \(1\%\);
- endpoint error below \(2\%\);
- coefficient spread below \(10\%\);
- rolling coefficient powers within \(0.10\) of constancy for the universal
  candidate;
- symmetry defects below five numerical noise floors;
- late width exponent within \(0.05\) of the model forecast.

The finite-window tangent interpretation requires:

- within-condition error below \(0.5\%\), or three numerical floors;
- at least a factor-of-two increase in cross-condition error;
- \(|A_B/A_W-1|<5\%\);
- rolling powers near \((-1/3,+1/3)\) within \(0.12\);
- deterministic continuation exhibiting the Burgers rarefaction crossover.

The common two-mode gate requires:

- at least \(30\%\) improvement over the best scalar competitor;
- a positive lower endpoint for the paired-bootstrap \(95\%\) interval;
- spin-flip and parity equivariance;
- one parameter set for profiles, currents, responses, and FCS.

The coupled model must additionally improve over independent two-Burgers by at
least \(10\%\) with \(\Delta\mathrm{BIC}\ge10\).  Time-block uncertainty uses
2,000 paired replicates with physical block duration 10.

The base universality verdict retains these exact protocol labels:

- `universal_scalar_supported_for_identified_field`;
- `physical_scalar_rejected_finite_surrogate_supported`;
- `two_mode_supported_scalar_rejected`;
- `memory_or_more_modes_required`;
- `simulation_unresolved` or `insufficient_observables` when the evidence
  gates do not yet support model selection.

The Production-v2 selection record refines the two-mode branch into
`scalar_surrogate_not_rejected`, `independent_two_burgers_supported`,
`coupled_two_mode_supported`, and `memory_or_more_modes_required`.  Keeping
the base scientific verdict and the executable v2 selection label separate
prevents a coarse label from hiding which nested model actually passed.

Protocol v1.2 gives the blinded Production-B interval to any surviving
registered scalar, independent-two-Burgers, or coupled-two-mode forecast.  It
does not reserve future-time confirmation for a preferred theory.

## 11. Numerical implementation and validation already completed

The confirmatory experiment uses an infinite-temperature purification-TEBD
backend in TeNPy.  The implementation includes magnetization, complete
physical-cut current, connected \(C^{zz}\), two-measurement transfer FCS,
checkpoint/resume, and grouped two-spin sites for the \(J_1\)-\(J_2\) control.

Completed validation includes:

- spin-flip defects below \(2\times10^{-15}\) in the small-chain smoke tests;
- total-magnetization drift at approximately \(10^{-14}\);
- a lattice-continuity relative residual of \(4.17\times10^{-4}\) in the
  original smoke validation;
- FCS Hermiticity, \(Z(0)=1\), spin-flip, and first-cumulant/charge-transfer
  checks;
- dense \(L=6\) evolution agreement at \(10^{-9}\) or better for the original
  observables;
- a real interruption and HDF5 restart whose stored arrays agree bit for bit;
- \(J_2=0.1\) grouped-backend agreement with dense evolution to at worst
  \(8.3\times10^{-10}\);
- grouped/ordinary \(J_2=0\) agreement to at worst
  \(1.0\times10^{-8}<2\times10^{-7}\);
- exact continuation compatibility across the original and current runner
  pair, including a zero-difference resumed dataset;
- source-hash gates on all twelve convergence jobs.

The latest committed \(J_2\) evidence records SCNet compute-node preflight job
`23015027` as `COMPLETED`, with all exact, symmetry, FCS,
grouped-equivalence, and checkpoint checks passing.  The resulting
Production-A \(J_2\) gate contains 31 ready rows and zero \(J_2\) blockers;
submission still remains conditional on the separate convergence gate.

The production-v2 manifest contains 34 logical conditions in each of
Production A and B.  Production A has 32 new executions and two exact fine-row
reuse paths; its registered FCS logical count is seven.  Production B has 34
fresh executions and three FCS rows.  Builders materialize and validate these
bundles without submitting them before their evidence gates are satisfied.

## 12. Current status and the next decisive readout

The public-trajectory pilot is complete:

```text
universal_scalar: unresolved
finite_window_surrogate: supported
microscopic_moment_law: not_rejected
two_mode: not_tested
overall: insufficient_observables
```

The confirmatory program is at the convergence stage.  Twelve registered jobs
cover four representative conditions at the three resolutions in the table
above.  The archived launch audit records jobs `23009466`--`23009477` as
started with initial checkpoints and controller `23009668` waiting on their
completion.  Because a live gateway refresh was not available while preparing
this document, these are explicitly dated archived observations, not a claim
about the present scheduler state.

The next decisive readout is therefore not another fit to the same public
trajectory.  It is the medium-to-fine convergence audit.  Once accepted, the
workflow is:

1. materialize the two validated reuse attestations and run Production A;
2. fit every registered model on \(50\le t\le150\);
3. evaluate time, condition, and orientation holdouts on
   \(150<t\le200\);
4. combine profile, current, response, correlation, and FCS losses;
5. produce one frozen model-selection record with hashes and uncertainty;
6. explicitly authorize the one-time unblinding if the selected forecast is
   eligible;
7. test that forecast once on \(200<t\le400\).

This sequence directly answers the issue's central distinction:

- **specific approximation:** coefficients or model quality track amplitude,
  orientation, shape, background, resolution, or time window;
- **transferable effective law:** one registered parameterization predicts
  unseen conditions and the blind future interval;
- **controlled microscopic closure:** the transferable field is identified,
  respects exact symmetries, and derives from an explicit reduction with
  quantified omitted terms.

No finite numerical campaign can prove a PDE for all times in the mathematical
sense.  It can, however, establish a controlled hydrodynamic law within a
stated scaling regime and give reproducible evidence for or against each
closure assumption.  That is the certification standard implemented here.

## 13. Where quantum computing enters

The scientific endpoint is a quantum-computing benchmark, but quantum
hardware is not used as a substitute for hydrodynamic reasoning.

The classical MPS campaign provides the controlled reference regime:
convergence can be measured, exact small systems can be checked, and every
observable has a frozen numerical floor.  Its limiting resource is
entanglement growth, exactly the obstacle emphasized by the original
machine-discovery work.

Quantum processors can extend the observable frontier in three ways:

1. prepare weak walls, pulses, backgrounds, and equilibrium ensembles beyond
   the classically accessible time window;
2. measure currents, correlators, and characteristic functions rather than
   only a mean profile;
3. generate blind future-time data against which a machine-discovered closure
   is certified without extrapolating the closure itself.

The benchmark supplied by this PR is therefore reusable: a quantum simulator
produces the registered observable panel, while the classical audit performs
symmetry checks, cross-condition model selection, uncertainty estimation, and
one-time blind confirmation.  The goal is not merely to use a quantum device
to draw a KPZ collapse.  It is to determine which effective equation the
device's dynamics actually support, for which field, under which conditions,
and with which omitted-mode uncertainty.

## 14. Reproducibility and evidence index

The scientific contract is
[`docs/RESEARCH_PROTOCOL_BURGERS_UNIVERSALITY.md`](docs/RESEARCH_PROTOCOL_BURGERS_UNIVERSALITY.md).
The machine-readable matrix and thresholds are
[`configs/burgers_research_matrix.json`](configs/burgers_research_matrix.json)
and
[`configs/burgers_decision_rules.json`](configs/burgers_decision_rules.json).

The following committed artifacts anchor the principal claims:

| Claim | Evidence |
|---|---|
| Field-identification, averaging, rarefaction, and public-profile audit | [`docs/CLOSED_LOOP_VERDICT.md`](docs/CLOSED_LOOP_VERDICT.md) |
| Frozen hypotheses, conditions, splits, and thresholds | [`docs/RESEARCH_PROTOCOL_BURGERS_UNIVERSALITY.md`](docs/RESEARCH_PROTOCOL_BURGERS_UNIVERSALITY.md) |
| Protocol corrections frozen before Production-A results | [`docs/PROTOCOL_AMENDMENTS.md`](docs/PROTOCOL_AMENDMENTS.md) |
| Implementation and archived cluster ledger | [`docs/IMPLEMENTATION_STATUS_BURGERS_RESEARCH.md`](docs/IMPLEMENTATION_STATUS_BURGERS_RESEARCH.md) and [`CURRENT_STATUS.md`](CURRENT_STATUS.md) |
| 74-row base manifest | [`results_research_program/manifest.json`](results_research_program/manifest.json) |
| 68-row Production-v2 A/B manifest | [`results_research_program/production_manifest_v2.json`](results_research_program/production_manifest_v2.json) |
| Current dataset gates | [`results_research_program/dataset_validation.json`](results_research_program/dataset_validation.json) |
| Frozen stochastic ensemble and refinement budget | [`results_research_program/two_mode/solver_budget.json`](results_research_program/two_mode/solver_budget.json) |
| \(J_2\) local and SCNet compute-node validation | [`results_research_program/hpc/j2_validation_20260730.json`](results_research_program/hpc/j2_validation_20260730.json) |
| Two-mode/FCS data-completeness audit | generated by `scripts/run_two_mode_comparison.py` |

Lightweight local checks run from this directory:

```bash
python3 -m compileall -q src scripts hpc tests
python3 -m pytest -q
python3 scripts/validate_tenpy_exact_diagonalization.py
python3 scripts/validate_tenpy_fcs.py
python3 scripts/validate_tenpy_resume.py
```

Tensor-network production uses the pinned Slurm entry points under
`hpc/scnet/`.  Raw production arrays and checkpoints remain in the registered
compute environment; the public package contains source, compact manifests,
decision rules, and validation summaries without private credentials.

## 15. Primary literature

1. Y. Kharkov *et al.*, [“Discovering hydrodynamic equations of many-body
   quantum systems”](https://arxiv.org/abs/2111.02385) (2021).
2. M. Ljubotina, M. Žnidarič, and T. Prosen,
   [“Kardar-Parisi-Zhang physics in the quantum Heisenberg
   magnet”](https://arxiv.org/abs/1903.01329) (2019).
3. J. De Nardis, S. Gopalakrishnan, and R. Vasseur,
   [“Non-linear fluctuating hydrodynamics for KPZ scaling in isotropic spin
   chains”](https://arxiv.org/abs/2212.03696) (2023).
4. E. Rosenberg *et al.*, [“Dynamics of magnetization at infinite temperature
   in a Heisenberg spin chain”](https://arxiv.org/abs/2306.09333) (2023).
5. K. A. Takeuchi *et al.*, [“Partial yet definite emergence of the
   Kardar-Parisi-Zhang class in isotropic spin
   chains”](https://arxiv.org/abs/2406.07150) (2025 revision).
6. A. Valli *et al.*, [“Efficient computation of cumulant evolution and full
   counting statistics: application to infinite temperature quantum spin
   chains”](https://arxiv.org/abs/2409.14442) (2025 publication).
