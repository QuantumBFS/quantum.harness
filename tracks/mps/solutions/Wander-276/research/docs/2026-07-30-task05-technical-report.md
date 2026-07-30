# Technical Report: Geometry Speaks Under Exact Degeneracy

**Release:** `task05-geometric-chaos-v1`
**Article:** *Spectral Silence and Geometric Chaos in an Exactly Degenerate Topological Manifold*
**Authors:** Thomas J. Wang and OKongOYangO
**Date:** 2026-07-30

## Executive Signal

This project establishes a new route to diagnosing quantum chaos when an entire many-body manifold is exactly degenerate. Instead of introducing an artificial energy splitting, it measures how the protected subspace moves over coupling space. The result is a hierarchy of geometric information: finite-Jacobi curvature correlations at local scales, a gauge-invariant connected response cumulant at the operator level, and tunable Wilson holonomy inside a fixed Chern class.

The central scientific advance is therefore stronger than a new statistic. It is a complete architecture for **geometric chaos under exact spectral flatness**:

$$\text{exact parent kernel}\longrightarrow\text{projector response}\longrightarrow\text{metric normalization}\longrightarrow\text{finite-rank RMT}\longrightarrow\text{global bundle topology}.$$

## Relation to the Starting Point

Chen, Colin-Ellerin, Mamroud, and Papadodimas introduced non-Abelian Berry curvature as an intrinsic chaos diagnostic for exactly degenerate BPS sectors. Their work supplies the conceptual starting point: energy degeneracy elevates quantum geometry from an auxiliary observable to the primary carrier of chaos information.

This release adds a complementary condensed-matter realization and four new layers:

| Starting capability | Innovation in this project | Why it matters |
|---|---|---|
| Curvature as a BPS chaos diagnostic | Exact bosonic Laughlin zero modes of a local Kapit–Mueller parent | Demonstrates the geometric principle in a frustration-free fractional-topological system |
| Random-matrix-like curvature | Exact finite-\(D\) complex-Jacobi kernel and connected form factor | Supplies a parameter-free benchmark at the dimensions used numerically |
| Curvature eigenvalue evidence | Gauge-invariant four-channel response tensor | Promotes Geometric ETH from eigenvalue statistics to a matrix-element statement |
| Moduli-space Chern topology | Fixed-spectrum, fixed-Chern, tunable Wilson holonomy | Separates integrated topology from relative non-Abelian transport |
| Numerical demonstration | Cryptographic release manifest and tiered verification | Makes every public claim traceable to source, figure, compact artifact, or regenerable array |

## Why the New Algorithms Make This Possible

### Exact parent-Hamiltonian geometry

The bosonic contact parent is positive semidefinite, and its Laughlin quasihole manifold is the exact kernel. The Kapit–Mueller lattice supplies an exactly flat Chern band and a clean boundary-twist torus. Together they provide exact degeneracy, an open external gap, a growing multiplet rank, and local response channels in one calculable model.

### Signature-compression reduction

Let \(P\) project onto the exact zero-mode manifold and \(Q=1-P\). The resolvent-dressed response map for a deformation \(\lambda^\mu\) is

$$X_\mu=P(\partial_\mu H)Q\,[Q(H-E_0)Q]^{-1}.$$

After whitening by the quantum metric, the curvature becomes a compression of a fixed signature matrix by the row space of the response channel. When that row space is Haar distributed, the curvature eigenvalues form an exact complex-Jacobi process. The algorithm therefore replaces a large, model-specific matrix comparison with a finite-rank analytic law containing the correct rank, support, and boundary atoms.

### Determinantal-kernel form factor

The connected curvature form factor is evaluated directly from the unfolded finite-Jacobi determinantal kernel. For \(D>M\), the signature compression produces exact atoms at \(\lambda=\pm1\). Separating their algebraic multiplicities yields

$$K_{J,c}^{\mathrm{full}}(\tau)=\frac{k}{D}K_{J,c}^{(k)}(\tau),\qquad k=2M-D.$$

At \(D=800\), the calculation resolves 120 atoms on each boundary and a connected plateau of \(0.7\). This finite-rank correction is available analytically and is implemented as an executable theorem.

### Gauge-invariant four-channel law

The whitened response tensor

$$T_{\mu\nu\rho\sigma}=\frac{1}{D}\operatorname{Tr}(\widetilde X_\mu\widetilde X_\nu^\dagger\widetilde X_\rho\widetilde X_\sigma^\dagger)$$

is invariant under independent changes of basis in the zero-mode and complementary subspaces. Its complex-Gaussian reference is generated from measured two-point covariances and independent samples, so the normalized residual \(R_4\) measures a genuine connected four-channel component.

### Bundle-isomorphism control of holonomy

For a smooth periodic ambient unitary \(\mathcal U_g(\theta)\),

$$H_g(\theta)=\mathcal U_g(\theta)H_0(\theta)\mathcal U_g^\dagger(\theta)$$

