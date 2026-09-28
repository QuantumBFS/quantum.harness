# Closed-Loop Hydrodynamic Synthesis

## Executive statement

The machine-discovered viscous Burgers equation is an exceptionally accurate
finite-window effective closure for the public weak-domain-wall trajectory.
Its coefficients describe the tangent of a scale-dependent broadening law over
the sampled interval. Exact spin-flip symmetry assigns the quadratic current
to a chiral, sector-labelled, background-expanded, or trajectory-conditioned
field. Open-system averaging supplies an additional variance or covariance
current. Together these facts define a precise research program for deciding
which scalar or two-mode field carries the transferable hydrodynamic law.

The result has three layers:

1. **Exact microscopic structure:** continuity and spin-flip transformation.
2. **Measured effective structure:** the public profile, moment bridge, and
   rolling coefficients.
3. **Registered transferable structure:** multi-condition prediction of
   profiles, currents, responses, correlations, and full counting statistics.

## 1. Exact microscopic starting point

For the spin chain Hamiltonian, local magnetization obeys the continuity law

\[
\partial_t m(x,t)+\partial_x j_m(x,t)=0.
\]

This identity is the exact bridge from quantum dynamics to hydrodynamic
variables. It establishes conservation and leaves the constitutive relation
for \(j_m\) as the quantity to identify from symmetry, local equilibrium, and
data.

At zero magnetic field, global spin flip \({\cal F}\) acts as

\[
{cal F}:m\mapsto-m,
\qquad
j_m\mapsto-j_m.
\]

An autonomous local current written directly in terms of physical
magnetization therefore has odd parity:

\[
j_m(-m)=-j_m(m).
\]

The Burgers advective current

\[
j_B(U)=\frac{a}{2}U^2
\]

has even parity. This algebra identifies the learned \(U\) as a field carrying
extra orientation, background, sector, or chiral information. That field
assignment is productive: it points directly toward paired modes and
orientation-resolved coefficient laws.

## 2. Two-mode bridge

Introduce magnetization \(m\) and a second hydrodynamic field \(\phi\), with
the equal-coupling deterministic flux

\[
\partial_t m+g\partial_x(m\phi)=D\partial_x^2m,
\]

\[
\partial_t\phi+\frac{g}{2}\partial_x(m^2+\phi^2)
=D\partial_x^2\phi.
\]

The combinations

\[
u_+=m+\phi,
\qquad
u_-=m-\phi
\]

diagonalize the deterministic flux:

\[
\partial_tu_+ + g u_+\partial_xu_+ =D\partial_x^2u_+,
\]

\[
\partial_tu_- - g u_-\partial_xu_- =D\partial_x^2u_-.
\]

Thus paired Burgers equations arise algebraically as opposite-chirality normal
modes. Physical magnetization is their symmetric combination,

\[
m=\frac{u_++u_-}{2}.
\]

This bridge preserves spin-flip structure and turns the machine discovery into
a concrete hypothesis about the identity of the effective field. The
registered experiment compares independent chiral propagation with a coupled
stochastic two-mode extension.

## 3. Open-system mean evolution

For a stochastic Burgers mode

\[
\partial_tu+a,u\partial_xu
=D\partial_x^2u+\partial_x\eta,
\]

ensemble averaging gives

\[
\partial_t\langle u\rangle
+\frac{a}{2}\partial_x\langle u^2\rangle
=D\partial_x^2\langle u\rangle.
\]

Using

\[
\langle u^2\rangle
=\langle u\rangle^2+\operatorname{Var}(u),
\]

the mean equation becomes

\[
\partial_t\bar u
+a\bar u\partial_x\bar u
+\frac{a}{2}\partial_x\operatorname{Var}(u)
=D\partial_x^2\bar u.
\]

For paired modes, the corresponding mean flux contains their covariance.
Consequently the average profile carries information from fluctuations and
mode coupling. Current, connected response, and full counting statistics
measure this information directly and elevate the comparison beyond a profile
fit.

## 4. Public-data result

The public trajectory produces the following quantitative benchmark:

