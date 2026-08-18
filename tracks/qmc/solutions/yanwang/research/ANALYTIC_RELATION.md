# Can the factor \(\sqrt5\) be derived?

## Short answer

No exact derivation is presently known to us. The numerical proximity is a
well-motivated conjecture, not a consequence of ordinary universality,
Kramers–Wannier duality, or the classical triangular–honeycomb
star–triangle transformation.

The two quantum critical points share the 3D Ising universality class.
Universality fixes critical exponents and scaling functions, but the
dimensionless microscopic locations \(h_c/J\) are nonuniversal. Equal
universality classes therefore do not impose an algebraic relation between
the two critical fields.

## Why the classical star–triangle proof does not transfer

For the two-dimensional *classical* Ising model, tracing a central spin in a
three-leg star gives a local Boltzmann weight that can be represented by
pairwise couplings on a triangle. This is the exact star–triangle
transformation.

For the two-dimensional quantum TFIM, a Suzuki–Trotter decomposition gives a
three-dimensional anisotropic classical model with

\[
K_s=\Delta\tau J,\qquad
K_\tau=\frac12\log\coth(\Delta\tau h).
\]

Every spin in a spatial star is also coupled to its copies on adjacent
imaginary-time slices. Eliminating the central worldline therefore generates
multi-spin and retarded interactions between neighboring worldlines. These
terms do not close inside the original nearest-neighbor TFIM family. A
single-slice classical star–triangle identity consequently does not produce
an exact map

\[
(J,h)_{\rm honeycomb}\longleftrightarrow
(J',h')_{\rm triangular}.
\]

## Why standard quantum duality does not give the ratio

In one spatial dimension, the TFIM is self-dual, which pins \(h_c/J=1\).
In two spatial dimensions, the corresponding exact Ising duality maps the
spin model to a \(\mathbb Z_2\) lattice gauge theory. It does not map the
honeycomb nearest-neighbor TFIM to the triangular nearest-neighbor TFIM while
preserving the same two couplings. Thus it supplies no equation whose
solution is \(h_c^\triangle/h_c^\hexagon=\sqrt5\).

## What a genuine proof would require

At least one of the following would be needed:

1. an exact operator or partition-function transformation that closes within
   the two TFIM Hamiltonians and fixes the coupling map;
2. an integrable representation that determines both critical fields
   algebraically;
3. a convergent symbolic expansion plus a theorem identifying its critical
   singularity and proving the proposed relation.

A useful next analytic test is to compute high-field gap series for both
lattices to high order. A mismatch with every functional identity implied by
the proposed coupling map would rule out broad classes of simple
star–triangle explanations. Agreement to finite order would motivate, but
would not prove, an exact relation.

## Present status

Our QMC baseline gives a ratio only `0.55` total standard deviations from
\(\sqrt5\). It is therefore consistent with the conjecture, but numerical
agreement—even at much higher precision—cannot by itself establish exact
equality.

Primary references:

- M. E. Fisher, “Transformations of Ising Models,” Phys. Rev. 113, 969
  (1959), DOI `10.1103/PhysRev.113.969`.
- M. Mathur and T. P. Sreeraj, “Lattice gauge theories and spin models,”
  Phys. Rev. D 94, 085029 (2016), DOI `10.1103/PhysRevD.94.085029`.
- H. W. J. Blöte and Y. Deng, “Cluster Monte Carlo simulation of the
  transverse Ising model,” Phys. Rev. E 66, 066110 (2002), DOI
  `10.1103/PhysRevE.66.066110`.
