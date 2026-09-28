# Project summary

## Purpose

This package tests whether the constant-coefficient Burgers equation found in
the isotropic spin-1/2 Heisenberg chain is an asymptotic law or a finite-window
projection.  It combines a frozen numerical protocol with a trajectory-free
TBA/GHD/KPZ/Mori derivation.

## Main entry points

- `README.md`: current scientific answer, evidence ladder, and reproduction.
- `docs/FIRST_PRINCIPLES_WINDOW_DERIVATION.md`: microscopic continuity,
  infinite-field fluctuating GHD, exact projected memory equation, and the
  controlled finite-window closure hierarchy.
- `src/heisenberg_burgers_bridge.py`: theory-only constants, projection normal
  equations, scale-running closure, TCL coefficients, and Mori inversion.
- `scripts/derive_theory_only_hierarchy.py`: zero-trajectory coefficient and
  scheme-variation certificate for a declared time window.
- `scripts/audit_theory_finite_size_lattice.py`: zero-trajectory finite-chain
  and centered-lattice-difference audit.
- `scripts/audit_theory_exact_weak_estimator.py`: applies the exact frozen
  public-profile weak estimator to the zero-trajectory leading KPZ wall.
- `scripts/derive_xxx_mori_lanczos.py`: sparse Pauli-string commutators through
  the twenty-sixth long-wave Mori moment and the corresponding thirteen exact
  Lanczos recurrents.
- `scripts/derive_kpz_lanczos_terminator.py`: removes the exact microscopic
  recurrents from the universal KPZ kernel and evaluates the analytic
  scale-correction contribution to the finite-time terminator.
- `scripts/derive_microscopic_finite_window_mori.py`: one-command,
  zero-trajectory certificate combining the exact giant-string quadrature,
  KPZ self-consistency, the explicitly non-physical spectral-regulator
  candidate for `F1`, the resulting `delta K1(s)`, the microscopic Lanczos
  prefix, and the declared `50<t<200` projection band.
- `scripts/invert_finite_time_mori_from_walls.py`: gated, target-free inversion
  of `F1`, `F1_perp`, the microscopic quadratic current vertex, and the frozen
  weak `(a,D)` from converged opposite-wall datasets.  It refuses to run unless
  the convergence validation is accepted.
- `scripts/audit_microscopic_coefficient_identifiability.py`: target-free
  resolution/gate audit that keeps the exact physical Kubo vertex, conditional
  current vertex, and finite-frequency Mori projection distinct and never
  promotes their numerical proximity to a unique asymptotic scalar PDE.
- `scripts/derive_conditional_current_vertex_amplitude_limit.py`: frozen
  four-amplitude, two-orientation extrapolation of the microscopic conditional
  current vertex to `mu->0+`, kept distinct from the exact zero physical Kubo
  vertex.
- `scripts/evaluate_full_tba_diffusion.py`: finite-field dressed-kernel
  quadrature with independent string, rapidity, and velocity-series controls.
- `scripts/audit_full_tba_subleading.py`: exact-leading-benchmark audit that
  rejects an unconverged constant (D_1) and the finite-field/time-field
  substitution.
- `scripts/audit_joint_zero_field_limit.py`: fail-closed joint regulator
  certificate for the `h`, string-tail, rapidity-grid, and velocity-series
  limits of the full off-diagonal diffusion contraction.
- `scripts/audit_adaptive_mixed_kernel_step_zero_field.py`: calibrates the
  coarse/fine dressed-kernel error on matched fields, propagates it into the
  smallest-field point, and applies a fail-closed zero-field/D1 gate.
- `scripts/derive_full_mode_mori_certificate.py`: trajectory-free analytic
  OU covariance propagation and exact resolvent elimination of every retained
  non-spin GHD mode into the physical-spin Mori kernel.
- `scripts/derive_regulated_infinite_mode_fghd.py`: whitens every retained
  occupation mode, rotates exactly onto physical magnetization plus its full
  orthogonal complement, propagates the complete non-diagonal diffusion/FDT
  noise, and Schur-eliminates the complement without a finite-pole closure.
- `scripts/derive_full_mode_physical_one_loop.py`: deterministic Wick
  contraction of the dressed-velocity, state-dependent diffusion,
  multiplicative-FDT-noise, and quadratic-spin-observable vertices, with an
  explicit hydrodynamic-UV audit.
- `scripts/audit_mori_uv_local_counterterms.py`: tests whether a common finite
  Taylor/contact basis removes the one-loop cutoff drift over more than one
  Laplace frequency, and rejects frequency-selective apparent convergence.
- `scripts/derive_matched_infinite_mode_mori.py`: peels up to the thirteen exact
  `mu26` Lanczos levels from the complete known full-mode loop, reconstructs the
  unresolved terminator as a nonnegative continuum quadrature, and rejects
  cutoff-dependent or moment-incompatible kernels without choosing a pole
  count.
- `scripts/certify_nonlinear_mori_closure_no_go.py`: constructs two positive,
  unit-mass terminators behind the same exact `mu26` prefix and proves that the
  known finite microscopic moments plus the bare one-loop hydrodynamic
  vertices do not uniquely determine the low-frequency nonlinear Mori kernel.
- `scripts/audit_gap_3_4_5_7_completion.py`: freezes the exact finite-regulator
  statements for covariance propagation, Schur/Mori elimination, spin-flip
  current parity, and sharp-wall linear initial slip.
- `scripts/derive_matched_full_mode_wall.py`: fail-closed wall/projection gate;
  it emits no `a,D` unless positive-spectrum matching and the joint infinite-
  mode limit have both been certified.
- `scripts/derive_cubic_velocity_memory_smoke.py`: deterministic six-point Wick
  contraction of the first nonzero normal-ordered two-cubic-velocity (`W^2`)
  Mori memory, with wrapped cubic aliases removed.
- `scripts/plot_theory_only_burgers_window.py` and
  `scripts/plot_running_kernel_hierarchy.py`: diagnostic figures.
- `hpc/scnet/`: frozen SCNet submission, continuation, and validation gates.
- `tests/`: unit, regression, protocol, and submission-policy checks.

## Dependencies and commands

Python dependencies are listed in `requirements.txt`; the theory figures also
need NumPy, SciPy, and Matplotlib.  From this directory:

```bash
python3 -m pytest -q
python3 -m compileall -q src scripts hpc tests
python3 scripts/derive_theory_only_hierarchy.py --t-start 50 --t-stop 200
python3 scripts/audit_theory_finite_size_lattice.py --length 400
python3 scripts/audit_full_tba_subleading.py
```

The two theory scripts may download the public Prähofer--Spohn stationary-KPZ
table; `--kpz-table` pins a local copy for offline reproducibility.

## Scientific state and invariants

- Exact microscopic magnetization conservation is never replaced by an
  assumed Burgers current.
- The Markov hydrodynamic state is the infinite set of GHD root densities;
  eliminating them gives a Mori memory kernel for physical magnetization.
- Infinite-temperature commutator algebra fixes the microscopic kernel moments
  through order twenty-six and hence thirteen long-wave Mori--Lanczos
  recurrents.  The
  corresponding normalized structure factor begins with an exact `t^4`
  expansion; the remaining positive terminator carries the continuum spectrum.
- Two explicit positive terminators preserving this entire prefix give
  low-frequency kernels differing by `77.7%--93.4%` at
  `z=(0.1,0.05,0.02)`.  Thus the finite moment prefix is a rigorous constraint,
  not a unique closure of the physical Mori kernel.
- A constant Burgers pair is defined only after fixing the field, projector,
  norm, initial state, lattice, and time window.
- Theory-only calculations must not read Heisenberg trajectories or accept
  target coefficients.  Their JSON certificates record both invariants.
- The controlled `50<t<200` result is an EFT-scale estimate near
  `a_eff≈0.23`, `D_eff≈2`, with projection/truncation uncertainty; the quoted
  trajectory decimals are not claimed as a microscopic theorem.
- A second field is optional.  The next one-field levels are scale-running
  local coefficients and then the nonlocal Mori/TCL generator.
- The apparent quadratic coefficient and diffusion are two coordinates of
  the same normalized linear-response current under the frozen
  `(U**2,-grad U)` projection.  Since the physical current is proportional to
  the wall height, the `U**2` column does not make `a` a second-order Kubo
  vertex; that exact physical vertex is zero by spin flip.  A
  non-gated coarse development run gives orientation-averaged
  `a_current=0.23101` in the full `50:200` window, but it visibly runs downward
  when the window is moved later; this is not a frozen numerical result.
- The registered four amplitude pairs are wired to a target-free `mu->0+`
  certificate.  It extrapolates the conditional current vertex with all
  symmetry-allowed terms through `mu^4`, and separately extrapolates the full
  finite-frequency `delta K1(s;mu)` before applying a weak/Markov scalar
  projection.
