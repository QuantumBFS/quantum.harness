# Hodge-Resolved Geometric ETH Across Topological and SUSY Zero Modes

**Status:** Approved by the human on 2026-08-01 with “做吧.”

**Scientific target:** Determine whether the covariance-whitened response law developed for exactly degenerate Laughlin parent Hamiltonians extends to a genuinely different supersymmetric/cohomological protection mechanism, and whether a response-complex Hodge decomposition predicts the unseen higher-order geometry better than a collapsed covariance model.

## Novelty boundary

The third-model result must not be presented as the discovery of chaotic Berry curvature in $\mathcal N=2$ SYK. Chen, Colin-Ellerin, Mamroud, and Papadodimas already established random-matrix-like curvature statistics, number variance, spectral form factors, structured decomposable-three-form controls, and moduli-space topology in that model. Miyahara and Shibuya also studied a chaos--integrability crossover using operators projected into the BPS subspace.

The new contribution is a common response-matrix and connected-four-point formalism across non-SUSY topological constraints and SUSY cohomology, with a prediction generated only from safe two-point Hodge data before the third model's physical $R_4$ is opened.

## Model and protected fiber

Use the generic cubic $\mathcal N=2$ SYK supercharge

$$Q(C)=\sum_{1\leq i<j<k\leq N}C_{ijk}\psi_i\psi_j\psi_k,\qquad Q^2=0,$$

with Hamiltonian

$$H(C)=\{Q(C),Q(C)^\dagger\}.$$

The computation is charge resolved. In the charge-$r$ Hilbert space $\mathcal H_r$, the protected fiber is the harmonic cohomology

$$\mathcal H_{\mathrm{BPS},r}=\ker Q_r\cap\ker Q_{r-3}^\dagger.$$

The primary sequence uses even $N$ and two sectors:

1. the central sector $r=N/2$, where particle-hole symmetry constrains the curvature class and tests a balanced Hodge response;
2. the adjacent sector $r=N/2-1$, which tests a generically unbalanced response without the central spectral pairing.

The script-generated registered dimensions are:

| $N$ | sector | $\dim\mathcal H_r$ | expected BPS rank | complement rank |
|---:|---|---:|---:|---:|
| 8 | $r=4$ | 70 | 54 | 16 |
| 8 | $r=3$ | 56 | 27 | 29 |
| 10 | $r=5$ | 252 | 162 | 90 |
| 10 | $r=4$ | 210 | 81 | 129 |
| 12 | $r=6$ | 924 | 486 | 438 |
| 12 | $r=5$ | 792 | 243 | 549 |
| 14 | $r=7$ | 3432 | 1458 | 1974 |
| 14 | $r=6$ | 3003 | 729 | 2274 |
| 16 | $r=8$ | 12870 | 4374 | 8496 |
| 16 | $r=7$ | 11440 | 2187 | 9253 |

Use $N=8,10,12$ for implementation and sequential validation. Keep every $N=14$ four-point outcome sealed until a numerical prediction is hashed. Run $N=16$ only if the accepted models give separated registered intervals and the $N=14$ calculation passes every numerical gate.

## Exact Hodge response

Let $P$ project onto $\mathcal H_{\mathrm{BPS},r}$ and $H_\perp^+$ denote the inverse of $H$ on the orthogonal complement of the BPS fiber. For a real coupling tangent $\delta Q+\delta Q^\dagger$, the complement-to-fiber response is

$$X(\delta C)=-H_\perp^+\bigl(Q\,\delta Q^\dagger+Q^\dagger\delta Q\bigr)P=X_-\oplus X_+,$$

with

$$X_-=-H_\perp^+Q\,\delta Q^\dagger P,\qquad X_+=-H_\perp^+Q^\dagger\delta QP.$$

Nilpotency gives $\operatorname{im}Q\perp\operatorname{im}Q^\dagger$, so the exact and coexact branches are orthogonal. This identity must be checked directly against a finite-difference projector derivative and against the full resolvent response at reduced size.

The existing Kapit--Mueller and continuum-LLL parents enter the common formalism as one-sided positive-constraint complexes. Their current accepted outputs remain immutable. A new adapter may read their safe covariance artifacts but may not change their physical $R_4$ arrays.

## Coupling ensemble and tangent panels

Draw the independent complex coefficients $C_{ijk}$ from the standard isotropic Gaussian SYK ensemble and normalize the full three-form to unit norm. Overall normalization does not move the BPS projector, so it cannot affect the normalized response law.

At every accepted base point construct two $m=8$ tangent panels:

1. **Primary sparse panel:** individual cubic coupling coordinates, selected by a deterministic seed and orthogonalized after projection away from null moduli directions;
2. **Secondary isotropic panel:** deterministic complex Gaussian coupling combinations, projected and orthonormalized in the same tangent metric.

Project away the real radial direction $C$ and the overall phase direction $iC$. Both leave the BPS projector invariant. Reject any panel whose supported channel-label covariance has rank below eight; do not replace it after an $R_4$ outcome is inspected.

The uncertainty unit is a complete disorder realization, not an individual tangent direction or tensor entry. Panels from the same realization remain grouped in every bootstrap.

## Safe Hodge signature

Before opening any connected four-point outcome, expose only:

