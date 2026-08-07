# Quantum Harness Challenge Draft: Geometry Speaks Under Exact Degeneracy

## Form Fields

**Title**

`[challenge] Can non-Abelian quantum geometry reveal chaos inside an exactly degenerate manifold?`

**Released by**

Thomas J. Wang, Tsinghua University

**Public contact**

[@JunkaiWang-TheoPhy](https://github.com/JunkaiWang-TheoPhy); the issue form can carry the preferred public email.

**Method**

Exact Diagonalization

## Challenge Issue

**Difficulty:** ★★★

### Background

An exactly degenerate multiplet has identical internal energies, while its projector can trace a rich path through Hilbert space. Chen, Colin-Ellerin, Mamroud, and Papadodimas proposed non-Abelian Berry curvature as an intrinsic chaos diagnostic for degenerate BPS microstates in [arXiv:2604.23287](https://arxiv.org/abs/2604.23287). The public task-05 baseline turns that idea into a gauge-invariant many-body matrix-element program with exact analytic references and machine-checkable outcomes.

For a degenerate projector \(P(\lambda)\), \(Q=1-P\), and zero-mode energy \(E_0\), define the resolvent-dressed tangent response

$$X_\mu=P(\partial_\mu H)Q[Q(H-E_0)Q]^{-1}.$$

After whitening by a preregistered two-point channel covariance, evaluate the gauge-invariant tensor

$$T_{\mu\nu\rho\sigma}=\frac{1}{D}\operatorname{Tr}(\widetilde X_\mu\widetilde X_\nu^\dagger\widetilde X_\rho\widetilde X_\sigma^\dagger)$$

against its finite-size covariance-matched complex-Gaussian Wick reference.

The baseline establishes feasibility for a bosonic Laughlin sequence at \(N=3,4,5\): local curvature correlations follow the finite-Jacobi law, the connected four-channel component decreases monotonically, and fixed-Chern Wilson holonomy occupies a structured tunable regime. The challenge begins at the next scaling frontier.

### Research Objective

Complete at least one branch:

1. extend the fixed-two-quasihole Laughlin sequence through \(N=6\) and issue a preregistered matrix-element verdict;
2. repeat the full gauge-invariant test in a second local exact-degeneracy mechanism;
3. derive and verify the asymptotic scaling of the connected four-channel component from locality or constraint algebra.

The verifier selects exactly one outcome:

- `emergent_wick_geometric_eth`;
- `deformed_geometric_eth`;
- `structured_geometry_regime`;
- `scaling_frontier`.

Every branch carries scientific value and maps a distinct universality structure.

### Mandatory Gates

**Gate 0: exact kernel and gap.** Match the target rank to independent counting, resolve internal bandwidth below \(10^{-8}\) times the external gap, publish eigensolver/resolvent residuals, and retain every preregistered size.

**Gate 1: gauge and mesh invariance.** Curvature spectra, the four-channel residual, Chern number, and Wilson eigenphases must remain stable under independently sampled local \(U(D)\) frame rotations. Two meshes must agree on the integer Chern number with positive determinant-branch margin and stable Wilson statistics.

**Gate 2: independent chaos axes.** Tune unfolded intramultiplet statistics through \(PHP\) while preserving \(P\) and its geometry; tune \(P(\partial_\mu H)Q\) while preserving the complete energy spectrum.

**Gate 3: matrix-element verdict.** Freeze sizes, local-operator panels, covariance cutoff, random seeds, reference count, compatibility bands, and solver tolerances before the largest run. Emit the result branch from raw artifacts through a public script.

**Gate 4: topology.** On a closed two-parameter surface, separate determinant \(U(1)\) topology from relative \(SU(D)\) holonomy and report both the fixed \(C_1\) sector and the Wilson universality class.

### Deliverables

- source and environment lock;
- raw spectra, overlaps, seeds, and solver checkpoints or a DOI-backed data archive;
- machine-readable result schema and one-command verifier;
- gauge-randomization and mesh-convergence reports;
- compact figures showing the three-ensemble comparison, four-channel scaling, and fixed-Chern holonomy;
- a research report that explains the selected outcome as a distinct universality statement.

### Why This Can Produce Research

Wick compatibility would establish a microscopic matrix-element Geometric-ETH law in an exactly degenerate many-body manifold. A stable connected component would establish a deformed fixed tensor with operator memory. Independent spectral and geometric axes reveal how multiple notions of chaos coexist, while the topology gate connects local universality to the global structure of parameter space.

The baseline contributes new finite-rank algorithms, a gauge-invariant tensor law, and an isospectral topology control, so every submission begins from an executable research platform rather than a conceptual prompt.

### References

1. Y. Chen, S. Colin-Ellerin, O. Mamroud, and K. Papadodimas, [“Chaos of Berry curvature for BPS microstates”](https://arxiv.org/abs/2604.23287).
2. M. Kolodrubetz, D. Sels, P. Mehta, and A. Polkovnikov, [“Geometry and non-adiabatic response in quantum and classical systems”](https://arxiv.org/abs/1602.01062).
3. T. Fukui, Y. Hatsugai, and H. Suzuki, [“Chern Numbers in Discretized Brillouin Zone”](https://doi.org/10.1143/JPSJ.74.1674).
4. Quantum Harness [issue 73](https://github.com/QuantumBFS/quantum.harness/issues/73), an Abelian Berry-phase benchmark complementary to this non-Abelian challenge.

## Submission Note

An authorized repository member can paste this draft into the issue form, add the preferred public email, and attach the release DOI when available.