- The finite-field dressed-kernel formula and exact off-diagonal contraction
  are implemented.  Although the supplement's Eq. (16) states
  `D_spin=D_diagonal+O(h)`, the new selected-row sequence does not verify that
  order: `h D_cross=(.18432,.19070,.19281)` for
  `h=(.10,.05,.025)`.  Consequently neither the diagonal nor the full
  contraction is currently eligible for a physical constant-`D1` fit.
- Reproducing the supplement's finite-`s_max` curves requires truncating both
  the Eq. (16) numerator and the Eq. (17) susceptibility while retaining the
  infinite dressing tail.  The evaluator now reports that cutoff
  normalization separately and labels it non-physical; it restores the
  published curve scale but does not resolve the non-commuting limits or a
  physical `D1`.
- Expanding the exact symmetric charge-difference square proves that the
  evaluator's cross contraction is the physical off-diagonal term in
  `(mathfrak D C)_spin`; `full = diagonal - cross` is an algebraic identity,
  not a two-mode ansatz.  An early finite-cutoff full value is nevertheless
  not by itself a converged diffusion coefficient.  At fixed `xi_max=3`, lowering `h` from
  `0.2` to `0.05` leaves an artificial `1/h` cross contribution, and at
  `h=0.1` the reported `h D_full` moves from `0.159` to `0.532` as `xi_max`
  changes from `1.5` to `5`.  The later `xi_max=8..12` checks remove the
  dominant tail ambiguity at `h=0.2`, but does not make the cross-cancelled
  sequence eligible for a constant-term extrapolation.  The previous
  `D1=-0.82+-0.12` estimate has been withdrawn.
- The missing analytic operation for the physical constant term is now
  isolated as a matched asymptotic expansion.  With `xi=s*h`, one needs the
  uniform first correction to the dressed diagonal integrand, the
  Euler--Maclaurin boundary term, and the fixed-string inner contribution
  minus its overlap with the giant-string outer solution.  The published
  supplement explicitly discards the required `O(h)` scattering-kernel terms,
  so it fixes `D0` but not `D1`.  The first *bare* giant-kernel correction is
  now derived analytically by Euler--Maclaurin:
  `T1=-(2/pi)[a/(a^2+4u^2)+b/(b^2+4u^2)]`, with
  `a=abs(xi-zeta), b=xi+zeta`; exact discrete sums converge to it under four
  successive field halvings.  The leading/first coefficients of the scaled
  filling, dressed magnetization, total density, dressed energy derivative,
  and effective velocity are also explicit, and the first dressed kernel
  obeys a linear resolvent equation rather than a new nonlinear TBA problem.
  Fourier transformation in scaled rapidity reduces its leading operator to
  the exactly solvable half-line Poschl--Teller Green function
  `[-d_xi^2+(|k|/2)^2+2*csch(xi)^2] X0=2 delta`.  The corrected XXX sign is
  `X=T-T*N*X`; the formerly written plus-sign resolvent was wrong.  The closed
  `X0` and one-dimensional Nystrom `X1` now pass direct Fredholm residual and
  cutoff/order tests, so the outer dressed-kernel subproblem is closed.
  The complete pointwise first diagonal integrand is also assembled from the
  left weight, partner weight, absolute-velocity derivative, and `2*X0*X1`
  term; field-halving tests verify the product expansion.  No `O(h)` hole
  factor is missing because `1-n=1+O(h^2)` in the giant sector.
  The first shared-FFT outer audit was not converged: both nominal schemes
  fixed `du=.125`, whereas the small-string boundary layer has width
  `u=O(xi)`.  Halving `du` at `eta=.05` changes the diagonal leading value
  from `.628861` to `.682792`, so that artifact is now explicitly
  superseded.  The replacement integrates thermodynamics in an adaptive
  `u/xi` coordinate and uses geometric `xi` panels.  For
  `eta=(.10,.05,.025)` it gives diagonal leading
  `(.700038,.729225,.744812)`, cross leading
  `(.200230,.200352,.200366)`, and full leading
  `(.499808,.528872,.544446)`.  An independent low-memory selected-row
  evaluator reproduces the complete finite matrix contractions to `0.3%` and
  finds a fixed-`s=1` field exponent `1.9973`; finite small strings therefore
  vanish while the joint `xi,u -> 0` layer remains.
  The supplement's regulated measure
  `int[d xi]_h f=int dxi f-(h/2)lim_(xi->0)f` is the missing quantum boundary
  operation.  It vanishes for the filling equation but is explicitly needed
  for density dressing.  Until its contribution to the full contraction is
  derived, neither Eq. (16), the existence of a pure constant `D1`, nor a
  numerical `D1` is certified.  See
  `docs/iterated_full_diffusion_limit_audit.json`.
- Direct quadrature of the controlled giant-string expression now reproduces
  `5*pi/27` to `1.3e-13` relative error.  Treating the analytic spectral
  regulator only as a candidate first scale correction gives
  `delta K1=-0.264...-0.278` on `s=0.5...2` and the no-trajectory restricted
  projection band `a=0.23363+-0.02006`, `D=2.02636+-0.20250`.  The candidate
  agrees numerically with the coarse finite-time kernel but is not promoted to
  the physical full-diffusion `D1`.

## External state and risks

The first trace-pairing pilot is now frozen and rejected.  All twelve P1/P2/P4
tasks completed with zero exit code and less than 357 MiB batch RSS, but the
paired endpoint audit rejects both P2 and P4: their mean shifts from P1 are
`0.002401/0.000901` and `0.002641/0.001141` (shift/SEM), respectively.  The
machine-readable verdict is
`docs/scnet_full_matrix_trace_pairing_variance_audit_20260816.json`; partial
pairing counts must not be used for the five-field calculation.

A separate target-free P1 versus complete P8 experiment was frozen before its
candidate outputs and submitted as Slurm array `23323335`, run
`full_matrix_complete_pairing_pilot_20260816_001`.  For eight x and eight y
probes, eight cyclic shifts enumerate all 64 ordered pairs, so P8 is the exact
conditional pairing average rather than another selected partial pairing.
If its paired mean/variance gate fails, the frozen fallback is high-replicate
P1; no further pairing count will be tried.  These outputs also contain the
new complete colored continuity memory.

The microscopic splice no longer normalizes that colored memory and declares
it to be a deep Lanczos terminator.  The complete F-GHD structure factor is
first inverted at the physical top level,
`K=(1/Ftilde-z)/khat^2`; the finite-k `mu16` prefix is then peeled from this
absolute kernel, and only the remainder is projected onto a positive
continuum.  This removes an otherwise arbitrary amplitude matching scheme.

The remote SCNet team root is authoritative for convergence/production gates.
As of 2026-08-16, six of twelve convergence jobs have final outputs and six
ended at their time limit with checkpoints.  The authoritative controller
`23190354` is visible under the original `acamtw70yu` identity and is pending
with reason `AssocGrpJobsLimit`; it must not be duplicated.  No Production A/B
work may be inferred from local files or resubmitted outside the frozen
controller policy.

The 2026-08-16 read-only scheduler audit shows the `acamtw70yu/giggleliu`
association with `GrpJobs=0` and `GrpSubmit=0`.  Both the authoritative
controller and an unrelated 24-task array are pending for
`AssocGrpJobsLimit`; there are no running jobs under this user.  This is an
external association-capacity block, not a missing checkpoint or code error,
and does not authorize migration or duplicate submission.

The main unresolved analytic object is the finite-time correction to the
universal KPZ shape, equivalently the finite-scale GHD/Mori kernel.  Existing
microscopic theory fixes the leading giant-string coefficient but does not
uniquely determine the trajectory-level decimals `0.2301488, 1.97`.

The complete non-diagonal diffusion/noise operator has now also been put in a
physical-spin basis without selecting a second mode.  For the regulator
sequence `h=1/4,1/8,1/12` at fixed `xi_max=3`, `|u|<=6`, `du=0.5`, the scaled
spin block `h D_mm` is `0.27133,0.28855,0.29281`, while the scaled coupling to
the *entire* orthogonal sector is larger:
`h ||D_perp,m||=0.36245,0.37455,0.38268`.  FDT residuals are below `5e-16`.
Exact Schur elimination gives a frequency-dependent Mori correction that
changes sign across this field sequence, so neither a scalar Markov correction
nor one auxiliary pole is justified by the microscopic operator.

This is not yet an accepted infinite-mode limit.  At `h=1/8`, changing
`xi_max=2,3,4,6` moves `h D_mm=0.2359,0.2886,0.3083,0.3159`; changing
`u_max=4,6,8,12` moves it `0.3073,0.2886,0.2792,0.2699`; halving `du` moves it
to `0.3777`.  The failure is localized to the regulated `xi->0` boundary layer:
fixed rapidity spacing cannot simultaneously resolve finite strings and the
`s~1/h` giant sector.  A matched small-string/giant-continuum discretization
and microscopic Mori contact matching are required.  The certificate therefore
sets `infinite_mode_limit_accepted=false` rather than reporting a fitted
finite-window `a,D`.