$$T_\pm=\sum_{a=1}^{m}\lVert X_{a,\pm}\rVert_F^2,\qquad \eta_H=\frac{4T_+T_-}{(T_++T_-)^2},$$

plus:

- branch-resolved target covariance spectra;
- branch-resolved complement covariance spectra;
- effective ranks and normalized spectral entropies derived from those spectra;
- exact/coexact orthogonality residual;
- charge-sector identity, BPS rank, external gap, and kernel residual;
- particle-hole and expected Altland--Zirnbauer symmetry labels;
- input seeds, source hashes, array hashes, and numerical tolerances.

Safe JSON and NPZ artifacts must fail a serialized-key audit if they contain `R4`, `four_point`, `connected`, or an outcome-sidecar payload.

## Competing finite-size nulls

The existing collapsed null samples one separable Gaussian response using the combined target and complement covariance spectra. It remains a frozen competitor.

The new Hodge-resolved null samples the two branches independently,

$$G_{a,\pm}=R_\pm^{1/2}Z_{a,\pm}L_\pm^{1/2},$$

forms the orthogonal direct sum $G_a=G_{a,-}\oplus G_{a,+}$, applies the same complete channel whitening, and evaluates the same gauge-invariant four-channel tensor and normalized $R_4$. The one-sided Laughlin null must be recovered exactly when one branch weight is zero.

The null uses measured two-point covariance spectra but no physical four-point number. Random streams for safe covariance generation, Gaussian reference generation, and physical disorder are disjoint and recorded.

## Information barrier and sequential test

Every physical response checkpoint is split into:

1. a safe metadata/array pair containing generators, Hodge branches, covariance spectra, gaps, residuals, and hashes;
2. a separately hashed `.outcome.json` sidecar containing physical $R_4$ and only the metadata needed to identify the case.

The $N=8,10,12$ outcomes may be opened sequentially after their internal gates pass, but they cannot change the observable, panel construction, null definitions, or $N=14$ identities. The $N=14$ safe covariates are aggregated first. Both collapsed-null and Hodge-null numerical intervals are written atomically and sealed with SHA-256 before the unseal command is permitted to read any $N=14$ sidecar.

## Controls and falsification gates

1. **Analytic decomposable control:** use $C_3=A_1^{(1)}\wedge A_1^{(2)}\wedge A_1^{(3)}$ and tangent directions preserving the decomposable locus. Recover the analytic curvature atoms $0,\pm1/\alpha^2$ and their multiplicities at reduced size.
2. **Gauge covariance:** independent random basis rotations in the BPS fiber and both complement branches leave every scalar, covariance spectrum, and $R_4$ unchanged.
3. **Projector derivative:** centered finite differences agree with $X_-\oplus X_+$ after optimal subspace alignment.
4. **Resolvent identity:** the branch sum agrees with the direct $-H_\perp^+(\partial H)P$ computation.
5. **Hodge orthogonality:** $\lVert X_-^\dagger X_+\rVert_F$ is below a registered relative tolerance.
6. **One-sided regression:** setting either branch to zero reproduces the accepted one-sided Wick implementation at machine precision.
7. **Corruption tests:** changed outcome identity, source hash, seed, prediction hash, or premature outcome access must fail closed.

## Frozen result branches

The final inference selects exactly one primary branch:

- `strong_covariance_universality`: both the collapsed and Hodge-resolved nulls cover the registered $N=14$ central/adjacent primary cases;
- `hodge_resolved_geometric_eth`: the Hodge-resolved null covers the complete registered $N=14$ primary pair while the collapsed null does not;
- `cohomological_non_gaussian_class`: neither null covers the registered pair, but a reproducible non-Gaussian excess survives all numerical and disorder checks;
- `structured_cohomology`: generic-coupling cases cannot be statistically separated from the decomposable structured control under the frozen diagnostics;
- `feasibility_failure`: expected BPS rank, open gap, Hodge support, response identity, or prediction seal fails.

Monotonic decrease with $N$ is secondary evidence only. No asymptotic exponent or thermodynamic limit may be claimed from four sizes without a successful held-out law.

## Publication claim boundary

A successful Hodge prediction supports a response-complex classification of geometric chaos across a non-SUSY topological zero-mode manifold and a SUSY cohomological BPS manifold. It does not establish conventional energy-resolved ETH, real-time chaos, a thermodynamic theorem, or a universal law for all parent Hamiltonians.

The generic $\mathcal N=2$ SYK benchmark is a cross-protection-mechanism test, not an independent discovery of SYK Berry chaos. A later spatially local nilpotent-supercharge model is required to claim spatial-locality universality.

## Deliverables

- a task-local sparse fermionic supercharge and charge-sector backend;
- exact BPS/Hodge response and validation tests;
- safe/outcome checkpoint writer with an enforced information barrier;
- collapsed and Hodge-resolved Gaussian null generators;
- sequential $N=8,10,12$ inference and sealed $N=14$ predictor/unsealer;
- analytic decomposable-three-form control;
- generated JSON/NPZ inference artifacts and a publication figure;
- a source-backed report stating the selected branch and claim boundary;
- synchronized task and main dashboards;
- a full task-local regression, corruption, provenance, and delivery audit.
