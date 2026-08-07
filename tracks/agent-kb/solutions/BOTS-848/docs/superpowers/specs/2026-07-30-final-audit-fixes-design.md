# BOTS:848 Final Audit Fixes Design

## Objective

Remove the scientific and reproducibility blockers found in the final audit
without expanding the two-day literature study into a production many-body
electron--phonon implementation.  The result remains a source-backed research
hypothesis and software MVP; it must not claim real-material accuracy or a
measured speedup over DFPT.

## Physical contract

The finite-q electron-gas comparison constrains a complete physical-to-DFPT
ratio, not a second proper-vertex factor applied to an already screened DFPT
operator:

```text
K_total = g_physical / g_DFPT
        = z Gamma_rho [1 - (v + f_xc) chi_s] / [1 - v P_MB].
```

Under the scalar matching relation used in the report,
`P_MB = chi_s / (1 - f_xc chi_s)` and
`z Gamma_rho = P_MB / chi_s`, so `K_total` is approximately one.  The report
will therefore remove `P/chi_s` as a universal correction kernel and retain the
electron-gas result only as evidence that the complete static DFPT vertex can
be accurate in that calibration domain.

The one-body Hermitian prototype uses four mutually orthogonal channels:

1. `global_charge`: the single global identity component;
2. `site_charge`: block-identity shifts relative to the global average;
3. `internal`: the traceless remainder inside each site block;
4. `nonlocal`: off-site blocks.

Only `global_charge` can be Ward protected, and the decision gate may return
`dfpt-safe` for it only when evidence explicitly states that the perturbation is
the strict uniform q=0 common shift.  `site_charge`, `internal`, and `nonlocal`
all count as correction channels.

The executable decomposition remains restricted to a Hermitian real-space
derivative, Gamma perturbation, or a real standing-wave combination of q and
-q.  A general fixed-q perturbation instead obeys `D(q)^dagger = D(-q)` and is
outside the present API.  The report will state this limitation rather than
claim continuous finite-q support.

Derivatives of two-body interactions such as `dU/du` and `dJ/du` remain a
separate two-body vertex space.  They are not components of the one-body
Hilbert--Schmidt decomposition.  Sparse response fitting targets a declared
fixed-basis one-body inverse-Green-function vertex; quasiparticle external-leg
residues and state rotations must be applied separately before observables are
compared.

## Software contract

- Reject booleans and non-finite matrix entries, weights, thresholds, kernels,
  evidence ratios, coefficients, and costs.
- Static channel kernels are finite real scalars so a Hermitian input remains
  Hermitian.
- Preserve finite response coefficients during serialization; formatting must
  not change the matrix used for prediction.
- Keep the existing cost semantics: the corrected path can be cheaper than a
  dense higher-level calculation but is not faster than DFPT-only in the
  bundled accounting model.

## Reproducibility contract

Reviewer report builds write only below `report/build/`; `make check-all` must
not modify the distributed `report/main.pdf` or leave LaTeX intermediates in the
worktree.  The documented SHA-256 validates the distributed artifact, not
bitwise reproducibility of a fresh TeX build.  A maintainer-only target updates
the distributed PDF after source changes.

## Verification

Regression tests cover the staggered-site counterexample, the strict q=0 gate,
non-finite inputs, real kernels, small fitted coefficients, and finite costs.
The final gate is two consecutive `make check-all` runs in a fresh clone,
followed by a clean Git status, PDF page rendering, link/claim audit, and commit
attribution verification.

## Non-goals

- No production fixed-q q/-q paired matrix interface.
- No implementation of a two-body interaction vertex.
- No autonomous online retrieval engine or real-material training data.
- No claim of universal DFPT validity, physical held-out accuracy, or measured
  runtime acceleration.
