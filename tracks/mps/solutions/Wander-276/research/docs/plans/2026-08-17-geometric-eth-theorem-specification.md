# Effective-channel theorem for Geometric ETH

## Scope

This specification freezes the analytic claim before any v14 channel data are
generated. It concerns the off-fiber projector response in an exactly
degenerate, externally gapped quantum-state bundle. It does not assert
conventional eigenstate thermalization, real-time thermalization, spectral
chaos, or a universal law for protected Hamiltonians.

The first result is exact weighted cumulant additivity for independent
centered complex channels. A conditional \(1/N_{\mathrm{eff}}\) law follows
only after variance normalization and a comparability assumption on
single-channel fourth cumulants. A separate proposition concerns the
response-algebra commutant. That proposition is an irreducibility diagnostic;
it does not imply Gaussianity or ETH.

## Complex response variables

Let \(\mathcal V=\operatorname{Hom}(P\mathcal H,Q\mathcal H)\) be the complex
space of rectangular response matrices at a fixed protected projector \(P\).
Cumulants are defined on the realification of \(\mathcal V\), which retains
mixed holomorphic and antiholomorphic contractions. Let

$$Y_\alpha\in\mathcal V,\qquad \mathbb E Y_\alpha=0,\qquad \alpha=1,\ldots,n,$$

be independent centered complex channels, and write
\(y_\alpha=\operatorname{vec}(Y_\alpha)\). Their complete second moments are
the ordinary covariance and pseudocovariance

$$C_\alpha=\mathbb E(y_\alpha y_\alpha^\dagger),\qquad P_\alpha=\mathbb E(y_\alpha y_\alpha^T).$$

Here \(P_\alpha\) denotes pseudocovariance, not the protected projector.
Ordinary covariance alone specifies a complete complex Gaussian null only
after properness, \(P_\alpha=0\), has been established.

Let \(w_\alpha\in\mathbb R\) be deterministic normalized weights. The
canonical convention is \(\sum_\alpha w_\alpha^2=1\), although all formulas
below are scale invariant. Define

$$Z=\sum_\alpha w_\alpha Y_\alpha,\qquad z=\operatorname{vec}(Z).$$

Centering and independence give

$$C_Z=\sum_\alpha w_\alpha^2C_\alpha,\qquad P_Z=\sum_\alpha w_\alpha^2P_\alpha.$$

Both tensors enter the three complex Wick pairings. The connected fourth
tensor is defined only after subtracting the Wick tensor built from both
\(C_Z\) and \(P_Z\).

## Cumulant convention

For real-linear functionals
\(f_1,\ldots,f_k:\mathcal V\rightarrow\mathbb R\), set

$$\kappa_k(Y)[f_1,\ldots,f_k]=\operatorname{cum}\!\left(f_1(Y),\ldots,f_k(Y)\right).$$

Equivalently, \(\kappa_k(Y)\) is the order-\(k\) derivative tensor of the log
characteristic function on the realification of \(\mathcal V\). Complex trace
words are obtained by complexifying this real multilinear tensor. At
\(k=4\), it is the connected tensor obtained by subtracting all three
pairings fixed by ordinary covariance and pseudocovariance.

## Theorem: weighted cumulant additivity

### Assumptions

1. The variables \(Y_\alpha\) are mutually independent, not merely pairwise
   uncorrelated.
2. They are centered: \(\mathbb E Y_\alpha=0\).
3. The weights \(w_\alpha\) are deterministic and fixed independently of the
   observed channel outcomes.
4. An order-\(k\) statement requires finite \(k\)-th absolute moments of
   every tested real-linear projection. The fourth-order conclusion assumes
   finite fourth moments.
5. All variables occupy one common response space, or are identified with
   that space by a fixed, outcome-independent map.

### Conclusion

The exact tensor identity is

$$\kappa_k(Z)=\sum_\alpha w_\alpha^k\kappa_k(Y_\alpha).$$

This is weighted cumulant additivity at finite channel number, not a
central-limit approximation.

### Proof at specification level

For any real-linear test field \(t\), independence yields

$$\log\mathbb E e^{it(Z)}=\sum_\alpha\log\mathbb E e^{iw_\alpha t(Y_\alpha)}.$$

Taking \(k\) derivatives at the origin contributes one factor of
\(w_\alpha\) per derivative and produces no mixed-channel connected term.
Polarization over \(k\) test fields proves the tensor identity. A complex
trace contraction is a linear combination of these real multilinear
components, so the same identity applies.

## Corollary: effective-channel law

Define

$$N_{\mathrm{eff}}=\frac{(\sum_\alpha w_\alpha^2)^2}{\sum_\alpha w_\alpha^4}.$$

For L2-normalized weights,
\(\sum_\alpha w_\alpha^4=1/N_{\mathrm{eff}}\). Equal weights give
\(N_{\mathrm{eff}}=n\); a concentrated profile gives a smaller participation
number.

The exact theorem alone does not make the channel cumulants equal. The
\(1/N_{\mathrm{eff}}\) conclusion needs three additional assumptions.

### Additional assumptions for variance normalization

1. Each active channel is variance-normalized in the tested contraction. In a
   scalar projection, \(\mathbb E|f(Y_\alpha)|^2=1\). A matrix calculation may
   instead use a fixed real-augmented whitening that retains ordinary
   covariance and pseudocovariance.
