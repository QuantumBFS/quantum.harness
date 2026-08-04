# SUSY/cohomological third-model source audit

Date: 2026-08-01
Status: discussion-stage literature and novelty audit; no numerical outcome has been inspected or generated.

## Scientific question

Can the covariance-whitened, gauge-invariant response statistic already used for the Kapit--Mueller and continuum-LLL Laughlin parents distinguish a one-sided frustration-free constraint kernel from a genuinely two-sided supersymmetric cohomology, without fitting the third model's four-point result?

The intended third-model benchmark is the generic cubic $\mathcal N=2$ SYK complex,

$$Q(C)=\sum_{i<j<k}C_{ijk}\psi_i\psi_j\psi_k,\qquad Q^2=0,\qquad H=\{Q,Q^\dagger\},$$

in a fixed central $R$-charge sector. Its BPS fiber is the harmonic cohomology

$$\mathcal H_{\mathrm{BPS},r}=\ker Q_r\cap\ker Q_{r-3}^\dagger.$$

For a coupling tangent $\delta Q$, the complement response of a BPS state separates into the orthogonal exact and coexact Hodge branches

$$X(\delta C)=-H_\perp^+\bigl[Q\,\delta Q^\dagger+Q^\dagger\delta Q\bigr]P\equiv X_-\oplus X_+,$$

because $\operatorname{im}Q$ and $\operatorname{im}Q^\dagger$ are orthogonal when $Q^2=0$. By contrast, the two current Laughlin parents have a one-sided positive-constraint response. This makes branch number, Hodge balance, branch effective ranks, and branch covariance spectra available before any connected four-point statistic is opened.

## Primary-source boundary

- [Fu, Gaiotto, Maldacena, and Sachdev, *Supersymmetric SYK models*](https://arxiv.org/abs/1610.08917) introduced the supersymmetric SYK construction and its $\mathcal N=2$ version with exact supersymmetric ground states. It is the canonical model source.
- [Chang, Chen, Sia, and Yang, *Fortuity in SYK Models*](https://arxiv.org/abs/2412.06902) established that generic-coupling $\mathcal N=2$ SYK BPS states are fortuitous and concentrated in central charge sectors, and formulated the supercharge-chaos conjecture. It supplies the physical reason to use the generic rather than decomposable supercharge.
- [Chen, Lin, and Shenker, *BPS Chaos*](https://arxiv.org/abs/2407.19387) developed projected-operator diagnostics inside protected sectors and the smooth-state/black-hole-microstate contrast.
- [Chen, Colin-Ellerin, Mamroud, and Papadodimas, *Chaos of Berry curvature for BPS microstates*](https://arxiv.org/abs/2604.23287) already computed non-Abelian Berry curvature in generic $\mathcal N=2$ SYK, including curvature level repulsion, number variance, spectral form factors, exact decomposable-three-form controls, and moduli-space topology. Reproducing only these curvature spectral statistics would not be a new result.
- [Miyahara and Shibuya, *Chaos-Integrability Transition in the BPS Subspace of the $\mathcal N=2$ SYK Model*](https://arxiv.org/abs/2605.20913) already studied a projected-operator chaos-to-integrability crossover within the same BPS subspace. A generic-versus-integrable crossover alone is therefore also below the novelty threshold.
- [Zhang, Sukeno, Ikeda, and Wei, *Local symmetries and extensive ground-state degeneracy of a 1D supersymmetric fermionic chain*](https://arxiv.org/abs/2412.17208) proves exponential zero-mode degeneracy in a spatially local SUSY chain and gives structured states built from immobile walls. This is a strong later negative control, but a stable multidimensional deformation with fixed charge-resolved cohomology and open gap must be demonstrated before it can replace the canonical SYK benchmark.
- [Huijse and Schoutens, *Supersymmetry, lattice fermions, independence complexes and cohomology theory*](https://arxiv.org/abs/0903.0784) supplies the cohomological language for local lattice realizations and clarifies that cohomology counting alone does not determine how harmonic representatives move in parameter space.
- [Jiang and Zhou, *Eigenvalue Statistics of Random Quantum Geometry*](https://arxiv.org/abs/2606.27809) raises the benchmark for claims based only on quantum-geometric eigenvalue statistics. The present extension must therefore operate at the response-matrix/four-point level and include a physical structural predictor.

## Novelty conclusion

The publishable unit is not “Berry curvature in $\mathcal N=2$ SYK.” That calculation exists. The distinct target is a common response-complex formalism across non-SUSY topological parents and SUSY cohomology, with a preregistered two-point Hodge signature and an unseen four-point test. A positive result would identify a mechanism-level geometric-chaos class; a negative result would delimit precisely which covariance information fails to predict higher-order quantum geometry.

The lowest-risk benchmark is generic $\mathcal N=2$ SYK because its BPS degeneracy, charge sectors, fortuity, and curvature chaos are independently established. The higher-novelty follow-up is a spatially local nilpotent supercharge, but only after the exact zero-mode-count, gap, and nontrivial-projector-motion feasibility gates pass.

## Proposed pre-outcome quantities

For every accepted response panel, keep the four-point outcome in a sealed sidecar and expose only:

1. the exact/coexact branch weights $T_\pm=\sum_a\lVert X_{a,\pm}\rVert_F^2$;
2. the Hodge balance $\eta_H=4T_+T_-/(T_++T_-)^2$, with $\eta_H=0$ for a one-sided response and $\eta_H=1$ for exactly balanced branches;
3. branch-resolved target and complement covariance spectra and their effective ranks;
4. the numerical orthogonality residual between $\operatorname{im}Q$ and $\operatorname{im}Q^\dagger$;
5. BPS nullity, external gap, charge-sector identity, and particle-hole/AZ symmetry class.

These data may choose between a one-sided and a signed two-sided Gaussian null, but they may not be used to fit the sealed physical $R_4$. A third-model prediction is scientifically meaningful only if the null, channel panel, size split, aggregation unit, and branch decision are fixed first.