A string-adaptive rapidity quadrature now removes the main uniform-`u` boundary
artifact.  It integrates each string in `theta=s*r` with a sinh-mapped
Gauss--Legendre rule while retaining all small--giant dressed-scattering
blocks.  At `h=1/8`, increasing `xi_max=2,3,4,5,6` moves the captured
susceptibility monotonically through
`0.16327,0.21809,0.23686,0.24174,0.24282` toward the exact `0.246134`; the
`xi_max=8,R=20` calculation captures `99.26%`.  The matched full-operator
sequence gives `hD_mm=0.43474,0.48183,0.50499,0.51871,0.52780,0.53891` at
`h=1/4,1/6,1/8,1/10,1/12,1/16`.  Polynomial and `h log h` schemes extrapolate
to `0.57049..0.57419`, still `1.2..1.9%` below `5*pi/27`.  The declared 1%
leading gate therefore remains false.  More importantly, this is the full
finite-cutoff diagonal-minus-cross spin block, whereas Eq. (16) of the source
supplement defines the physical constant term from the diagonal contraction
only after the infinite-string limit.  The finite-cutoff cross block retains
a spurious `1/h` piece, so this sequence is ineligible for `D1` even if its
leading numerical gate were to pass.  Static normalization is controlled, but
the required order of limits is not.

A stricter nested audit now separates the rapidity-node limit from the field
limit at fixed `(xi_max,R,alpha,kernel_step)=(6,20,4,1)`.  For each of
`h=(1/20,1/16,1/12,1/10,1/8)`, the `N_node=(32,40,48)` data are extrapolated
with `N_node^{-p}`, `p=2,3,4`, before fitting in `h`.  The resulting zero-field
intercepts span `0.55027..0.55952`, so the worst discrepancy from
`5*pi/27=0.5817764` is `5.41%`, despite every susceptibility capture exceeding
`99.14%`.  The exact-leading 1% gate fails.  Fits that forcibly subtract the
exact leading term produce only an ineligible diagnostic range
`D1=-1.176..-0.742`; this range is explicitly not a physical error bar.  The
machine-readable rejection is
`docs/adaptive_node_field_limit_audit.json`.

An independent tail audit shows that the main bias in the preceding sequence
was the scaled-rapidity extent rather than `xi_max` or dressed-kernel spacing.
At `h=.05,N=32`, changing `xi_max=6->8` moves `hD` by only `0.047%`, and
halving the kernel step moves it by `0.031%`.  Fixed-node `R` growth is not a
limit, but the approximately fixed-density path `(R,N)=(20,32),(24,40),
(28,48)` stabilizes at `hD=.54574,.54475,.54415`.  Recomputing all five fields
at `(R,N)=(28,48)`, including `h=1/25`, gives a stable rejected sequence.  The
fine-kernel dense run at `h=1/30` exceeded memory, but the coarse-kernel run
succeeded.  Matched coarse/fine pairs at `h=.04,.05` give
`(y_coarse-y_fine)/h^2=.287385,.284011`, so the inferred fine-kernel value is
`hD=.55315008+-.00000187` at `h=1/30`.  Adding it gives the zero-field scheme
envelope `0.570678..0.571505`, still `1.77..1.91%` below `5*pi/27` and outside
the declared 1% gate.  Forcing the exact intercept gives diagnostic
`D1=-.6641` (linear) and `-.8412` (quadratic), neither eligible as a physical
interval.  Extending the balanced coarse-kernel path from `(R,N)=(28,48)` to
`(32,56)` moves the `h=.05` result by only `-0.0765%`; the remaining bias is
not explained by the measured kernel-step or one-step tail errors.  Applying
the same field grid and fit family to the closed spectral regulator recovers
its exact leading limit to `3.44e-7` relative error, excluding a generic fit
failure.  A separate `Delta xi_buffer=1.5..9` sweep changes the test value by
only `2.5e-6` relative, excluding the remote string boundary.  The
machine-readable rejection is
`docs/adaptive_mixed_kernel_step_zero_field_audit.json`; further progress needs
a continuous/matrix-free *diagonal* contraction and an inner--giant matched
expansion rather than blind dense growth.

A dense finite-cutoff implementation of the complete occupation-space
diffusion operator is now available in
`scripts/evaluate_full_tba_diffusion.py::full_diffusion_operator_field`.
It retains all off-diagonal string/rapidity pairs and constructs the FDT noise
covariance.  `scripts/derive_full_mode_linear_ghd.py` propagates this operator
and projects it back to the spin structure factor; the 192-mode smoke report
has zero FDT identity residual and a noise minimum eigenvalue of
`-3.5e-12`.  `scripts/propagate_full_mode_fluctuating_ghd.py` now also
propagates the complete microscopic vertex `delta v_i^eff/delta n_j`, uses
exact FDT OU increments, a dealiased quadratic step, paired linear controls,
antithetic paths, and includes the quadratic dressed-spin observable Hessian.
The 48-mode three-string run detects finite-time shape
corrections of order `1e-3--1e-2`; the 96-mode six-string run is not yet
  statistically or coarse-graining converged.  State derivatives of
diffusion/noise and the deterministic mixed dynamical-observable contractions
are now available analytically.  The Itô multiplicative-noise--observable
`B' H` contact is also evaluated as a causal one-time contraction, including
both observable-leg placements.  At Fourier cutoff 8 it runs from `+0.00350`
at `t=1` to `-0.02035` at `t=25` and `-0.12391` at `t=200`; cutoffs 12 and 16
show substantial short/intermediate-time drift.  Thus all finite-cutoff
quadratic diagrams are present.  The exact second Frechet derivative of the
dressed effective velocity is also implemented.  Its one-cubic-vertex
two-point contribution is entirely an equilibrium Wick tadpole,
`delta_v_A=W_A,BC C_BC/(2 dx)`; an explicit normal-ordering counterterm cancels
it mode by mode.  At Fourier cutoffs 8,12,16 the bare tadpole L2 norms are
`1.15075,1.72612,2.30149`, while the retained cancellation residual is zero.
The diagonal second Frechet derivatives of the full non-diagonal diffusion,
static covariance and FDT noise have now also been propagated analytically as
second-order dressing jets.  The second derivative of the symmetric noise root
solves `B d2B+d2B B=d2Q-2 dB dB`, with maximum residual `4.5e-14`.  The resulting
one-cubic-vertex diffusion/noise tadpoles are retained together with their
equal and opposite Wick-ordering counterterms; the separate `B'B'` loop remains
in the physical quadratic correction.  Multi-cubic diagrams, microscopic
Mori UV matching, higher vertices, and the joint zero-field renormalization remain
before a physical `F1_perp` can be claimed.  No two-mode closure is assumed.
The first genuine two-cubic-velocity contribution is no longer only formal:
the fully symmetric `J_IJK` vertex and all six cross-time Wick pairings are
contracted deterministically.  A 16-mode one-string smoke certificate gives
The Fourier spacing is fixed, so the physical cell length is correctly held
at `2*pi/Delta k`, rather than spuriously divided by the number of retained
modes.  After removing the resulting artificial `N_x^2` enhancement, the
integrated continuity memories at cutoffs 4,6,8,10,12,16,20,24 are
`(0.0959,0.2582,0.3744,0.4698,0.5402,0.6571,0.7803,0.9073)e-3`.
The sequence has no UV plateau and is not promoted to the zero-field physical
correction.
Two additional Fourier cutoffs, 20 and 24, raise the bare colored-kernel
integral to `28.53` and `50.56`.  A local Mori-EFT subtraction through orders
0--4 about `z0=.5` was tested simultaneously at `z=.1,.2`.  Order 2 stabilizes
only `z=.2` (last-cutoff change `4.89%`) but fails at `z=.1` (`24.0%`); no
single order passes both frequencies at 10%.  Thus a finite contact basis is
not accepted as the UV match, and the frequency-dependent microscopic
continuum cannot yet be replaced by a fitted local constant.  The rejection
is frozen in `docs/mori_uv_local_counterterm_audit.json`.

The finite-cutoff linear stochastic tier now has a sampling-free certificate.
For each `k`, the covariance is propagated exactly as
`Sigma(t)=C+exp(Lt)[Sigma(0)-C]exp(L^dagger t)`, while the physical-spin
resolvent gives `Ktilde=(1/Ftilde-z)/khat^2` without choosing a basis for the
eliminated modes.  In the 48-mode certificate the equilibrium covariance is
stationary to machine precision, accumulated noise covariances are positive,
and the Mori resolvent identity has residual `2.2e-16`.  At `h=0.25`, its real
low-frequency kernel lies inside the exact nine-recurrent zero-field moment
interval for `z<=0.1`; high-frequency disagreement is expected because a
hydrodynamic generator does not reproduce microscopic short-time moments.

