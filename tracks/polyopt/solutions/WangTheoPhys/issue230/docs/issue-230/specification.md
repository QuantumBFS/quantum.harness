# Issue #230 certificate specification

## Quantity and normalization

For a chain of spin-\(\frac12\) sites, this project uses

\[
H_N(\Delta)=\frac14\sum_j
\left(X_jX_{j+1}+Y_jY_{j+1}+\Delta Z_jZ_{j+1}\right).
\]

The target is the thermodynamic ground-state energy per bond/site,

\[
e_0(\Delta)=\lim_{N\to\infty} E_0(H_N(\Delta))/N.
\]

All JSON certificates carry the model identifier
`xxz-spin-half-xx+yy+delta-zz-over-4`. A verifier must reject any other
identifier. Finite periodic energies are not treated as thermodynamic
certificates without an explicit construction proving the required direction.

## Certified endpoints

A level certificate proves

\[
L_{\rm cert}\le e_0(\Delta)\le U_{\rm cert}.
\]

The lower endpoint is reconstructed from a dual SDP witness using exact
rational arithmetic and exact positive-definiteness checks. The upper endpoint
is reconstructed from an explicitly finite rational variational state. Raw
floating-point solver values are stored for diagnostics only.

At \(\Delta=1\), the independent reference is

\[
e_B=\frac14-\log 2.
\]

The verifier evaluates an outward-rounded decimal interval
\([e_B^-,e_B^+]\) itself and checks

\[
L_{\rm cert}\le e_B^-\le e_B^+\le U_{\rm cert}.
\]

Neither the Bethe value nor its interval may be passed to a lower/upper solver,
candidate ranker, rational repair routine, or PSD shift calculation.

## Lower proof families

- `lti-rational-dual`: exact dual of a dense local
  translation-invariant marginal relaxation.
- `u1-lti-rational-dual`: the same implication represented in fixed
  magnetization sectors.
- `rg-lti-rational-dual`: exact dual of an MPS-flow-compressed LTI
  relaxation.
- `anderson-rational-ldl`: exactly checked finite-cluster decomposition.
- `local-term-spectrum`: analytic fallback from the smallest local
  interaction eigenvalue.

Symmetry reduction is accepted only after a small-instance equivalence test or
an exact lift back to a canonical proof representation. Sparse principal
submatrices may yield sound relaxations, but no unproved convergence rate is
claimed for arbitrary sparse deletion.

## Upper proof families

- `rational-mps-repeated-block`: exact finite rational MPS block, including
  explicit left and right boundary vectors.
- `rational-sparse-repeated-block`: exact sparse block vector.
- `rational-repeated-block`: exact dense block vector.
- analytic product-state fallback.

The repeated-block construction explicitly includes the boundary bond cost;
therefore it defines a physical infinite variational state rather than relying
on an uncontrolled finite-size extrapolation.

## Level ordering

Files presented as one nested hierarchy for a fixed \(\Delta\) must satisfy

\[
L_{\ell+1}\ge L_\ell,\qquad U_{\ell+1}\le U_\ell.
\]

The audit command groups by \(\Delta\), sorts by declared level, and fails its
overall status if either direction is violated. Results from unrelated
relaxations may be reported separately without a false nesting claim.

## Release gates

A release result is strict only if:

1. schema validation succeeds with no ignored fields;
2. proof arithmetic is independently reconstructed;
3. all required exact PSD and compatibility checks pass;
4. stored rounded endpoints lie outside their exact witnesses;
5. the independently evaluated Bethe interval is contained;
6. the certificate is included in the clean-environment test suite;
7. its Git commit, generator, solver, and dependency provenance are recorded.

Record claims additionally require a cited, normalization-matched prior strict
thermodynamic bound. The currently selected level-13 result is a rigorous
baseline, not yet a record-width result.