2. The standardized fourth cumulants are comparable. Exact equality assumes
   \(\kappa_4(Y_\alpha)=K_4\) in the tested tensor direction. The bound form
   assumes \(\|\kappa_4(Y_\alpha)\|\leq K\) in a fixed tensor norm.
3. No outcome-dependent rescaling, channel selection, or tangent refit occurs
   after fourth-order data are opened.

With identical standardized channel cumulants,

$$\frac{\kappa_4(Z)}{(\sum_\alpha w_\alpha^2)^2}=\frac{K_4}{N_{\mathrm{eff}}}.$$

With only the uniform norm bound,

$$\frac{\|\kappa_4(Z)\|}{(\sum_\alpha w_\alpha^2)^2}\leq\frac{K}{N_{\mathrm{eff}}}.$$

The exponent is derived, not fitted. A numerical audit must compare directly
with this fixed inverse-participation prediction.

For unequal known standardized channel cumulants, the prediction is

$$\kappa_{4,\mathrm{pred}}(Z)=\frac{\sum_\alpha w_\alpha^4\kappa_4(Y_\alpha)}{(\sum_\alpha w_\alpha^2)^2}.$$

This expression, rather than the identical-channel specialization, defines
the general executable interface.

## Proposition: response algebra and irreducibility

Let the protected fiber have complex dimension \(D\), and let
\(X_a\in\operatorname{Hom}(P\mathcal H,Q\mathcal H)\) be the accessible
responses. Define the unital star-closed response algebra

$$\mathcal A_X=\operatorname{alg}^{*}\{X_a^\dagger X_b:a,b\}\subseteq\operatorname{End}_{\mathbb C}(P\mathcal H)$$

and its commutant

$$\mathcal A_X'=\{M:[M,A]=0\text{ for every }A\in\mathcal A_X\}.$$

For a finite-dimensional complex star algebra, a nontrivial invariant
subspace has an invariant orthogonal complement and supplies a nonscalar
projection in the commutant. Therefore
\(\mathcal A_X'=\mathbb C I_D\) implies irreducibility. Burnside's theorem
then gives
\(\mathcal A_X=\operatorname{End}_{\mathbb C}(P\mathcal H)\).

The claim used here is weaker than the mathematical equivalence. A nonscalar
commutant falsifies unrestricted full-matrix mixing unless invariant blocks
are first resolved. A scalar commutant is only an irreducibility diagnostic.
Irreducibility is necessary for that strong full-matrix ansatz, but
irreducibility alone does not imply Gaussianity or ETH, fourth-cumulant
suppression, locality, thermalization, or a large-\(D\) limit. Deterministic
matrices can generate the full matrix algebra without statistical closure.

## Failure branches

- **Correlated channels.** Mixed connected cumulants survive, so weighted
  cumulant additivity acquires cross-channel terms. Zero covariance is not
  independence.
- **Heavy-tailed channels without fourth moments.** The connected fourth
  tensor and its inverse-participation normalization are undefined.
- **Growing single-channel dominance.** If
  \(\max_\alpha w_\alpha^2/\sum_\beta w_\beta^2\) does not vanish, then
  \(N_{\mathrm{eff}}\) need not grow with the nominal channel count.
- **Symmetry-unresolved blocks.** A nonscalar commutant mixes invariant
  sectors in one statistic. Closure must be tested in resolved blocks.
- **Nonstationary tangent ensembles.** Size-dependent or outcome-dependent
  changes to the channel population invalidate a comparison based only on
  \(N_{\mathrm{eff}}\).
- **Closing external gap.** The isolated-projector response loses control;
  a divergent reduced resolvent is not channel proliferation.
- **Incomplete complex covariance.** Omitting pseudocovariance removes one
  Wick pairing. Rejection of that restricted null is not a complete-cumulant
  result.
- **Noncomparable channel cumulants.** Exact additivity remains true when
  moments exist, but the uniform \(K/N_{\mathrm{eff}}\) bound need not follow.

## Executable audit contract

The analytic module checks weight normalization, equal- and unequal-weight
predictions, and commutant dimensions for reducible and irreducible matrix
sets. Its Monte Carlo oracle uses centered non-Gaussian complex channel
matrices with finite moments and zero pseudocovariance. Equal and unequal
weights are tested at channel counts \(4,8,16,32,64\). The audit records the
fixed seed, matrix draws, block uncertainty, empirical ordinary covariance,
empirical pseudocovariance, and direct relative error from the fixed
\(1/N_{\mathrm{eff}}\) law. It passes only if the maximum relative error is
at most \(0.08\). No exponent is fitted.

The raw double-precision Monte Carlo observables and every pass/fail decision
are evaluated before serialization. For the portable JSON record and its
scientific SHA-256 signature, every finite floating-point leaf is then
canonically rounded to 10 significant decimal digits. This precision is far
finer than the registered \(0.08\) relative-error threshold and removes only
cross-BLAS last-bit variation observed in near-zero covariance entries. The
quantization applies to serialization and
signature only; it does not alter the raw Monte Carlo calculation, its
uncertainty estimate, or any gate. Non-finite values are rejected rather than
serialized. Cold-start regression tests compare complete output bytes and
scientific hashes under distinct BLAS thread environments.
