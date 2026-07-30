# Burgers universality: preregistered proof-or-falsification protocol

**Protocol version:** 1.2  
**Frozen:** 2026-07-29; v1.2 eligibility amendment frozen 2026-07-30,
before Production-A results  
**Primary system:** \(\Delta=1\), \(T=\infty\), \(J=1\), zero background
magnetization  
**Machine-readable matrix:** `configs/burgers_research_matrix.json`  
**Machine-readable rules:** `configs/burgers_decision_rules.json`

## 1. Question

The public high-temperature Heisenberg domain wall is reproduced with very
high accuracy on \(t\simeq50\!-\!200\) by

\[
U_t+aUU_x=D_{\rm cl}U_{xx}.
\]

This protocol distinguishes:

1. a universal deterministic scalar equation for an identified physical
   hydrodynamic field;
2. a trajectory- and window-conditioned scalar surrogate;
3. a microscopic GHD moment law;
4. a symmetry-complete two-mode fluctuating theory.

Training residuals are secondary evidence. The primary evidence is prediction
on unseen initial conditions and future times, together with exact symmetry
tests.

## 2. Frozen hypotheses

### \(H_{\rm U}\): universal physical-magnetization scalar law

One pair \(a,D_{\rm cl}\), depending only on the Hamiltonian and thermodynamic
state, predicts all registered \(\Delta=1,T=\infty,m_0=0\) conditions.

### \(H_{\rm F}\): finite-window scalar surrogate

Condition- and window-dependent \(a_{\mathcal I,\mathcal W}\) and
\(D_{\mathcal I,\mathcal W}\) predict one trajectory locally but do not
transfer universally.

### \(H_{\rm G}\): GHD moment law

\[
D_{\rm moment}(W)=A_\infty\sqrt W,\qquad
A_\infty=\frac{20\pi}{81}=0.775701894\ldots.
\]

Equivalently,

\[
W(t)=1.106260504\ldots\,t^{2/3},\qquad
D_{\rm moment}(t)=0.815874868\ldots\,t^{1/3},
\]

up to finite-time corrections.

### \(H_2\): two-mode nonlinear fluctuating hydrodynamics

\[
\begin{aligned}
m_t+\partial_x[m\phi-D_m m_x-\sqrt{2D_m\chi}\xi_m]&=0,\\
\phi_t+\partial_x[\lambda_m m^2/2+\lambda_\phi\phi^2/2
-D_\phi\phi_x-\sqrt{2D_\phi\chi}\xi_\phi]&=0.
\end{aligned}
\]

The chiral fields \(u_\pm=m\pm\phi\), rather than physical \(m\) alone, are the
candidate Burgers modes.

## 3. Exact field-identification gate

At zero magnetic field, spin flip requires

\[
m\mapsto-m,\qquad j_m\mapsto-j_m.
\]

Consequently a local one-field physical-magnetization current must be odd:

\[
j_m(m)=c_1m+c_3m^3+\cdots.
\]

A fixed term \(a m^2/2\) is forbidden. A microscopic derivation of a nonzero
quadratic current must identify at least one of:

- a chiral mode \(u_\pm\);
- a spin-flip-odd sector label;
- a nonzero background about which the current is expanded;
- explicitly broken spin-flip symmetry.

Passing profile fits cannot override this exact gate.

## 4. Moment-level bridge

For a rising wall with plateaus \(\pm U_0\),

\[
p=\frac{U_x}{2U_0},\qquad
W^2=\int(x-\bar x)^2p\,dx,
\qquad
D_{\rm moment}=\frac12\frac{dW^2}{dt}.
\]

The deterministic scalar Burgers equation obeys

\[
D_{\rm moment}
=D_{\rm cl}
+\frac{a}{4U_0}\int(U_0^2-U^2)\,dx.
\]

With

\[
c_f=\frac{\int(U_0^2-U^2)\,dx}{U_0^2W},
\qquad
v=\frac{aU_0c_f}{4},
\]

this becomes

\[
D_{\rm moment}=D_{\rm cl}+vW,\qquad
\dot W=\frac{D_{\rm cl}}W+v.
\]

The GHD and Burgers constitutive laws are compared through

\[
A_W=\frac23\frac{dW^{3/2}}{dt},
\qquad
A_B=2\sqrt{D_{\rm cl}v}.
\]

The finite-window tangent hypothesis predicts

\[
D_{\rm cl}=vW_*,\qquad A_B=A_W,
\]

and rolling coefficient powers

\[
a(t_*)\sim t_*^{-1/3},\qquad
D_{\rm cl}(t_*)\sim t_*^{1/3}.
\]

## 5. Registered physical conditions

The machine-readable configuration is authoritative. It contains:

- \(\mu=0.02,0.05,0.10,0.20\), both orientations;
- tanh widths \(1,2,4,8\);
- erf, double-wall, Gaussian, and two sinusoidal profiles;
- backgrounds \(m_0=\pm0.05\);
- environment controls \(\Delta=0.8\), \(\Delta=1.2\), and
  \(\Delta=1,J_2=0.1\).

Environment controls do not enter the restricted \(\Delta=1\) universality
verdict.

For avoidance of ambiguity, the registered \(J_2\) control means

\[
H=-J\sum_i\left(S_i^xS_{i+1}^x+S_i^yS_{i+1}^y+
\Delta S_i^zS_{i+1}^z\right)
-J_2\sum_i\mathbf S_i\cdot\mathbf S_{i+2}.
\]

