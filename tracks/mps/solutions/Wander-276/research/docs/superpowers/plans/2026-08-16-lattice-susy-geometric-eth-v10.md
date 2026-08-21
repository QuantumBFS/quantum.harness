# Lattice-SUSY Geometric ETH v10 Implementation Plan

**Goal:** Test the same exact-degeneracy geometric statistics in a hard-core-fermion lattice supersymmetry whose zero modes arise from graph cohomology rather than a fractional-quantum-Hall parent.

**Registered model:** The graph is a disjoint union of `m` six-site cycles.  The nilpotent supercharge is `Q = sum_i z_i c_i^dagger P_<i>`, acting on the independence complex.  The registered sector has fermion number `2m`; its harmonic rank is `2^m`, while both incoming and outgoing differentials are nonzero.

**Opened sizes:** `m = 1, 2, 3`.  `m = 4` is prospective until the sparse response implementation and measured memory audit pass.

**Observable:** Site-coupling tangents are projected away from the component-wise complex rescaling directions.  Exact and coexact resolvent responses are retained separately, total-channel whitening uses the existing frozen convention, and the connected four-channel statistic is reported without refitting.

- [ ] Implement and test independent-set bases, fermionic signs, and nilpotency.
- [ ] Verify the complete harmonic rank `2^m`, zero-mode bandwidth, positive gap, and deterministic projector for every opened size.
- [ ] Verify exact/coexact branch sum, mutual Hodge orthogonality, target leakage, and centered finite-difference projector response.
- [ ] Run a deterministic opened pilot with local and isotropic tangent panels.
- [ ] Register resource estimates before opening `m = 4` or larger.
- [ ] Aggregate accepted and failed cases without deleting either.
