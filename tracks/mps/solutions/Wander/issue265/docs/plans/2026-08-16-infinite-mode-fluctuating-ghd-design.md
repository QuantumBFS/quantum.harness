# Infinite-mode fluctuating GHD with microscopic Mori matching

## Objective

Propagate the physical spin structure factor with the complete retained GHD
occupation space, including the non-diagonal diffusion operator and the full
fluctuation--dissipation noise covariance.  No auxiliary mode, target
trajectory, or target Burgers coefficient is supplied.  The calculation must
either produce a regulator-stable finite-window correction or report that the
available microscopic constraints do not determine it uniquely.

## Chosen construction

At finite magnetic regulator `h`, whiten the static occupation covariance and
rotate exactly onto physical spin plus its entire orthogonal complement.  The
linear generator retains the full advection and diffusion matrices, and the
noise covariance is constructed from the Lyapunov/FDT identity.  The
orthogonal complement is eliminated by a Schur resolvent or Krylov action,
without replacing its spectrum by one or two poles.

The leading nonlinear correction is evaluated deterministically by Wick and
Duhamel contractions.  It includes the dressed-velocity vertex, the Frechet
derivative of the complete diffusion operator, the derivative of the symmetric
FDT noise root, their cross terms, and the quadratic physical-spin observable.
Equilibrium tadpoles are Wick ordered.  The resulting colored and contact Mori
terms are not interpreted before a hydrodynamic-UV audit.

## Microscopic matching

The zero-field Heisenberg commutator algebra supplies the exact long-wave Mori
moments through `mu20`, equivalently ten positive Lanczos recurrents.  A matched
kernel must preserve these moments while retaining the low-frequency
infinite-mode GHD contribution.  We therefore peel the ten exact continued-
fraction levels and reconstruct the unresolved terminator as a nonnegative
continuum quadrature of `z/(z^2+omega^2)`.  Reinserting this spectrum preserves
the exact recurrent prefix algebraically without selecting a physical pole
count.  Positivity and regulator stability are tested over the whole declared
Laplace band.  If they fail, the artifact records that `F1_perp` remains
underdetermined.

## Outputs and gates

The machine-readable certificate records covariance capture, FDT residual,
full off-diagonal diffusion retention, the linear full-spectrum Mori kernel,
each nonlinear diagram, exact microscopic moment bounds, cutoff variation,
and whether one common matching prescription stabilizes all declared
frequencies.  Only a passed matching and joint field/node/cutoff limit may be
used to construct a target-free wall and apply the frozen weak projection to
`(a,D)`.  Otherwise the output is evidence about the missing correction, not a
coefficient prediction.

Tests cover exact FDT stationarity, basis invariance, positivity of the
microscopic continued fraction, moment preservation, and fail-closed behavior
under cutoff drift.