A weak local magnetic GGE wall has the exact linear-response tangent
`delta u_A(x)=C_AB p_B h(x)`, hence zero static-metric orthogonal fraction at
`O(h)`.  Finite-amplitude local-GGE curvature, non-local-GGE initial slip, and
nonlinear generation of orthogonal modes remain separate errors.

At the symmetric XXX point this tangent is singular in any fixed finite-string
occupation basis.  The exact infinite-temperature fillings
`n_s(h)=[sinh(h)/sinh((s+1)h)]^2` are even in `h`, so opposite walls have
identical occupations and every fixed string has zero linear derivative at
`h=0`, despite nonzero physical susceptibility.  A finite-string cutoff thus
captures zero of the signed linear spin weight; the missing fraction is one.
The complete local-GGE coordinate must be augmented by a signed SU(2)
orientation/giant-string boundary variable:
`n_s(x)=n_s(|h(x)|), sigma(x)=sign(h(x))`.  This closes the linear mapping for
a smooth magnetic GGE, with gradient remainder `O(a/L_wall)`, but a sharp
product wall still has an uncontrolled microscopic initial slip.
For the registered amplitudes `0.02,0.05,0.10,0.20`, the crossover string
scales are `50,20,10,5`; hence a 3- or 6-string occupation calculation cannot
encode the sign of the weakest walls even if its trajectory sampling error is
small.

The sharp product-wall initial condition is separately closed at linear Mori
order.  Its opposite-orientation density matrix difference divided by
`2*mu` starts exactly with `sum_j f_j S_j^z`, which lies in the retained
physical spin-density Fourier subspace.  Hence the linear Mori initial-slip
source is zero without requiring a smooth wall.  Pairing orientations and
fitting the normalized response through `mu^4` leaves `O(mu_max^6)`; for
`mu_max=0.2` the bare power is `6.4e-5`, with its coefficient monitored by
scheme and leave-one-amplitude-out checks.

The analytic certificate now also evaluates the Gaussian one-loop Mori
memory generated by the exact dressed-velocity vertex.  The `O(V)` correction
to a two-point function vanishes by Gaussian parity, while the first nonzero
term is the deterministic Wick contraction `O(V^2)`.  For the current
`h=0.25`, 48-mode, `k=0.04` cutoff, its continuity-normalized real memory is
`0.1431, 0.1136, 0.06691, 0.006296, -0.004517` at
`t=1,5,10,25,50`.  This supplies an analytic mechanism for a good short
Markov/Burgers window followed by running coefficients and a sign-changing
memory tail.  The bare accumulated diffusion correction is not UV converged:
at Fourier cutoffs `8,12,16` its `t=50` values are `1.355,2.494,4.048`.
Accordingly it is a component of, not a prediction for, physical `F1_perp`;
microscopic Mori matching and the other same-loop-order vertices are required.

The state-dependent vertices are no longer merely listed as omissions.  Exact
Frechet differentiation of the dressed diffusion/noise operator and a
Sylvester solve for the symmetric FDT noise root give all currently known
quadratic bare vertices.  At `h=0.25`, 48 modes, and `t<=50`, Fourier cutoffs
`8,12,16` give integrated `(velocity,diffusion,cross)` memories
`(1.356,1.257,~0)`, `(2.497,4.526,~0)`, and
`(4.060,11.850,~0)`; the white multiplicative-noise contact coefficients are
`16.831,25.247,33.662`.  The root-derivative residual is `6.5e-15`.  Thus the
diffusion/noise terms are quantitatively non-negligible and more UV divergent,
not a small correction to the velocity loop.  The deterministic mixed
`Gamma H` diagrams are now evaluated by a normal-ordered Duhamel--Wick
contraction.  At `t=1,5,10,25,50`, their total shape correction is
`(.0167,.0543,.0786,.1226,.1228)` for 8 Fourier points and grows to
`(.0871,.2041,.2921,.4044,.3244)` for 16 points.  Halving the time-integration
step changes the 8-point result by `0.97%` at `t=1` and `0.18%` at `t=50`, so
the larger drift is a UV rather than time-quadrature effect.  This closes that calculable
quadratic-observable term but confirms its bare UV dependence.
An independent 8-point extension gives mixed corrections
`0.12282,0.04814,0.03852,0.06868` at `t=50,100,150,200`; the non-monotone
tail cannot be represented by a permanent constant shift.  It remains a
finite-field/cutoff certificate, not a zero-field prediction.
Multiplicative-noise/observable contacts, cubic-vertex
tadpoles/counterterms, microscopic Mori matching, and the joint
zero-field/infinite-string limit still prevent a physical `F1_perp` claim.

The loop-momentum discretization is separately controlled at fixed
hydrodynamic UV cutoff.  Holding `|p|max=0.16` and reducing the momentum
spacing from `0.04` to `0.005` gives accumulated `t=50` values
`1.3553,1.4212,1.4572,1.4757`.  Thus the finite-cutoff integral converges with
volume; the unresolved operation is UV matching to microscopic dynamics, not
the Fourier quadrature.

The one-loop memory is now propagated into an observable structure-factor
correction using the perturbative Mori--Dyson identity
`delta Ftilde=-khat^2 Ftilde0^2 delta Ktilde`.  At the same finite cutoff,
`delta F_V` is `-1.17e-4,-0.00276,-0.00993,-0.04047,-0.07677` at
`t=1,5,10,25,50`.  Thus the dressed-velocity nonlinearity is almost invisible
at very short times and accumulates into a non-dilational late-window shape
shift.  These values still inherit the unresolved UV matching.

Projecting the same operator onto the weak magnetic tangent gives the
well-defined Galerkin coordinates `c=-5.78e-4`, `D=0.29509`, and
`A=0.01396` at this finite field.  Their advective, diffusive, and nonlinear
orthogonal fractions are `0.999999`, `0.83499`, and `0.999888`, so the scalar
subspace is not invariant and these numbers are not controlled scalar
transport coefficients.  Spin flip further enforces physical `A(h=0)=0`;
the one-sided conditional normal-mode coefficient is a separate projection.

The quadratic dressed-spin observable is now contracted analytically as
well.  Its linear--quadratic cross term vanishes by Gaussian parity and the
first contribution is the deterministic `H^2` Wick contraction.  At the
current finite cutoff its zero-time weight is `0.4182` relative to the linear
susceptibility.  After static renormalization, the shape shifts at
`t=10,25,50` are `-0.0877,-0.1305,-0.1039`.  This demonstrates that a linear
spin projection can miss a larger finite-window distortion than the isolated
velocity vertex.  The bare magnitude remains cell/coarse-graining dependent;
the deterministic mixed `Gamma H` and stochastic `B' H` observable-contact
diagrams are now included as described above, while cubic counterterms and
microscopic contact matching remain unresolved.

The joint zero-field audit is currently fail-closed and now respects the
order statement in Eq. (16).  The cross-cancelled sequence approaches
`5*pi/27`, but is ineligible for `D1`; its old `[-0.792,-0.377]` envelope is
marked withdrawn.  The eligible diagonal sequence after the available
velocity extrapolations is `hD=0.66488,0.68672,0.71314,0.72611` at
`h=0.20,0.15,0.10,0.075`, which moves away from `D0`, has a maximum known
regulator error of about `3.53%`, and a nested `D1` scheme spread of `3.57`.
Thus the current calculation supplies no physical `D1` interval at all.

The leading giant-string tail is now analytically bounded rather than inferred
from a second cutoff.  Bounding the exact `D0` integrand by a cubic polynomial
times `exp(-2 xi)` gives omitted tails `2.21e-5` at `xi=8` and `2.26e-8` at
`xi=12`, so the leading `5*pi/27` string tail is controlled.  This bound does
not include the finite-field dressed kernel or off-diagonal contraction and
therefore does not certify the physical `D1`; the audit intentionally keeps
those regulator entries missing.

The exact Pauli-string expansion now fixes long-wave Mori moments through
`mu26` and thirteen positive Lanczos recurrents.  A translation-orbit
Gaussian-integer chain eliminates finite-ring accumulation error; it corrects
`mu22` to `6735689494485335/4194304` and obtains exact `mu24` and `mu26` without
trajectory data.  Peeling the known
finite-momentum layers from the leading KPZ kernel
and the explicitly labelled spectral-scale correction gives positive
terminators throughout `L=400`, modes 1--4, and `50<=t<=200`; the candidate
subleading kernel is 6.8--11.3% below the leading kernel.  Moment-only
Stieltjes bounds remain too wide to determine the perpendicular shape
correction.

The exact off-diagonal charge-difference contraction of the finite-field TBA
matrix has also been evaluated.  At `h=0.2` it is stable under velocity-series
(`150..600`) and string-tail (`h*smax=8..12`) checks.  The finite-cutoff full
sequence gives `hD=0.46012,0.48762,0.51472` at `h=0.2,0.15,0.1`, but this
apparent approach to `5*pi/27` results from a cross term that has the wrong
finite-cutoff scaling.  It is retained as a noncommuting-limit diagnostic,
not as evidence for a constant `D1` or a unique `F1`.