preserves every energy, the external gap, and the vector-bundle isomorphism class. The Berry connection gains the projected one-form

$$A_g=A_0+i\Phi_0^\dagger\mathcal U_g^\dagger d\mathcal U_g\Phi_0,$$

which tunes relative Wilson transport while \(C_1\) stays fixed. This provides a clean causal separation of determinant topology and non-Abelian holonomy.

## Quantitative Results

### Exact spectral-flatness identity

For a \(D\)-fold degenerate zero-mode manifold,

$$K_{E,\mathrm{raw}}=D,\qquad K_{E,c}=0.$$

This exact identity fixes the baseline and motivates the geometric channel.

### Local curvature universality

The physical ensemble contains 20000 independent Kapit–Mueller tangent pairs. At \(\tau=0.5\), the connected curvature form factor is \(0.502\), compared with \(0.501\) from the exact finite-\(D\) Jacobi kernel. A full-rank Fourier tangent family produces \(4.476\), cleanly resolving microscopic structure at the same active rank.

### Matrix-element Geometric ETH

| \(N\) | \(D\) | Physical median \(R_4\) | Matched Gaussian median | Connected excess |
|---:|---:|---:|---:|---:|
| 3 | 16 | 0.37093 | 0.21708 | 0.15385 |
| 4 | 25 | 0.24715 | 0.14638 | 0.10078 |
| 5 | 36 | 0.20906 | 0.12723 | 0.08183 |

The monotone decrease reveals progressive Gaussianization, while the resolved connected component defines the registered `deformed_geometric_eth` branch.

### Fixed-Chern holonomy

| \(N\) | \(D\) | \(C_1\) | Minimum external gap | Base Wilson \(\langle r\rangle\) | Deformed seed interval |
|---:|---:|---:|---:|---:|---:|
| 3 | 16 | 6 | 0.051741 | 0.28849 | [0.30837, 0.35754] |
| 4 | 25 | 10 | 0.094695 | 0.30998 | [0.32379, 0.34411] |

The complete spectrum and \(C_1\) stay fixed across the family. The Wilson shift is reproducible across seeds and occupies a structured regime distinct from CUE, establishing `fixed_chern_deformed_holonomy`.

## Innovation-to-Evidence Matrix

| Innovation | Primary evidence | Independent verification |
|---|---|---|
| Exact spectral-flatness baseline | Figure 1 and Eq. (1) | Analytic form-factor tests |
| Finite-Jacobi curvature algorithm | Figures 1, 2, and 5 | Quadrature stability and Monte Carlo cross-checks |
| Independent spectral/geometric interventions | Figure 3 | Fixed-projector and tangent-channel invariance tests |
| Correlation hierarchy | Figure 4 | Matrix-level simultaneous confidence bands |
| Four-channel Geometric ETH | Figure 6 | Gauge randomization and covariance-matched references |
| Fixed-Chern Wilson engineering | Figure 7 | Mesh convergence, branch margins, and isospectral checks |
| Reproducible public release | Release manifest | Hash, link, blob-size, isolation, PDF, and test audits |

## Delivery Package

- [17-page article PDF](../01_task_folder/task_05/script/output/spectral_silence_and_geometric_chaos_v3.pdf)
- [Task release guide](../01_task_folder/task_05/README.md)
- [Machine-readable release manifest](../01_task_folder/task_05/script/output/release_manifest_v1.json)
- [Combined PDF/article audit](../01_task_folder/task_05/script/output/geometric_eth_topology_delivery_audit_v3.json)
- [Matrix-element artifact](../01_task_folder/task_05/script/output/matrix_element_geometric_eth_v3.json)
- [Topology artifact](../01_task_folder/task_05/script/output/topological_holonomy_v3.json)
- [Seven-figure package](../01_task_folder/task_05/script/output/figure_1_spectral_silence_v2.png)
- [Public challenge handoff](2026-07-30-quantum-geometry-harness-challenge-draft.md)

## Verification

The compact review path is:

```bash
cd 01_task_folder/task_05/script
python -m pip install -r requirements.txt
bash run_quick_verify_v1.sh
```

It checks 17 release-contract classes and 38 focused tests. The complete compact-checkout suite reports 86 passing tests plus 6 production-data tests that activate when their manifest-listed arrays are restored. The article build independently compiles and audits all 17 pages, seven figures, references, metadata, and source synchronization.

## Forward Program

The release opens three high-value directions:

1. extend the genuine fixed-two-quasihole sequence through \(N=6\) and resolve the asymptotic four-channel law;
2. transfer the invariant response-tensor protocol to a second exact-degeneracy mechanism;
3. connect local curvature, operator cumulants, and Wilson transport to dynamical observables.

The combined analytic reduction and reproducible numerical architecture make each direction immediately testable. The public challenge packages these goals into machine-verifiable outcomes and welcomes independent implementations.