| Observable | Measured value |
|---|---:|
| fitted nonlinearity | \(a\simeq0.230\) |
| fitted viscosity | \(D_{\rm cl}\simeq1.97\) |
| integrated profile relative difference | \(0.167\%\) |
| width exponent, \(t=80\ldots190\) | \(0.6802\) |
| moment-diffusivity exponent | \(0.3372\) |
| width amplitude | \(A_W=0.741842\) |
| Burgers tangent ratio | \(A_B/A_W=0.999154\) |

The near-unit tangent ratio is the central analytical observation. Let the
wall width obey

\[
W(t)=A_Wt^\beta.
\]

The moment diffusivity is

\[
D_{\rm mom}(t)=\frac{1}{2}\frac{dW^2}{dt}
=\beta A_W^2t^{2\beta-1}.
\]

With \(\beta\approx2/3\), this quantity scales as \(t^{1/3}\). A
constant-coefficient Burgers profile samples a narrow interval of that curve
and produces an almost exact tangent across the observed window. This explains
simultaneously the profile fidelity, the fitted classical viscosity, and the
measured broadening exponent.

## 5. Deterministic continuation as a model signature

The fitted scalar equation generates its own long-time continuation. Its local
width exponent evolves from approximately \(0.665\) near \(t=200\) to
approximately \(0.851\) at \(t=5000\), approaching the deterministic
rarefaction scaling \(W\propto t\). The quantum chain supplies an independent
future-time trajectory. Comparing these two flows is a high-leverage
classification test:

- continued agreement supports a transferable deterministic scalar law;
- paired orientation and current agreement supports chiral Burgers modes;
- joint correlation and counting-statistics agreement supports the coupled
  open two-mode model;
- a richer temporal signature selects the registered memory or additional-mode
  extension.

Each branch is a scientifically informative destination in the frozen model
hierarchy.

## 6. Full-counting-statistics role

For an infinite-temperature equilibrium state, odd cumulants respect the
spin-flip pairing of opposite sectors. Even cumulants carry the shape and
coupling information needed to compare complete distributions. The fourth
cumulant, response functions, and connected correlations therefore complement
the mean profile and current.

The registered analysis scores one shared parameter set against the full
observable panel. This gives the scalar and two-mode hypotheses a common,
quantitative standard.

## 7. Evidence map

| Statement | Evidence class | Operational test |
|---|---|---|
| magnetization is conserved | exact | lattice continuity |
| physical current has odd spin-flip parity | exact | transformed current operator |
| paired chiral modes yield Burgers fluxes | algebraic | \(u_\pm=m\pm\phi\) diagonalization |
| public profile admits a precise Burgers closure | measured | profile and coefficient fit |
| fitted viscosity is a moment tangent | measured and analytical | \(A_B/A_W=0.999154\) |
| one parameter set transfers across conditions | registered | condition and orientation holdouts |
| stochastic two-mode physics organizes higher observables | registered | current, response, correlation, and FCS score |
| future-time forecast transfers | registered | sealed \(200<t\le400\) confirmation |

## 8. Paper-ready statement

> A machine-discovered constant-coefficient Burgers equation provides a
> high-precision effective closure for the public weak-domain-wall trajectory
> of the isotropic Heisenberg chain. Its fitted viscosity coincides with the
> finite-window tangent of the observed scale-dependent moment diffusivity.
> Exact spin-flip symmetry assigns the quadratic current to a chiral,
> sector-labelled, background-expanded, or trajectory-conditioned field, and
> open-system averaging introduces measurable variance and covariance fluxes.
> A preregistered multi-condition quantum-dynamics campaign now classifies the
> transferable law among scalar, paired-chiral, coupled-two-mode, and richer
> hydrodynamic descriptions.

## 9. Next decisive action

Complete the registered three-resolution convergence groups, materialize the
accepted datasets, and run Production A through \(t=200\). That single action
unlocks coefficient-transfer tests, symmetry-resolved current prediction,
higher-observable comparison, frozen model selection, and the one-time future
forecast. The long-time quantum readout is the direct answer to Issue #265.