The adaptive infinite-mode linear fluctuating-GHD regulator now has a
complement-free Krylov path.  It propagates the complete non-diagonal
whitened `A,D,Q` operators and computes the exact scalar Mori resolvent
`e_m^T(z-L)^-1e_m`, algebraically equal to eliminating the entire orthogonal
sector without a finite-pole closure.  The full FDT noise contribution to the
equal-time covariance is also propagated through the exact Lyapunov identity.
At fixed giant-string variables `q=k/h^2=2.56`, `p=z/h^3`, and `tau=t*h^3`, a
768--2336-mode sequence captures 99.11--99.17% of the finite-field
susceptibility.  The scaled orthogonal memory converges to approximately
`0.20831,0.16500,0.12125` at `p=2.56,5.12,10.24`.  A nine-frequency audit
finds relative L2 errors 35.0% (constant), 2.27% (one positive pole), 0.737%
(contact plus one pole), and 0.0169% (two positive poles).  Hence a two-mode
closure may approximate this window but is neither imposed nor exact.  The
same joint-scaled total kernel has now been peeled through prefixes of 10--13
exact XXX Mori--Lanczos recurrents without choosing a pole terminator.  Every
input lies inside its exact finite-moment Stieltjes interval, each terminator
is positive, and continued-fraction reconstruction returns the input kernel.
The low-frequency last-step drift alternates between about `2.1%`, `44.4%`,
`2.3%`, and `44.4%` for the `mu20`, `mu22`, `mu24`, and `mu26` prefixes.
This strong prefix-parity sensitivity excludes interpreting the apparently
small 10- or 12-level drift as convergence.  See
`docs/joint_scaled_microscopic_terminator_audit_mu20.json` through
`docs/joint_scaled_microscopic_terminator_audit_mu26.json`.  The
remaining obstacle is the joint zero-field resummation and Mori/UV matching
of state-dependent velocity, diffusion, multiplicative-noise, and observable
vertices; the linear certificate alone does not determine physical `F1_perp`
or the unique `(a,D)` pair.

The first positive-continuum matching audit has now been applied to the
complete known one-loop diagrams at `h=0.25`.  The bare multiplicative-noise
contact grows as `8.416,12.623,16.831` for 8, 12, and 16 Fourier points, and the
colored loop grows with it.  The resulting total kernels lie outside the exact
moment interval at every sampled Laplace frequency; the finest-pair maximum
relative drift is `45.7%`.  Consequently
`docs/matched_infinite_mode_mori_h025.json` sets both continuum matching and
`physical_F1_perp` false.  The wall gate in
`docs/matched_full_mode_wall_50_200.json` emits no `(a,D)`.  This identifies a
microscopic contact-renormalization problem, not evidence for a second field.

Prefix-depth stability is now explicitly falsified through `mu26`.  On the
same joint-scaled linear full-mode kernel and frozen low-frequency window, the
last-field-step scaled-terminator changes are `2.103%, 44.404%, 2.331%,
44.363%` after 10, 11, 12, and 13 exact recurrents.  Every source kernel stays
inside its corresponding Stieltjes interval and every peeled terminator is
positive, so the alternation is a finite-Jacobi-prefix effect rather than a
positivity failure.  No finite prefix presently determines the finite-window
continuum spectrum or a unique `(a,D)` pair.

The quadratic full-mode loop now also has a consistent unit-lattice
Brillouin-zone option: the signed `2*sin(k/2)` symbol is used inside every
linear propagator and velocity/diffusion/noise vertex, rather than only in the
final continuity normalization.  At fixed external `k=pi/16`, the `N=32` and
`N=64` bare kernels agree at the `2e-4` level, so the former Fourier-cutoff
drift has been separated from spatial quadrature error.  The converged bare
contact is nevertheless of order `10^3`, far outside the exact XXX Mori
moment interval.  A `mu20`-preserving exponential-jet subtraction is strongly
matching-rate dependent and never restores a positive admissible kernel.
This leaves microscopic no-double-counting/contact matching, not an optional
second pole, as the nonlinear bottleneck.  The target-free linear
self-consistent wall calculation has also been extended through 64 nodes per
string.  The last two results are `(a,D)=(0.214111,2.311431)` at 56 nodes and
`(0.213137,2.293300)` at 64 nodes in `50<t<200`; the FDT residual stays below
`1.6e-16`.  This sequence does not converge to the trajectory pair and hence
proves that complete linear `A,D,Q` propagation alone is insufficient.

The microscopic side of the matching is now fixed directly from the XXX
bond current.  Sparse Pauli algebra proves
`[H,Sz_k]=-2*sin(k/2)*j_bond,k` with zero operator residual for `L=400`, modes
1--4, and gives `chi=1/4`, `||j_k||^2=1/8`, hence the exact kernel norm
`K(k,0)=mu0=1/2`.  This identity fixes only the external bond-divergence
symbol, not every internal GHD loop momentum.  A necessary Kubo projector
bound is therefore `0<=K_Pj(0)<=1/2`; the cell-scale Brillouin GHD loop gives
`3824.39--3825.09`, violating it by factors `7649--7650`.  The bare loop is
not an orthogonal microscopic slow component and cannot be added to the exact
Mori kernel.  The next required operation is an explicit Kubo-orthogonal
`j=P_slow j+Q_slow j` spectral split.  See
`docs/xxx_bond_current_mori_matching_L400.json` and
`docs/bond_current_fghd_projector_bound_audit.json`.

The required Kubo-orthogonal static split has now also been constructed
without a Gaussian cell approximation.  The exact momentum-bilinear Gram
matrix includes the on-site four-spin quantum cumulant and projects
`j_k=sum_p B_p` onto the subspace in which both spin legs are below a declared
cutoff.  At `L=400`, `k=2*pi/L`, the Gram matrix is positive semidefinite,
the full current norm is exactly `1/8`, and every cutoff gives a positive
identity `K_P(0)+K_Q(0)=1/2` with zero reported residual.  The slow-current
fractions are `0.0418%, 0.3323%, 2.5616%, 17.5986%` at cutoffs
`0.12566, 0.25133, 0.50265, 1.00531`; at small cutoff the fraction scales as
approximately `(2/(3*pi))*Lambda^3`.  Thus the long-wave sector has small
static weight but can dominate late times through a divergent lifetime.  The
full non-diagonal F-GHD continuum must be normalized inside this bounded
slow weight, while the exact orthogonal Mori spectrum carries the remainder.
See `docs/xxx_slow_current_projector_L400_k1.json`.  Dynamical `PLP/QLQ`
matrix elements, not the static split, are now the missing microscopic input.

The first dynamical matrices of that split are now exact as well.  Sparse
Pauli algebra evaluates `G0=(B,B)`, `G1=(B,L B)`, and `G2=(L B,L B)`, then
separates the norm of `L Pj` into positive `P L Pj` and `Q L Pj` pieces.  At
fixed physical cutoff `Lambda=pi/4`, the fraction retained inside the
two-spin bilinear space is `2.7925%, 1.2765%, 0.7255%` for `L=16,24,32`, with
a fitted `L^-1.944` decay.  At `Lambda=pi/2` it is `5.4749%, 2.5510%,
1.4598%`, fitted as `L^-1.905`; the largest generalized `PLP` frequency also
scales as `L^-1`.  Thus the thermodynamic slow-bilinear space is strongly
non-closed: nearly all of its first Liouvillian image enters the three-spin
and higher `Q` continuum.  A finite extra-field closure can only approximate
the resulting `P L Q (z-Q L Q)^-1 Q L P` self-energy.  Sources are
`docs/xxx_slow_current_dynamics_L16_k1.json` through `L32` and
`docs/xxx_slow_current_dynamics_scaling_audit.json`.  The next missing object
is the frequency-resolved `Q L Q` positive spectrum matched simultaneously
to the exact `mu26` prefix and the infinite-mode F-GHD low-frequency limit.

That `QLQ` spectrum now has its first directly projected microscopic Lanczos
prefix.  At fixed `Lambda=pi/4`, the positive squared recurrents for
`L=16,24,32` are `(1.01183,1.95235,3.46548)`,
`(1.14055,1.98035,3.71276)`, and `(1.18923,1.98716,3.80221)`; `L=40,48`
extend the first two to `(1.21237,1.98970)` and `(1.22509,1.99090)`. Every Lanczos
diagonal vanishes and the maximum re-projection residual is below `3e-17`.
Linear/quadratic `1/L` extrapolation envelopes contain the candidate limits
2 and 4 for the second and third recurrents.  The first envelope
`[1.26515,1.34346]` does not yet contain `5/4`.  A symmetry-motivated but not
yet certified `1/L^2` diagnostic gives `1.249858` and `1.997396` for the first
two limits, within `0.0114%` and `0.130%` of `5/4` and 2.  No exact simple
sequence is claimed until the cutoff endpoint correction is derived.  This
is the first finite Jacobi prefix of the actual
`Q L Q` continuum seen by `Q L Pj`, rather than the prefix of the unprojected
total current.  See `docs/xxx_qlq_lanczos_scaling_audit.json`.  The remaining
terminator must now be constrained by the joint-scaled infinite-mode F-GHD
low-frequency kernel before any finite-window `(a,D)` can be emitted.

