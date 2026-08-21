# Phase 6 Critical-Scaling Design

## Objective and scope

Reproduce the published `sigma=1.75` critical point
`Gamma_c=1.5609(3)` before attempting the full challenge sigma scan. The
primary production sizes are `L=64,128,256`. `L=32` is included only as a
correction-analysis diagnostic for crossing drift and leave-smallest-size
checks; it must not be retained merely because it improves fit quality or
moves a result toward a published value.

The Hamiltonian remains

```text
H = -sum_(i<j) J_L(j-i;sigma) Z_i Z_j - Gamma sum_i X_i,
```

where `J_L` is the periodic Hurwitz-zeta image sum. No other sigma value and
no automatic critical-point search is part of this phase.

## Symmetry-resolved rotated basis

Production MPS calculations use a basis rotation

```text
physical X -> TeNPy Sigmaz
physical Z -> TeNPy Sigmax.
```

TeNPy's conserved parity in this basis is the physical global spin-flip
parity `prod_i X_i`. The ground state is targeted in the even sector and the
first excitation in the odd sector. This preserves the finite-ring symmetry
and prevents a symmetry-broken MPS branch from contaminating the zero-momentum
structure factor.

Before production, rebuild both the nearest-neighbor TFIM and the periodized
long-range MPO in the rotated convention. Validate both Hamiltonians at
`L=8,10,12`, requiring agreement of the even-sector ground energy and
odd-sector first-excitation energy with their existing dense-ED fixtures.
Also reconstruct the physical correlation as

```text
C(r) = (1/L) sum_i <Sigmax_i Sigmax_(i+r mod L)>
```

in the rotated basis and compare it with dense ED. The full correlation is
used; no connected-correlation subtraction is allowed.

## Primary critical-point estimator

For each size and transverse field, compute the full translation-averaged
physical correlation, written explicitly with physical operators,

```text
C(r) = (1/L) sum_i <Z_phys,i Z_phys,(i+r mod L)>.
```

In the rotated TeNPy basis, `Z_phys` is `Sigmax`, so the same observable is
evaluated through `Sigmax`-`Sigmax` correlations. The two expressions denote
one physical correlation, not separate definitions.

Its structure factor and second-moment correlation length are

```text
S(k) = sum_(r=0)^(L-1) cos(k r) C(r),
k_min = 2 pi/L,
xi = [2 sin(k_min/2)]^(-1) sqrt[S(0)/S(k_min) - 1],
R_xi = xi/L.
```

The real cosine transform is used because the finite-ring correlations are
real and inversion symmetric. `R_xi` is the primary dimensionless crossing
observable. Binder and fixed-distance correlation ratios are optional
cross-checks only.

## Locked Gamma grid

Every size uses the same preregistered nested grid:

```text
coarse: Gamma=1.540,...,1.580, step 0.005
fine:   Gamma=1.552,...,1.570, step 0.001.
```

There is no adaptive refinement. For each pair `(L,2L)`, obtain
`Gamma_x(L,2L)` by linear interpolation between the two neighboring fine-grid
points where

```text
R_xi(L,Gamma) - R_xi(2L,Gamma)
```

changes sign.

If any crossing lies outside the initial range, extend both coarse and fine
windows symmetrically by `0.010` at each end, retaining the original
spacings. Record the extension before executing it. Never extend only toward
the published critical field.

## Gamma_c extraction and correction analysis

The three adjacent-size crossings are `(32,64)`, `(64,128)`, and `(128,256)`.
The primary critical-point estimate is the intercept of the preregistered
power-drift form

```text
Gamma_x(L,2L) = Gamma_c + a/L.
```

Sensitivity analyses use

```text
Gamma_x(L,2L) = Gamma_c + a/log(L)
```

and repeat both forms after removing the `(32,64)` crossing. With only two
crossings after removal, these are sensitivity brackets, not statistically
distinguishable correction models. No correction form is selected according
to agreement with `Gamma_c=1.5609(3)`.

Critical-field uncertainty includes crossing interpolation, MPS convergence,
MPO convergence, the full-window versus leave-`(32,64)`-out shift, and the
power-versus-log sensitivity spread. The published value is compared only
after this analysis is locked and complete.

## Gap convention and z extraction

All sizes use the same primary extrapolated `Gamma_c`; pair-dependent
pseudocritical fields are not used for the gap. Compute `Delta(L,Gamma_c)`
from the odd-sector first excitation minus the even-sector ground energy.
Repeat the gap calculation at the lower and upper `Gamma_c` uncertainty
bounds to propagate critical-field uncertainty.

The primary DMRG dynamical estimator is the gap-based pairwise effective
dynamical exponent

```text
z_eff(L1,L2) = -log[Delta(L2)/Delta(L1)]/log(L2/L1),
L_eff = sqrt(L1*L2),
```

where `L_eff` is the logarithmic midpoint assigned to each pair. For doubled
sizes this reduces to the previously stated `z_eff(L,2L)` formula. The
primary production interpretation emphasizes
`z_eff(64,128)` and `z_eff(128,256)`; the `L=32` point diagnoses corrections.

Two fixed sensitivity forms are reported:

```text
power: z_eff(L_eff) = z + a/L_eff,
log:   z_eff(L_eff) = z + a/log(L_eff).
```

This definition follows from the DMRG gap scaling
`Delta(L,Gamma_c) ~ L^(-z)`; it is not the finite-size estimator used in
Shiratani--Todo's QMC aspect-ratio procedure. These correction forms are
sensitivity analyses only; no correction-form model selection is claimed
with the available sizes. The reported z uncertainty combines gap numerical errors,
the propagated `Gamma_c` interval, leave-`L=32`-out drift, and the difference
between the two correction sensitivities.

## Targeted bond-dimension convergence

Run the complete common Gamma grid at `chi=128`. Higher bond dimensions are
reserved for the two fine-grid bracket points defining each crossing, and for
the gaps at `Gamma_c` and its uncertainty bounds.

For every crossing, recompute the same bracket at `chi=256` and `chi=384`.
Accept the crossing only if

```text
abs(Gamma_x(384)-Gamma_x(256)) <= 2e-4
```

and the shift does not grow relative to
`abs(Gamma_x(256)-Gamma_x(128))`. The sign-change bracket must remain
unchanged at `chi=256` and `chi=384`. Otherwise run `chi=512` and apply the
same `2e-4` threshold to `Gamma_x(512)-Gamma_x(384)`. Failure at `chi=512`
is reported as unresolved.

For every gap, require

```text
abs(Delta(384)-Delta(256))/abs(Delta(384)) <= 1e-3
```

and maximum discarded weight no larger than `1e-9`, separately for the
ground and excited states. If either condition fails, run `chi=512` and
require the same discarded-weight bound and

```text
abs(Delta(512)-Delta(384))/abs(Delta(512)) <= 1e-3.
```

Failure remains visible as a non-converged cell. Variance is always recorded
but is not an unconditional production cutoff.

The crossing threshold `2e-4` and relative gap threshold `1e-3` quantify only
chi-induced numerical uncertainty. They are not the final uncertainties of
`Gamma_c` or z, which are expected to be dominated by finite-size drift and
correction analysis. Chi is never raised or stopped according to agreement
with a published critical field or expected exponent.

## Per-sigma exponential-fit regeneration

Every sigma value receives a fresh deterministic fit; coefficients and pole
spectra are never reused between sigma values. For the current
`sigma=1.75`, and later independently for every requested sigma, use

```text
primary: K=24, alpha=0.5,
r_fit = 8 x L_max = 2048, with L_max=256.
```

The fit target remains only the infinite kernel `r^(-1-sigma)`. Optimize
bounded exponential rates by variable projection and solve nonnegative
coefficients `c_k>=0`.

Before production at each sigma:

1. Validate the analytically periodized coupling against exact Hurwitz-zeta
   tables at `L=32,64,128,256`.
2. Repeat tail windows `r_fit=1024,2048,4096`.
3. Repeat pole counts `K=16,24,32`.
4. At `K=24`, repeat `alpha=0.25,0.5,1.0`.
5. Record every `lambda_k`, `a_k=-log(lambda_k)`, `c_k`,
   `a_min*r_fit`, and the complete distance-resolved coupling error.
6. Verify periodic symmetry and stable behavior at both short distances and
   `r` near `L/2`.

The final `K=24` versus `K=32` comparison has two layers:

- Hamiltonian level: coupling reconstruction error and periodized tail
  behavior;
- physics level: `Gamma_x` crossings, `Delta(L,Gamma_c)`, and `z_eff`.

MPO-induced shifts are reported separately from chi-induced shifts and from
finite-size corrections. The `K=24` versus `K=32` shifts in every
`Gamma_x(L,2L)`, every `Delta(L,Gamma_c)`, and every `z_eff(L,2L)` are
propagated into the corresponding uncertainty records. K is accepted from
convergence of these quantities, not from agreement with the published
`Gamma_c` or an expected z. If the physics-level K comparison is not
converged, production interpretation stops and K is increased systematically.

## Execution, provenance, and outputs

The full grid contains 24 distinct Gamma values for each of four sizes before
high-chi bracket refinement. This is cluster-scale work, not a local run.
Each cell records the exact Hamiltonian convention, sigma, L, Gamma, fit
spectrum/hash, K, alpha, r_fit, chi, sector, initialization, sweep statistics,
variance, discarded weight, energy, correlations, and code revision.

The run is resumable and retains failed or missing cells. Raw correlations and
state diagnostics are written before crossing interpolation or scaling fits.
Processed outputs include:

- `R_xi(Gamma,L)` tables containing raw `S(0)`, `S(k_min)`, and `xi`, plus
  the crossing plot;
- interpolated crossing table with chi and K convergence;
- primary and sensitivity `Gamma_c` fits;
- gap table at central/lower/upper `Gamma_c`;
- `z_eff` table and power/log sensitivity plots;
- a separated uncertainty budget for MPO, MPS, field propagation, and
  finite-size corrections.

No broader sigma scan starts until the `sigma=1.75` reproduction passes the
rotated-basis validation, fit-regeneration gate, crossing convergence, and
gap convergence defined above.