This convention was made machine-readable before any confirmatory simulation
was generated; see `docs/PROTOCOL_AMENDMENTS.md`.

## 6. Frozen data split

\[
\text{training}:50\le t\le150,
\]

\[
\text{validation}:150\le t\le200,
\]

\[
\text{blinded test}:200\le t\le400.
\]

Rolling windows are stored in the matrix configuration. No test interval may
be used to select preprocessing, model class, parameter priors, or error
thresholds.

## 7. Numerical convergence gate

The registered nested ladder is:

| level | \(L\) | \(\Delta t\) | \(\chi_{\max}\) | cutoff |
|---|---:|---:|---:|---:|
| coarse | 256 | 0.05 | 256 | \(10^{-8}\) |
| medium | 384 | 0.025 | 512 | \(10^{-10}\) |
| fine | 512 | 0.0125 | 1024 | \(10^{-11}\) |

A condition enters confirmatory testing only if

\[
\frac{\|U_{\rm fine}-U_{\rm medium}\|_2}{\|U_{\rm fine}\|_2}<0.002
\]

and

\[
\max_t\frac{|W_{\rm fine}-W_{\rm medium}|}{W_{\rm fine}}<0.003.
\]

Failure produces `simulation_unresolved`, not a physics verdict.

## 8. Registered scalar competitors

1. `shared_constant`: one \(a,D_{\rm cl}\) for all primary conditions.
2. `condition_specific`: independent \(a_i,D_i\).
3. `sector_amplitude_law`:

   \[
   a_i=2\sigma_i g\mu_i,\qquad D_i=D.
   \]

The third competitor is required by the single-chiral projection and may not
be replaced post hoc by a different amplitude law.

## 9. Primary metrics

- integrated and endpoint profile relative \(L^2\);
- width and center forecast error;
- spin-flip and parity equivariance defects;
- weak-amplitude superposition defect;
- joint \((a,D_{\rm cl})\) bootstrap region and feature condition number;
- rolling \(A_W,A_B,W_*,a,D_{\rm cl},c_f\);
- structure-factor and current/FCS errors for the two-mode comparison.

Time-block bootstrap uses physical duration 10 and 2000 replicates.

## 10. Frozen decision logic

### Universal scalar survival

All must pass:

- leave-one-condition-out integrated error \(<1\%\);
- endpoint error \(<2\%\);
- coefficient spread \(<10\%\);
- \(|\eta_a|,|\eta_D|<0.10\);
- exact symmetry defects below five numerical noise floors;
- late width exponent within 0.05 of the scalar forecast.

### Finite-window surrogate support

All must pass:

- within-condition forecast error \(<0.5\%\) or three numerical floors;
- cross-condition error degrades by at least a factor of two;
- \(|A_B/A_W-1|<5\%\);
- rolling powers agree with \((-1/3,+1/3)\) within 0.12;
- deterministic continuation exposes crossover toward \(W\sim t\).

### Two-mode support

All must pass:

- cross-condition error improves by at least 30%;
- the paired-bootstrap 95% interval of the improvement is positive;
- spin-flip and parity are respected;
- one parameter set describes profile, current correlations, and registered
  current cumulants.

## 11. Allowed final outcomes

- `universal_scalar_supported_for_identified_field`
- `physical_scalar_rejected_finite_surrogate_supported`
- `two_mode_supported_scalar_rejected`
- `memory_or_more_modes_required`
- `simulation_unresolved`
- `insufficient_observables`

On the existing single public trajectory, the only admissible pilot result is

```json
{
  "universal_scalar": "unresolved",
  "finite_window_surrogate": "supported",
  "microscopic_moment_law": "not_rejected",
  "two_mode": "not_tested",
  "overall": "insufficient_observables"
}
```

## 12. Unblinding rule

Production B is an independent long-window confirmation of a registered
forecast that survived Production A. It is eligible for exactly these frozen
validation outcomes:

- `scalar_surrogate_not_rejected`;
- `independent_two_burgers_supported`;
- `coupled_two_mode_supported`.

`memory_or_more_modes_required`, unresolved, missing, malformed, or
contradictory outcomes do not open Production B. The first case means that the
registered candidate family failed; more calculation of those same forecasts
would not be confirmatory.

Before opening \(t>200\), the one-time human confirmation must record:

- protocol and configuration hashes;
- source-tree hash;
- convergence, Production-A, and frozen-analysis evidence hashes;
- validation-selection and analysis hashes;
- analysis command;
- random seeds;
- timestamp.

The test interval is unblinded once, only through the explicit
`--confirm-unblind` command. Analysis completion alone must not open or submit
Production B. Any subsequent model changes are exploratory and must be labeled
as such.

## 13. Amendment log

| date | version | amendment | status |
|---|---:|---|---|
| 2026-07-29 | 1 | Initial freeze for Phase 0 and future production data | confirmatory |
| 2026-07-29 | 1.1 | Recorded executable manifest, convergence, cross-condition, two-mode and one-time unblinding paths; no hypothesis, condition, split, or threshold changed | confirmatory |
| 2026-07-30 | 1.2 | Corrected Production-B eligibility: any surviving registered scalar, independent-two-Burgers, or coupled-two-mode forecast receives the independent long-window test; candidate-family failure and unresolved states stop | confirmatory; frozen before Production-A results |