The first projected `QLQ` recurrent no longer requires a finite-ring
extrapolation.  In the thermodynamic translation-orbit basis the slow
projector is exactly the half-line sine-band projector.  This gives
`||P_Lambda j||^2=(1/8)(Lambda-sin(2 Lambda)/2)/pi`, proving the earlier
`2 Lambda^3/(3 pi)` small-cutoff law.  The banded Pauli matrices for `L O_r`
and `L^2 O_r` can then be sine-diagonalized with three explicit boundary
corrections.  At `Lambda=pi/4` the exact quadratures give
`||QLPj||^2=0.0027039745556968315`,
`||QLQLPj||^2=0.003391874529051187`, and therefore
`beta_Q,1^2=1.2544032716229014`.  It differs from `5/4` by `0.3523%`, so the
simple candidate is not exact for this projector.  The finite-tail `R=128`
calculation gives `(1.2562814,2.0037436,3.9636950)` and approaches the exact
first value from above.  See `scripts/derive_xxx_thermodynamic_qlq.py` and
`docs/xxx_thermodynamic_qlq_pi4_R128.json`.

The complete non-diagonal F-GHD noise has now also been propagated directly,
instead of being inferred only from the scalar FDT identity.  In the whitened
occupation basis the code evaluates
`khat^2 integral v(s)^dagger Q v(s) ds` with the full dense `Q` at every
Gauss--Legendre node and independently compares it with
`1-||exp(L^dagger t)e_m||^2`.  An adaptive-rapidity regulator sequence at
`h=(1/4,1/8,1/12)` contains `(512,1024,1536)` modes, captures
`(96.41%,95.99%,95.80%)` of the exact static susceptibility, and has maximum
direct-noise/FDT discrepancies below `3.2e-15`.  At `t=200` the off-diagonal
part of `Q` contributes `(-23.85%,-32.34%,-36.31%)` of the full projected
noise covariance, so a diagonal-noise approximation is quantitatively wrong.
The corresponding `h D_mm` values are `(0.42386,0.49485,0.51773)`: the
operator coefficient itself runs as the zero-field regulator is removed and
does not become the finite-window surrogate `D=1.97`.  The audit accepts the
finite-regulator full `A,D,Q` propagation but deliberately does not accept the
joint zero-field infinite-mode limit or emit a unique `(a,D)`, because the
string, rapidity, node, wave-number, and nonlinear magnetic-boundary tails
have not yet been varied independently.  See
`docs/direct_full_noise_fghd_regulator_audit.json` and
`scripts/audit_direct_full_noise_fghd.py`.

A target-free first-order propagation of a constant regular Mori term has now
also been completed.  Resolvent perturbation gives
`delta S=-d*khat^2*(S0 convolution S0)` with `S0` constructed only from the
stationary KPZ table and the TBA KPZ scale.  The spectral-regulator diagnostic
`d=-2/(3*pi)` moves the frozen weak pair from `(0.212228,2.221207)` to
`(0.212834,2.034906)`; halving `dt` gives `(0.212767,2.035557)`.  A strength
sweep `d=(-0.1,-0.3,-0.5)` gives
`a=(0.21220,0.21363,0.21588)` while
`D=(2.13244,1.96143,1.80617)`.  Thus a constant regular kernel can account for
the finite-window diffusion scale near `1.97` but cannot generate the observed
nonlinear projection near `0.230`.  The missing correction must retain the
frequency-dependent `delta K_1(s)`, or equivalently the nontrivial `F1(u)` / QLQ
continuum shape.  The value `-2/(3*pi)` remains a regulator diagnostic rather
than a certified physical finite part.  See
`docs/regular_mori_kernel_strength_audit.json` and
`scripts/derive_regular_mori_wall_correction.py`.

The thermodynamic projected `QLQ` chain has now been extended from three to
five recurrents.  The regulator envelopes are
`b_Q^2=(1.25440327 exact, [1.992233,1.992551],
[3.920982,3.921946], [4.948503,4.950790],
[6.342357,6.344682])`; in particular the fourth limit is not 5.  Continuity,
the KPZ table second moment `m2=0.5105231821`, and the exact slow-current norm
fix the absolute boundary
`R_Q(z)~0.2618273693*z^(1/3)` or
`rho_Q(omega)~0.1443529943*omega^(1/3)`.  A pole-count-free positive-measure
linear program imposing this low-frequency tail and all five recurrents still
allows `R_Q(0.005)` in `[0.04436,0.96341]`; adding the fifth recurrent reduces
the maximum relative interval width only from `1.9256` to `1.9155`.  Thus a
few more short-time moments cannot determine the `t=50..200` kernel.  The next
effective input must be a frequency-resolved microscopic or complete
infinite-mode F-GHD continuum.  See
`docs/qlq_positive_spectral_interval_steps5.json` and
`scripts/audit_qlq_positive_spectral_interval.py`.

The order of limits in the complete linear infinite-mode `A,D,Q` theory has
also been audited on fixed KPZ rays `r=(z/h^3)/(k/h^2)^(3/2)`.  At
`h=(0.1,1/12)` and `q=k/h^2` through `10.24`, the full pole-free Schur solve
shows that `p^(1/3) h K_bare = r^(1/3) q^(1/2) hD/2`: increasing
`q=5.12->10.24` gives the predicted `sqrt(2)` growth to `1.5e-8` relative
accuracy.  The orthogonal linear memory simultaneously falls to
`(0.36,0.32,0.29)` of its former amplitude on rays `(0.5,1,2)`.  Hence the
finite-field linear Navier--Stokes operator has no uniform zero-field KPZ
limit: its bare diffusion diverges and its orthogonal linear memory vanishes.
Complete non-diagonal `A,D,Q` is necessary at each regulator but cannot supply
the zero-field finite-time `F1`; dynamic giant-string cutoff and nonlinear
fluctuation resummation must precede microscopic QLQ matching.  See
`docs/kpz_ray_linear_fghd_order_of_limits.json`.

The first nonlinear-operator mismatch identified by that conclusion has now
been removed.  `full_diffusion_noise_frechet_derivatives` differentiates the
complete `D,C,Q` operators with the same arbitrary positive quadrature weights
used by the string-adaptive rapidity discretization, implementing
`d Tdr = Tdr W(dn) Tdr`.  A directional finite-difference test on a sinh-mapped
Gauss--Legendre string grid verifies the adaptive `D'`, `C'`, and `Q'` tensors
to `4e-5` relative/absolute tolerance, while the original uniform-grid test is
unchanged.  This closes the measure inconsistency for the quadratic diffusion
and multiplicative-FDT-noise vertices.  The diffusion part now also has an
`O(N_mode^2)` directional action: `projected_diffusion_vertex_action` evaluates
`R x` from one complete `delta D[x]` without storing either `R` or
`dD[l,i,j]`.  A randomized-Wick identity then evaluates the diffusion
force memory using only this action; a dense toy calculation is reproduced
within the reported sampling standard error.  A 512-mode adaptive operator
evaluates one action in `0.27 s` with about `134 MB` maximum RSS on the local
audit machine.  The same matrix-free trace now includes the exact
dressed-velocity vertex, the full diffusion vertex, and their cross
contraction using common random vectors.  The multiplicative FDT-noise root
derivative is applied through `B dB+dB B=dQ`, also with `O(N_mode^2)` storage.
The first end-to-end adaptive smoke uses 16 modes, four internal Fourier
points, and 2048 trace samples.  Common random numbers are reused across time, and
Rademacher traces reduce the reported standard errors by about `24%--25%`
relative to Gaussian traces in this smoke.  At `t=(0,1)` the matrix-free
diffusion continuity memories are `(0.00129086,0.00123466-2.87e-6 i)`, while
explicit dense-tensor checks are `(0.00128980,0.00123353)`; the discrepancies
are only `0.041` and `0.123` reported standard errors.  The total velocity plus
diffusion plus cross memories agree with dense Wick contractions within
`0.21` standard errors.  The randomized multiplicative-noise delta contact is
`1.18352+/-0.00203`, compared with dense `1.17947`, and the root Sylvester
residual is `3.3e-15`.  This contact remains bare: it must be matched to the
exact microscopic Mori prefix.  The quadratic spin-observable Hessian is now
also included matrix-free; its 16-mode smoke agrees with the dense Wick result
within `2.76` standard errors at `t=(0,1)`.  The mixed multiplicative-noise /
quadratic-observable stochastic contact is still separate and must be fixed
in the same microscopic matching before constructing a physical finite-time
`F1`.  See
`docs/matrix_free_adaptive_diffusion_memory_smoke.json` and
`scripts/derive_matrix_free_adaptive_diffusion_memory.py`.

