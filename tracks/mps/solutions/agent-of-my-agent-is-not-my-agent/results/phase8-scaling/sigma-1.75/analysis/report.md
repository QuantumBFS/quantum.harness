# Phase 8 sigma=1.75 finite-size scaling

The dynamical exponent is estimated from the lowest parity gap. The
gap-based pairwise effective dynamical exponents are
z_eff(16,32)=0.78160589, z_eff(32,64)=0.72413655,
z_eff(64,96)=0.64218628, and z_eff(96,128)=0.56746993, with each value
assigned to L_eff=sqrt(L1*L2). The five-size power and
logarithmic sensitivity regressions give
z=0.55881828 and
z=0.20019604. These deterministic regressions
have two residual degrees of freedom. Adjacent z_eff values share gap
estimates, so their residuals are correlated and are not treated as
independent statistical samples. The 1/L_eff and 1/log(L_eff) coordinates
do not assume a known leading correction exponent.

Leaving L=16 out gives z=0.47838405
and z=-0.07064197 for the
power and logarithmic coordinates, respectively.

Shiratani--Todo report z=0.91(2)
for the power correction and z=0.98(3)
for the logarithmic correction at sigma=7/4
([arXiv:2305.14121v4](https://arxiv.org/abs/2305.14121), Table 2).
The comparison follows the spirit of their power/log finite-size correction
analysis, while the underlying exponent estimators differ: DMRG uses
excitation-gap slopes, whereas their QMC calculation uses tuned
imaginary-time aspect ratios and quotient-style finite-size estimates.
Their calculation reaches L=362; the present L<=128
comparison is therefore qualitative and is not a precision reproduction.

The power/log critical-field sensitivity is reported separately and is not
fully propagated into gap uncertainty because only two crossings are
available. The zero-frequency susceptibility gamma/nu is not measured.
Equal-time C_eq(r) and S_eq(0) are auxiliary diagnostics only.

After the L=64 odd-sector state recorded discarded weight 5.49e-8 while
the variance and energy-convergence gates passed, the Phase 8-only
discarded-weight limit was changed from 1e-8 to 1e-7. The relative-variance
limit remains 1e-10. This post-observation protocol amendment is included
explicitly in the uncertainty budget.

The L=128 even chi=128 state is accepted with a diagnostic warning:
its nominal relative-variance target is
1e-10, the observed value
is 1.0506516e-10, and 21 additional
sweeps changed the energy by only
6.8212103e-13. The even state was
not promoted to chi=256.

The L=96 and L=128 odd states were initialized from their audited chi=128
checkpoints and fully reoptimized at chi=256. Their gap shifts were
-1.212214e-07 and
-4.5292344e-07, respectively. Both
chi=128 baselines and chi=256 refined results are retained in
`refinement-diagnostics.csv`; these shifts define the targeted Phase 8
MPS-truncation uncertainty.