The nonlinear matrix-free driver now also has a native giant-string joint
scaling interface.  It accepts fixed `q=k/h^2`, `tau=t*h^3`, and
`Delta tau=h^3 Delta t`, and the audit compares the dimensionally fixed
quantities `K_colored/h^2` and `h*K_delta`; no target wall or fitted scaling
exponent is used.  A refined `h=(1/4,1/5,1/6)` sequence uses
`(288,360,432)` modes and captures `(98.646%,98.689%,98.715%)` of the exact
static susceptibility through `tau=1` (physical time 216 at the smallest
field).  At 128 Rademacher trace samples, changes in the colored velocity,
diffusion, cross, and total kernels are only `1.2--1.8` pooled standard errors,
so colored convergence remains unresolved.  The bare multiplicative-noise
contact decisively fails: `h*K_delta=(1272.11,1555.35,1846.67)` and its last
step differs by about `2.9e3` pooled standard errors in the 128-sample rerun.
This requires microscopic Mori contact renormalization before a physical
`F1` or wall `(a,D)` can be formed.  The earlier fixed-`k,t` mu26 wall script
now explicitly rejects its own projection because it takes the wrong order of
limits and produces a negative structure factor.  See
`scripts/audit_joint_scaled_nonlinear_fghd.py` and
`docs/joint_scaled_nonlinear_fghd_refined_s128_audit.json`.

Microscopic contact matching has now been moved to the physical top-level
Mori kernel.  Exact large-`z` regularity uniquely cancels the entire bare
white-noise delta contact; the colored full-mode loop is added to the complete
linear Schur kernel before the thirteen exact recurrents through `mu26` are
peeled.  At `q=0.4,p=(1,2,4)`, coarse fields violate the Stieltjes interval,
whereas `h=1/6` and `1/8` are positive at every sampled `p`.  Nevertheless the
last total `hK` step still changes by `10.7%--14.1%`.  The colored correction
itself grows with effective powers `(0.648,0.693,0.754)`, compatible with a
`h^(-2/3)` infrared breakdown; subtraction powers from `1/3` through `1`
produce incompatible finite parts.  A scalar self-consistent KPZ line dressing
removes the bare divergence but remains regulator dependent:
`Gamma=(1.7755,1.8659,1.9997)` for `h=(1/5,1/6,1/8)`, and the `h=0.1` 64-sample
repeat gives `2.3078`.  Replacing exponential line damping by the exact
Praehofer--Spohn Fourier shape also leaves a strongly running scale.  Thus the
remaining task is a matrix-valued nonlinear resummation of the infinite
string modes, not another local counterterm or a selected second pole.  See
`scripts/match_joint_scaled_nonlinear_mu26.py`,
`scripts/audit_joint_scaled_one_loop_breakdown.py`, and
`scripts/derive_self_consistent_joint_scaled_mode_coupling.py`.

The first genuinely matrix-valued nonlinear step is now implemented in
`scripts/derive_full_matrix_mode_coupling.py`.  It constructs the complete
retained-mode quadratic velocity/diffusion force covariance before any spin
projection, converts it to the Mori kernel `M C^{-1}`, and propagates one full
matrix Volterra/Dyson update.  `full_fdt_noise_covariance` independently
reconstructs the complete non-diagonal additive FDT covariance from the
Lyapunov identity.  The directional derivative of the symmetric FDT root is
also contracted into a full multiplicative-noise contact matrix, but that bare
contact is intentionally not inserted before microscopic Mori UV matching.
For the 16-mode smoke, off-diagonal Frobenius fractions of `D` and `Q` are
`0.23044` and `0.04458`; the FDT operator residual is `3.37e-17`, stationary
covariance propagation is exact, and full-matrix-to-scalar projection agrees
at `1e-17`.  This is one matrix Dyson update with linear internal lines, not a
self-consistent zero-field/infinite-string solution and not an identification
of the physical wall coefficients.  See
`docs/full_matrix_mode_coupling_smoke.json`.

The matrix Dyson map now updates every nonzero Fourier momentum jointly.  At
`h=1/8, q=0.4`, dense finite-regulator sequences through 256 modes reach their
iteration fixed points, but the `t=200` structure factor still moves from
`0.94725` (128 modes) to `0.95344` (256 modes), and an expanded-rapidity
384-mode calculation gives about `0.95834`.  A fixed `(q,tau=t h^3)` four-field
audit at `q=0.4,tau=0.4` gives `(0.95880,0.95713,0.95078,0.94725)` for
`h=(1/5,1/6,1/8,1/10)`; candidate correction powers yield a broad
`0.9009--0.9444` zero-field intercept envelope, so the joint-field gate is
rejected.  See `scripts/audit_full_matrix_joint_field_limit.py` and
`docs/full_matrix_joint_field_limit_audit.json`.

To reach larger string/rapidity cutoffs, the randomized force covariance is
now retained as exact low-rank factors and the Volterra solver propagates only
`G_k(t) X_k` for fixed Wick sources plus `C g`.  Unit tests show that these
response actions reproduce dense matrix iteration, and the 384-mode
`q=0.4,t=200` value agrees with the prior dense run to `1.1e-15`.  Response
storage falls from `104 MB` to `4.60 MB`; a 576-mode expanded-tail run captures
`97.20%` of static susceptibility with `10.7 MB` instead of a `361 MB` dense
response.  Depth-five Anderson acceleration brings the 576-mode calculation
to the authoritative raw fixed-point residual `2.16e-4` after eight
iterations.  Expanded-tail four-field results through 720 modes capture about
`97.2%` of the static susceptibility, but their joint zero-field extrapolation
is still rejected: at `q=0.4, tau=0.4` the candidate intercept envelope is
about `0.9124--0.9465`.  The solver distinguishes the accelerated step from
the raw fixed-point residual `||F(G)-G||/||F(G)||`; no fitted wall trajectory
or target value of `a,D` enters this calculation.  See
`scripts/derive_low_rank_self_consistent_full_matrix.py`.

A higher-statistics regulator calculation is running independently of the
formal convergence/Production records on SCNet as array job `23322073` under
`qbics2622`.  It evaluates four fields `(1/5,1/6,1/8,1/10)`, four independent
Rademacher batches per field, and eight trace vectors per batch, retaining the
complete non-diagonal diffusion and FDT noise matrices before projection.  Its
persistent run root is
`/work/share/giggleliu/qbics2622/kharkov_full_matrix/full_matrix_infinite_mode_20260816_003`.
The superseded run `..._001` is preserved as a node-spool failure and contains
no solver result.  Run `..._002` is preserved as a regulator-configuration
failure: it used the default rapidity-map exponent 2, captured only `88.57%`
of the susceptibility at `h=1/5`, and was stopped before extrapolation.  Run
`..._003` fixes the exponent to 3 and rejects any output capturing less than
`96%`.  The array entry point is
`hpc/scnet/full_matrix_infinite_mode_array.sbatch`.

Array `23322073` has now completed all 16 tasks with zero exit status.  The
frozen artifact `docs/scnet_full_matrix_infinite_mode_20260816_003_audit.json`
records all four replicates per field, converged finite-regulator matrix
iterations, positive-semidefinite FDT covariances, and `97.14%--97.20%`
captured susceptibility.  It nevertheless gives
`joint_field_limit_accepted=false`.  At `q=0.4,tau=0.4` the four means are
`(0.95711465,0.95447247,0.94784519,0.94636891)`; the frozen candidate-power
zero-field envelope is `0.88840--0.94539`, its width `5.70e-2` is far above
the `2e-3` gate, the finest-field step bound is `5.20e-3`, and the maximum
single-field SEM is `1.42e-3`.  The failure is therefore an unresolved field
limit plus trace precision, not a solver/FDT/scheduler failure.  The full
Fourier job remains prohibited until the preregistered matched-field and
variance-reduction gates pass.

The `tau<=0.4` sequence is a regulator preflight, not yet the physical wall
ray.  The exact giant-string amplitude `D0=5*pi/27` and `chi=1/4` fix that ray
at `tau*=1/(4 D0 sqrt(chi))=27/(10*pi)=0.8594366927`.  A second independent
four-field/four-replicate array, job `23322120`, therefore propagates nineteen
uniform scaled-time points ending exactly at `tau*`.  Its persistent root is
`/work/share/giggleliu/qbics2622/kharkov_full_matrix/full_matrix_physical_tau_20260816_001`,
and its entry point is `hpc/scnet/full_matrix_physical_tau_array.sbatch`.
The first two ordinary-Rademacher physical-ray outputs differ by about
`7.6e-3` at `q=0.4,tau=tau*`, so trace variance grows materially on the longer
ray.  A variance-reduction pilot, array job `23322171`, compares four
eight-probe SRHT--Rademacher repeats at `h=1/5`; its root is
`/work/share/giggleliu/qbics2622/kharkov_full_matrix/full_matrix_srht_physical_tau_20260816_001`.
The SRHT probes have exact +/-1 entries and unbiased second moment but sample
Hadamard columns without replacement.  In an eight-repeat small-system test
they reduced endpoint real-part standard deviation from `1.93e-3` to
`1.02e-3`; the full 360-mode pilot is the acceptance test.

The 360-mode pilot completed with four valid outputs.  At
`q=0.4,tau=tau*`, ordinary Rademacher probes had real-part standard deviation
`4.82e-3`, whereas SRHT--Rademacher had `2.30e-3`.  Their mean difference
`1.81e-3` is below the pooled standard error `2.67e-3`, so the pilot found
variance reduction without detectable bias.  The already completed `h=1/5`
pilot is reused; SCNet array `23322241` computes only the remaining three
fields and four seeds under persistent root
`/work/share/giggleliu/qbics2622/kharkov_full_matrix/full_matrix_srht_physical_tau_20260816_002`.

The first completed `h=1/6` SRHT batch has endpoint mean
`0.84850+0.00184i` and complex SEM `3.29e-3`; eight probes therefore do not
meet the frozen `5e-4` single-field SEM gate.  A new variance reduction keeps
the same independently generated and propagated SRHT frames but reuses
cyclic pairs `(x_i,y_{i+r})`.  With `P` shifts it supplies `P*S` unbiased Wick
outer products while retaining only `1+2*S` propagated source columns; only
the low-rank Mori memory rank grows.  SCNet array `23322346` is the paired
`P=2,4` pilot at `h=1/6`, reusing the four `P=1` seeds.  Its persistent root is
`/work/share/giggleliu/qbics2622/kharkov_full_matrix/full_matrix_trace_pairing_pilot_20260816_001`;
the test-only submission succeeded and the frozen source-manifest hash is
`51baf7c817ad0af0037461f85e52f57c87f770c0ab82d4bf980778b817f45546`.
`scripts/audit_trace_pairing_variance_reduction.py` requires no detectable
paired mean shift and non-increasing real variance before the method can be
used beyond this pilot.  Before the pilot completed, the audit also froze the
`5e-4` complex-SEM target and a target-independent plug-in replicate estimate
`ceil((var(Re S)+var(Im S))/(5e-4)^2)`.  This estimate plans the next batch but
does not replace direct SEM validation because it is itself based on four
replicates.

The earlier `P=1` SRHT continuation used `trace_source_layout=pairwise`, while
the `P=2,4` pilot uses `shared_wave`; it is therefore not an orthogonal control
for cyclic pairing even though both estimators are unbiased.  Those older
files remain background evidence but are excluded from the pairing audit.
`hpc/scnet/full_matrix_trace_pairing_p1_control.sbatch` supplies the missing
four common-seed `P=1,shared_wave` controls.
The control was uniquely submitted as SCNet array `23322523` after a
successful test-only check.  Its persistent root is
`/work/share/giggleliu/qbics2622/kharkov_full_matrix/full_matrix_trace_pairing_p1_control_20260816_001`,
and its frozen source-manifest SHA256 is
`a42f0c23968097956a2d993a85718fce0a87519ea54d92800150a595b45b6417`.

The separately preregistered complete Cartesian pairing test has now also
finished.  SCNet parent `23323335` completed all 16 array elements with zero
exit status and maximum batch RSS below `442 MiB`; all nonempty stderr files
contain locale/startup warnings only.  The frozen eight-seed audit rejects
`P=8`: the `P=1` and `P=8` endpoint means are respectively
`0.84938876+0.00088866i` and `0.84390629+0.00092826i`; the `P=8/P=1`
real-variance ratio is `1.53380`, and the paired mean shift `0.00548260`
exceeds twice its SEM `0.00156839`.  The frozen fallback therefore selects
`P=1` only.  The preregistered plug-in estimate is 77 independent replicas
per field to target complex SEM `5e-4`; it is a planning count, and the final
SEM must still be checked directly.  See
`docs/scnet_full_matrix_complete_pairing_audit_20260817.json`.  Partial
pairing counts must not be resurrected after this result.

A separate matched-field audit is now preregistered rather than selecting a
fractional correction power after seeing the wall coefficients.  Once the
`u=xi*r` boundary layer is resolved, the Euler--Maclaurin string measure gives
the one-sided hierarchy `S_h=S0+c1*|h|+c2*|h|^2+c3*|h|^3+...`.  The audit
requires at least five fields: degree-one, degree-two, and degree-three fits
to the coarser fields must all predict a held-out finest field, and their
two-sigma zero-field intercept envelope must be at most `2e-3`; each field
still needs SEM at most `5e-4`.  Thus the current four fields cannot pass by
construction.  See `scripts/audit_matched_integer_field_limit.py`.

`hpc/scnet/full_matrix_matched_field_sequence.sbatch` is the unsubmitted
seven-field compute entry point.  It covers
`(0.3,0.25,0.2,1/6,1/8,1/10,1/12)` and
requires the submitter to freeze both `TRACE_PAIRING_COUNT` and
`REPLICATES_PER_FIELD`; it does not choose either from the target wall.  If a
pairing count above one is accepted, all seven fields must be recomputed under
that common regulator rather than mixing the existing `P=1` coarse fields
with paired finer fields.  The two added coarse fields are required because
the self-consistent physical regulator
`h_eff(t)=(tau*/t)^(1/3)` spans approximately `0.2581` to `0.1626` on
`50<=t<=200`; a five-field sequence beginning at `h=0.2` would extrapolate
over part of the requested window.

The final wall projector no longer enumerates fractional single-power field
corrections.  `scripts/project_running_field_full_matrix_wall.py` requires an
accepted seven-field matched-integer audit,
rechecks the exact input SHA256 set, and propagates only polynomial degrees
1, 2, and 3.  It evaluates those expansions at the running physical field
instead of taking the zero-field intercept first, Fourier-inverts
`S(q,t)=sum_n c_n(q,tau*) h_eff(t)^n` without an internal width
renormalization, and then applies the frozen weak projection.  For each
degree, that projection must agree with an independent strong projection to
within 15% for both `a` and `D`; the degree envelope must be at most 10%.
An unaccepted or stale field audit is a hard error.
The choices above, including the seven fields, physical-time map, Fourier
grid, projection windows, tolerances, and source hashes, are frozen in
`docs/full_matrix_running_field_projection_preregistration_20260816.json`
before any candidate seven-field output exists.

The next full-Fourier step is prepared but is not submitted before the
single-wave field gate.  `hpc/scnet/full_matrix_qgrid_momentum_pilot.sbatch`
uses 32 scaled Fourier points at `Delta q=0.25`, shared-wave SRHT probes, and
four paired seeds at internal-momentum sample counts `P=4,8`.
`scripts/audit_momentum_sampling_convergence.py` requires the maximum paired
`|mean|+2 SEM` change over every nonzero wave and time to be at most `1e-3`.
The q-grid sbatch now requires the accepted `TRACE_PAIRING_COUNT` explicitly;
the lower- and higher-momentum-sample groups must share it.  Its audit also
requires numeric non-diagonal `D,Q`, FDT, and thermodynamic-metric evidence,
so the Fourier stage cannot silently revert to a diagonal or `P=1` regulator.

After that pilot passes, the unsubmitted production entry point is
`hpc/scnet/full_matrix_qgrid_matched_field_sequence.sbatch`.  It covers all
seven fields and 32 scaled Fourier points, and requires the accepted
`TRACE_PAIRING_COUNT`, `MOMENTUM_SAMPLES`, and `REPLICATES_PER_FIELD`
explicitly.  Missing gate outputs therefore cannot fall back to defaults.

The low-rank solver now exports the colored physical continuity memory
`p^T M_k(t) p/(chi khat_k^2)` from the same full non-diagonal matrix factors
used in its Volterra update.  It explicitly excludes the regulator-dependent
white multiplicative-noise contact.  The new
`scripts/match_full_matrix_memory_to_exact_mori.py` averages independent
theory replicas and embeds this colored shape behind the exact finite-k XXX
Mori--Lanczos prefix (`mu0..mu16`, eight recurrents).  The unresolved part is
a nonnegative continuum quadrature, not a one- or two-pole/second-field
closure; spectral-node doubling and time-tail truncation are separate gates.
Sixteen focused tests pass.  Existing SCNet runs use an older frozen source
snapshot and therefore cannot supply this new observable; a matched-field run
with the accepted trace-pairing count is still required before the physical
`F1` and wall coefficients can be certified.
