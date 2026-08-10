# Challenge #15 design: intrinsic-symmetry NQS for the ν=1/3 sphere graviton

## 1. Purpose and claim boundary

The challenge asks for an exchange-antisymmetric, rotationally equivariant
neural quantum state (NQS) for spin-polarized electrons in the lowest Landau
level (LLL) on the Haldane sphere, and for the finite-size neutral-sector
quantity

```text
Δ₂(N) = E_lowest(L=2; N) - E_ground(L=0; N).
```

The minimum deliverable will call this quantity the **finite-size lowest-L=2
sector gap**. Exact `L=2`, `⟨L²⟩=6`, and the five-component rotational
multiplet certify spin 2, but do not by themselves certify chirality or a
graviton response pole.

The stronger deliverable may call the state a **chiral graviton** only after a
spherical metric-response calculation shows that the same low-energy `L=2`
level carries dominant spectral weight in the expected chiral channel and a
suppressed opposite channel. No thermodynamic claim will be made from only
`N=6–8`.

## 2. Fixed physical model

All calculations use the following convention unless a result explicitly says
otherwise:

- `N` fully spin-polarized electrons.
- Filling `ν=1/3` on the Haldane sphere.
- Laughlin shift `S=3`.
- Monopole flux `Nφ=2Q=3(N-1)`.
- One-particle LLL angular momentum `l=Q`, with orbitals
  `m=-Q,-Q+1,...,Q`.
- Number of one-particle LLL orbitals `2Q+1=3N-2`.
- Sphere radius `R=√Q ℓ_B`.
- Physical chord distance
  `r_ij=2R sin(γ_ij/2)`.
- Electron interaction
  `V_ij=(e²/(4π ε₀ ε))/r_ij`.
- Energy unit `E_C=e²/(4π ε₀ ε ℓ_B)`.

Finite-`Q` spherical Coulomb matrix elements are required. Planar
pseudopotentials must not be substituted for them.

A uniform neutralizing shell contributes an `N,Q`-dependent constant. It
cancels from `Δ₂(N)` because both states have the same `N,Q`. Raw
electron-electron energies and background-corrected total energies will be
stored separately; no density-rescaling convention will be applied silently.

The implementation records:

- monopole-harmonic phase convention;
- north/south gauge-chart convention;
- orbital ordering;
- creation-operator ordering;
- whether two-body integrals are stored before or after antisymmetrization;
- the location of the Hamiltonian's `1/2` factor.

## 3. Physical Hilbert space

The one-electron LLL is the monopole line-bundle section space `V_Q`, the
spin-`Q` irreducible representation of `SU(2)`. The many-electron Hilbert space
is the exterior power

```text
H_N,Q = ∧^N V_Q.
```

Its computational basis consists of ordered occupation determinants

```text
c†_{m1} c†_{m2} ... c†_{mN} |0⟩,  m1 < m2 < ... < mN.
```

This choice enforces simultaneously:

- fixed particle number;
- fixed monopole flux;
- exact LLL membership;
- Fermi antisymmetry;
- a deterministic fermionic sign convention.

In coordinate space, each particle coordinate is a holomorphic homogeneous
monopole section of degree exactly `2Q`. A generic coordinate neural factor
would violate this condition. The production ansatz therefore uses only
finite-degree holomorphic monopole harmonics, Pfaffians/determinants, linear
combinations, rotations, and exact band-limited projection. The occupation
space remains the independent small-system oracle.

## 4. Symmetry content

### 4.1 Required symmetries

The ansatz must contain these structures by construction:

1. Fixed global particle-number `U(1)`.
2. Fermionic permutation sign.
3. Monopole-bundle local `U(1)` gauge covariance.
4. `SU(2)` rotational covariance of monopole harmonics.
5. Exact total angular momentum `L=0` or `L=2`.

At `2Q=3(N-1)`,

```text
2QN = 3N(N-1)
```

is always even. The many-body central element therefore acts trivially and the
physical many-electron multiplets have integer `L`, so the final representation
factors through `SO(3)`. `SU(2)` remains the correct construction group because
the one-particle monopole representation may be half-integer.

### 4.2 Symmetries that must not be imposed

- Spatial reflection and parity reverse the monopole orientation and generally
  map the `Q` bundle to the `-Q` bundle.
- Time reversal flips the magnetic field and `Q`.
- Electron spin rotation is absent because the problem is fully spin-polarized.
- Particle-hole symmetry is not required by the challenge.
- No planar center-of-mass projection is added on the sphere.

Chirality is a response property, not an additional invariance imposed on the
wavefunction.

## 5. Symmetry-only oracle decomposition

Construct a Hamiltonian-independent isometry

```text
T_L : V_L ⊗ M_L → ∧^N V_Q
```

such that

```text
∧^N V_Q = ⊕_L (V_L ⊗ M_L).
```

`V_L` carries the standard `(2L+1)`-dimensional irrep and `M_L` is the
multiplicity space on which rotations act trivially.

The isometry may be generated from `L²`, `L_z`, and ladder operators, but not
from eigenvectors of the target Coulomb Hamiltonian. No energy-selected
low-dimensional subspace is allowed in the decoder. This prevents target-state
leakage. Complete `T_L` matrices are constructed only for small-system
validation; the production NQS never builds or contracts them.

The basis inside `M_L` has an independent `U(dim M_L)` convention. The
implementation fixes it deterministically by:

1. a fixed occupation ordering;
2. fixed Clebsch–Gordan and ladder phases;
3. a lexicographically pivoted row reduction or rank-revealing QR of the
   symmetry-generator nullspace;
4. deterministic sign/phase normalization of every accepted pivot column.

No auxiliary operator is used to split multiplicities: `SU(2)` alone does not
select an operator acting nontrivially on `M_L`, so such an operator would add
an extra convention and could leak target information if chosen from the
Hamiltonian. Numerical rank tolerances, pivots, and resulting basis hashes are
stored.

Changing this convention must leave reconstructed physical amplitudes and
observables unchanged after applying the corresponding multiplicity-space
unitary transformation.

## 6. Production NQS: holomorphic Pfaffian carriers with exact SU(2) projection

### 6.1 Fixed-degree carriers

Let `φ_m(z)` be the declared-gauge monopole harmonic in `V_Q`, written as a
holomorphic homogeneous polynomial of degree `2Q` in the particle spinor
`z=(u,v)`.

For even `N`, carrier `s` is the Pfaffian

```text
Φ_s(z_1,...,z_N; L) = Pf[G_s],
G_s(i,j;L) =
  Σ_{m>0} g_s(m/Q,L)
  [φ_m(z_i)φ_-m(z_j) - φ_m(z_j)φ_-m(z_i)].
```

For odd `N`, `Q` is integer at the Laughlin shift. The carrier is the bordered
Pfaffian

```text
Φ_s = Pf([G_s  h_s; -h_s^T  0]),
h_s(i;L) = b_s(L) φ_0(z_i).
```

Every Pfaffian term contains each particle exactly once. It is therefore:

- antisymmetric under particle exchange;
- holomorphic of degree exactly `2Q` in every particle;
- an exact state of `∧^N V_Q`;
- gauge covariant with the product monopole-chart phase;
- exactly in the `M_z=0` sector because every pair has `m+(-m)=0`, with an
  `m=0` blocked orbital for odd `N`.

The unprojected variational state is a rank-`χ` mixture

```text
Φ_θ(z;L) = Σ_{s=1}^χ a_s c̃_s(θ,L) Φ_s(z;L).
```

One shared complex hypernetwork independently generates `g_s(m/Q,L)`,
`b_s(L)`, and `c̃_s(L)` from fixed Fourier features of `m/Q`, a carrier token,
and the target-sector token `L∈{0,2}`. The explicit complex gate `a_s` is the
only parameter added with a carrier. There is no softmax, batch normalization,
or other cross-carrier normalization whose value changes when `χ` changes.
The same parameter set `θ`, normalization convention, and carrier bank serve
both sectors. There is no parameter indexed by a determinant or by an exact
multiplicity-basis vector.

`χ` is a controlled approximation parameter. Results are reported only after
rank convergence; no claim is made that fixed `χ` represents the Laughlin
correlation structure uniformly in `N`.

Ranks follow the nested sequence `χ=1,2,4,...`. When rank doubles, the prior
state is embedded exactly by copying the old carrier tokens, gates, and
hypernetwork parameters bit-for-bit, then initializing only the new gates
`a_s=0`. The largest reported rank must have two preceding ranks unless a
complete small-`N` projected span has already been reached.

### 6.2 Exact band-limited angular-momentum projection

Because every carrier is a laboratory `M_z=0` state, the projector's right
index is `K=0` and the Euler angle `γ` is trivial. The left angle `α` is still
required: after a `y` rotation it projects the coordinate-space amplitude back
to laboratory `M=0`. The exact projector is therefore the two-dimensional
integral

```text
Ψ_L0(z;θ) =
  (2L+1)/(4π) ∫_0^{2π} dα ∫_{-1}^{1} dx P_L(x)
  [R_z(α) R_y(arccos x) Φ_θ](z;L).
```

The many-body LLL has integer total angular momenta bounded by

```text
L_max = NQ.
```

The `α` dependence is band-limited to Fourier modes
`-L_max,...,L_max`. An equispaced periodic rule is exact with

```text
n_α ≥ 2 L_max + 1.
```

After that Fourier projection selects laboratory `M=0`, the remaining
`x=cos β` dependence is a linear combination of `d^J_00(β)=P_J(x)` with
`J≤L_max`. Gauss–Legendre quadrature is exact in exact arithmetic when

```text
2 n_β - 1 ≥ L_max + L.
```

Production uses at least

```text
n_α = 2 L_max + 1,
n_β = ceil((L_max + L + 1)/2)
```

or a larger validation order. Thus the projection error is floating-point and
quadrature-conditioning error, not an uncontrolled discretization of SU(2).

The quadrature and rotations are immutable architecture layers. They are not
loss penalties and do not use the Coulomb Hamiltonian. `L=0` and `L=2` differ
only through the sector token and fixed projector kernel.

The other `L=2` components are generated from `Ψ_20` using the exact ladder
operators or the corresponding `P^2_M0` projector. They never receive separate
neural parameters.

### 6.3 Evaluation strategy

JAX evaluates quadrature nodes, carriers, walkers, and `M` components in
blocked batches. The periodic `α` sum is implemented as an exact discrete
Fourier projection. Rotated one-particle monopole matrices, Fourier phases, and
Legendre weights are cached. Pfaffians use pivoted skew factorization with a
custom derivative or a verified stable library primitive; mixtures use a
phase-aware complex log-sum-exp.

The nominal amplitude cost is

```text
O(n_α n_β χ N^3)
```

per unbatched walker, with blocked rotations sharing one-particle work. Peak
memory is bounded by the configured quadrature-block size rather than by
`n_α n_β χ` all at once.

Production coordinate VMC samples

```text
|Ψ_L0(z)|² ∏_i dΩ_i/(4π)
```

with labeled-particle local `SU(2)` rotation proposals; the probability density
is permutation symmetric. Proposal widths are adapted during burn-in and then
frozen. Independent chains mix single-particle rotations with occasional
all-particle rigid rotations.

For an LLL variational state,

```text
⟨Ψ|P_LLL V P_LLL|Ψ⟩ = ⟨Ψ|V|Ψ⟩.
```

The bare chord-Coulomb value `V(z)` is therefore an unbiased multiplicative
estimator of the variational energy. With
`O_θ(z)=∂_θ log Ψ_θ(z)`, the gradient estimator is the score covariance

```text
∂_θ E =
  2 Re[⟨O_θ* V⟩ - ⟨O_θ*⟩⟨V⟩].
```

`V(z)` by itself is **not** a gradient estimator and is not the pointwise
projected-Hamiltonian local energy
`[P_LLL(VΨ)](z)/Ψ(z)`, and the Monte Carlo variance of `V(z)` is not reported as
the Hamiltonian energy variance.

For `N≤8`, projected Pfaffian coefficients are also expanded in the ordered
determinant basis using the same finite quadrature. This gives direct overlap,
energy, the true `H_LLL` variance, and symmetry comparisons with the independent
occupation oracle. Occupation-space work is exact enumeration/oracle
evaluation, not the production Monte Carlo sampler.

## 7. Hamiltonian oracle

Two independent finite-sphere Coulomb builders are required:

1. Direct two-body matrix elements from monopole harmonics and the spherical
   multipole expansion of `1/r_12`.
2. Finite-`Q` spherical pair pseudopotentials, transformed to the orbital basis
   with independently evaluated angular-momentum coefficients.

For electrons, only Pauli-allowed odd relative angular momenta contribute.

The builders must agree on:

- every two-particle pseudopotential;
- representative orbital matrix elements;
- low-energy spectra for `N=2` and small many-body systems;
- Hermiticity and angular-momentum conservation.

The ED oracle scans all accessible low-lying `L` sectors. It does not inspect
only `L=0` and `L=2`, so the report can distinguish the requested sector gap
from the absolute lowest neutral excitation.

Initial sizes are:

- `N=6`, `2Q=15`, 16 orbitals, full dimension 8008;
- `N=7`, `2Q=18`, 19 orbitals, full dimension 50388;
- `N=8`, `2Q=21`, 22 orbitals, full dimension 319770.

## 8. Optimization and statistical evaluation

The `L=0` and `L=2` sectors are orthogonal by construction. Sector-specific
warm-up phases are allowed only as optimizer initialization while retaining the
same shared parameterization. The reported result is then jointly optimized
with the single network and the state-averaged objective

```text
loss = w_0 E_0 + w_2 E_2
```

after both projected sectors pass their own finite-amplitude, norm, and
conditioning checks. Neither sector may freeze an independent private copy of
`θ`.

For `N≤8`, the first acceptance result uses exact sums over the finite
symmetry-adapted basis. This separates ansatz/optimization error from Monte
Carlo error.

The production Monte Carlo path samples sphere coordinates from the measure
defined in Section 6.3. It uses:

- independent post-training evaluation chains;
- burn-in;
- autocorrelation-aware blocking;
- effective sample size;
- split-chain diagnostics;
- bootstrap or jackknife confidence intervals;
- at least five independent optimization and sampling seeds;
- separate reporting of within-seed and between-seed variation;
- bare-potential estimator variance, labeled only as sampling variance.

The true projected-Hamiltonian variance is reported only where the
occupation-space oracle or an explicitly projected application of
`H_LLL` is available.

Shared parameters and correlated evaluation may reduce statistical error in
the gap. No cancellation of variational bias is assumed.

## 9. Spin-2 and multiplet certification

The implementation verifies:

```text
L² |ψ_LM⟩ = L(L+1) |ψ_LM⟩
```

and the ladder identities for all `M`. Exact projection, or equivalently zero
variance of `L²`, is required; the expectation value `⟨L²⟩=6` alone is
insufficient.

An `M=0` diagonalization contains one representative of each `L=2` copy, not
five repeated eigenvalues. Fivefold degeneracy is checked by reconstructing or
diagonalizing the corresponding `M=-2,...,2` components and verifying equal
energies and correct ladder norms.

The five components form one rotational multiplet. They are not interpreted as
five separate modes, nor are `M=±2` identified directly with the two chiral
helicities.

## 10. Chiral LHYR-response extension

Fix the outward sphere orientation, electron charge `-e`, and `Q>0`; in this
convention the ν=1/3 Laughlin graviton selected by the
Liou-Haldane-Yang-Rezayi (LHYR) probe has angular momentum/helicity `-2`.

The strong deliverable uses the exact finite-sphere Wigner–Eckart
covariantization of the LHYR planar, LLL-projected Coulomb source. The round
spatial sphere, its area, radius `R=√Q ℓ_B`, integration measure, scalar
finite-sphere Coulomb Hamiltonian, and physical chord distance remain fixed.
The source is a separate response operator; it does not deform the chord
interaction or the sphere.

With `k=q ℓ_B`, `k_±=k_x±i k_y`, and
`V(q)=2π E_C ℓ_B/q`, fix the planar pair-counted source and its overall phase
by

```text
S_- = -Σ_{i<j} ∫d²q/(2π)² V(q) exp(-k²/2) k_-²
      exp[iq·(R_i-R_j)],
S_+ = S_-†.
```

Equivalently, for the planar inverse-mass coordinates
`G(h)=[[1+h₁,h₂],[h₂,1-h₁]]+O(h²)`,
`h_±=h₁±ih₂`, and
`∂_{h_±}=(∂_{h₁}∓i∂_{h₂})/2`, the normalization is
`S_-=4∂_{h_+}H_proj|₀` and `S_+=4∂_{h_-}H_proj|₀`. This planar identity fixes
the common energy normalization; it is not promoted to a curved-sphere
material metric.

For odd relative angular momentum `r`, define the exact positive Coulomb
amplitude

```text
A_r/E_C =
  [2√((r+1)(r+2))]^-1
  Σ_{k=0}^r (-1)^k binom(r+2,r-k) Γ(k+5/2)/k!.
```

At flux `2Q`, retain `r=1,3,...,r_max`, where `r+2≤2Q`, and set
`J_b=2Q-r`, `J_k=J_b-2`. In the existing north-chart monopole convention,
ascending creation-operator order, and Condon–Shortley Clebsch–Gordan
convention, all five components are

```text
O^(2)_{-,M} =
  Σ_r A_r Σ_{M_k}
  ⟨J_k M_k; 2 M | J_b,M_k+M⟩
  |J_b,M_k+M⟩⟨J_k,M_k|,

O^(2)_{+,M} = (-1)^M (O^(2)_{-,-M})†,
M=-2,...,2.
```

The displayed Clebsch–Gordan sum is the direct reconstruction rule only for
`O_-`. Every `O_+` component is constructed only by the adjoint formula on the
second line. The same physical planar amplitudes `A_r` label both directions,
but the reversed `(J_b,J_k)` channel must not be inserted independently into
the displayed Clebsch sum: reduced-matrix-element conventions introduce a
dimension factor. For the bounded `2Q=3`, `r=1` case,
`J_b=2`, `J_k=0`,
`⟨0,0;2,2|2,2⟩=1`, whereas the forbidden reversed reconstruction gives
`⟨2,2;2,-2|0,0⟩=1/√5`.

Thus `O_-` maps `|r+2⟩ -> |r⟩`, while `O_+` maps
`|r⟩ -> |r+2⟩`. Here `r` is pair relative angular momentum, not a
one-particle orbital label or global component. The reduced-vector order is
ascending positive odd `r`, and its raw norm is
`[Σ_r |A_r/E_C|²]^(1/2)`. Production operators use the raw `A_r`; normalized
vectors are fixture diagnostics only.

The helicity label `σ∈{+,-}` and global spherical-tensor component
`M=-2,...,2` are distinct: `σ=±` must not be identified with `M=±2`. The
families obey

```text
(O^(2)_{+,M})† = (-1)^M O^(2)_{-,-M}.
```

The large-`Q` tangent-plane limit must reproduce

```text
O_∓ ∝ Σ_q (q_x ∓ i q_y)^2 V_q exp(-q²ℓ_B²/2) ρ̄_q ρ̄_-q
```

The binding pair-transition convention is specifically
`O_-: |m+2⟩ -> |m⟩`. A high-precision two-particle, large-`Q` fixture
verifies its amplitudes, phases, normalization, adjoint, and truncation; the
label is never assigned from `M=±2`.

The cited target literature does not uniquely define a local effective-mass
Hamiltonian, operator ordering, curvature coupling, tensor-harmonic drive, or
excited-Landau-level identification on a curved sphere. This deliverable
therefore forbids claiming that these operators are the unique derivative of
a curved-sphere effective-mass Hamiltonian. The binding derivation and claim
boundary are recorded in
`.superpowers/sdd/chiral-microscopic-source-resolution.md`.

The construction must:

1. be derived in the same monopole and phase convention as the Hamiltonian;
2. satisfy rank-two tensor commutators with `L_z` and `L_±` separately for both
   helicity families;
3. have documented normalization;
4. demonstrate that `Q→-Q` interchanges the complete `σ=+` and `σ=-`
   operator families;
5. obey the spectral sum rule
   `Σ_n |⟨n|O_σ|0⟩|² = ⟨0|O†_σ O_σ|0⟩`;
6. pass the `2Q=3`, `J_b=2`, `J_k=0` regression proving that direct
   reconstruction of `O_+` would incorrectly produce `A_1/√5`, while the
   required adjoint construction produces `A_1`.

For an `L=0` ground state and complete `L=2` eigensystem, define

```text
w_{σ,n} = Σ_{M=-2}^2 |⟨n,L=2,M|O^(2)_{σ,M}|0,0⟩|²,
W_σ = Σ_n w_{σ,n} = Σ_M ⟨0|O^(2)†_{σ,M} O^(2)_{σ,M}|0⟩,
f_σ = w_{σ,lowest}/W_σ,
ΔW = w_{-,lowest} - w_{+,lowest},
C = ΔW / (w_{-,lowest} + w_{+,lowest}).
```

Near-degenerate eigenstates are grouped before summing weights, making the
answer invariant under basis rotations inside a degenerate subspace. `C` is
reported as indeterminate when its denominator is below the declared numerical
floor. The spectral functions are

```text
I_σ(ω) = Σ_n |⟨n|O_σ|0⟩|² δ(ω-E_n+E_0).
```

The lowest `L=2` state is called a chiral graviton only if it carries a
statistically and numerically resolved dominant response in the `σ=-` channel,
with suppression of `σ=+`. The report preserves both normalized and
unnormalized weights.

This response extension is not replaced by comparing the `M=+2` and `M=-2`
members of the same rotational multiplet.

### 10.1 Implementation status and bounded runbook

The implemented response keeps the **round spatial sphere** and its
**Coulomb chord** interaction fixed. It is the finite-sphere
**Wigner–Eckart covariantization** defined above, with the binding transition
`|r+2⟩ -> |r⟩`; its `σ=±` families remain distinct from `M=-2,...,2`. The claim
boundary therefore **forbids claiming** a unique curved-sphere effective-mass
derivative.

The supported command forms are:

```bash
uv run python -m challenge15.cli response --particles N --output DIR
uv run python -m challenge15.cli response --oracle ORACLE --output DIR
uv run python -m challenge15.cli response \
  --oracle ORACLE \
  --generation GENERATION \
  --checkpoint CHECKPOINT \
  --rank RANK \
  --seed SEED \
  --output DIR
```

Each successful command atomically publishes `DIR/response.json` with schema
`challenge15.chiral-response.v1`. Exact-size routing supports `2 <= N <= 8`.
The mixed estimator is a mixed NQS-to-exact response contraction. It uses a
normalized NQS `L=0` initial state and exact ED `L=2` final states; it is not a
fully variational excited-state spectrum.

Acceptance requires both five-component tensor families to pass commutator
tolerance `1e-10`, adjoint and monopole-reversal tolerance `1e-12`, eigenpair
residual tolerance `1e-10`, and all channel sum rules with
`recovered_fraction>=0.99`. Artifact and strict-schema verification must also
pass before a result is accepted. Local verification is bounded to non-slow
tests and exact response sizes through `N=4`; response execution for `N=5..8`,
training, and production orchestration are deferred to approved compute
infrastructure.

The deferred production commands are recorded here and must not be executed
locally:

```bash
for n in 2 3 4 5 6 7 8; do
  uv run python -m challenge15.cli response \
    --particles "$n" \
    --output "tracks/qmc/results/frustration-free/challenge-15/chiral-response-n${n}"
done
```

Execution on approved compute infrastructure is accepted only after artifact
verification, tensor/adjoint/reversal gates, eigenpair residuals, and
`recovered_fraction>=0.99` pass.

## 11. Scaling policy and fusion research extension

The production scaling variables are `N`, carrier rank `χ`, and quadrature
order `n_β`. Reports include wall time, peak memory, effective sample size per
device-hour, and convergence under increasing `χ` and quadrature order. A
polynomial fixed-`χ` cost is not interpreted as proof that the rank needed for
fixed physical accuracy grows polynomially.

More expressive fixed-degree holomorphic carriers may be added only if every
primitive has a machine-checkable type

```text
(particle multidegree, SU(2) irrep, permutation parity, gauge charge).
```

Allowed arithmetic consists of direct sums, tensor products, CG contractions,
determinants/Pfaffians, and linear combinations whose output type is known
exactly. Generic activations, unconstrained attention, post-hoc degree
projection, and `Laughlin × polynomial correction` are forbidden. At fixed
`2Q=3(N-1)`, multiplying `Laughlin = ∏[ij]^3` by a nonconstant holomorphic
nonnegative-degree correction would exceed the available per-particle degree.

Exterior-power fusion remains a research extension, not the production
architecture. A naive Clebsch–Gordan tree for distinguishable copies spans
`V_Q^{⊗N}`, not `∧^N V_Q`. Bounded multiplicity dimension does not by itself
solve this: exact antisymmetry requires CAR-compatible exterior creation maps,
whose complete CFP spaces can grow exponentially.

A fusion implementation may be promoted only after demonstrating all of:

- polynomial-time determinant-amplitude contraction at fixed fusion rank;
- no complete exponential CFP, Gram, or fusion-path table;
- closure of retained spaces under the required fermionic maps;
- exact CAR/Pauli identities and zero forbidden paths;
- gauge-covariant multiplicity truncation;
- correct fermionic `6j/F` recoupling;
- agreement with the complete small-`N` exterior-power oracle.

Until those gates pass, fusion results are feasibility experiments and are not
used for the challenge's primary energy or gap claim.

## 12. Acceptance gates

### 12.1 Hilbert-space gate

- CAR and Pauli identities pass exactly.
- `dim M_L = dim H_{M=L} - dim H_{M=L+1}`.
- `Σ_L (2L+1) dim M_L = binomial(2Q+1,N)`.
- Intertwiner orthonormality defect is at most `1e-12`.

### 12.2 Gauge and rotation gate

- Generator residual
  `||J_i T_L - T_L(J_i^(L)⊗I)|| / ||T_L|| ≤ 1e-11`.
- Random finite-rotation residual is at most `1e-10`.
- North/south chart amplitudes differ only by the analytically expected
  product gauge phase, with relative residual at most `1e-10`.
- The `SU(2)` central element has the expected action.

### 12.3 Hamiltonian gate

- Relative Hermiticity defect is at most `1e-13`.
- Independent Coulomb builders agree on tested matrix elements and low spectra
  to `1e-11 E_C`.
- Relative commutator residuals with `L_z` and `L²` are at most `1e-10`.
- Eigenpair residuals are at most `1e-10`.

### 12.4 NQS gate

- At least four of five seeds pass all per-state criteria.
- The final `L=0` and `L=2` results come from one jointly trained
  sector-conditioned network and one parameter set.
- No trainable array dimension is proportional to the determinant count or
  `dim M_L`; carrier rank `χ` is explicit and independently converged.
- Every carrier is antisymmetric, holomorphic, and has per-particle degree
  exactly `2Q`.
- The unprojected state has `M_z=0` to `1e-12`.
- The Gauss–Legendre rule satisfies
  `2 n_β - 1 ≥ L_max + L`, and the periodic rule satisfies
  `n_α ≥ 2L_max+1`; increasing both orders changes normalized amplitudes,
  energies, and symmetry residuals by at most `1e-11` in the exact-sum tests.
- Rank convergence requires two consecutive doublings satisfying
  `|δE_L| + 2σ_diff ≤ 1e-4 E_C` for both sectors and
  `|δΔ₂| + 2σ_diff ≤ 0.2% Δ₂`. `σ_diff` is estimated from paired seeds and
  paired post-training chains, retaining their covariance; it is zero for
  exact-sum comparisons. Large uncertainty therefore blocks rather than
  relaxes convergence.
- For `N≤8`, each carrier is expanded in `M_L`; the singular values and
  numerical projected-span rank at relative threshold `1e-10` are reported.
  Exact overlaps must change by at most `1e-3` across the last rank doubling.
  Completeness is claimed only if this rank equals `dim M_L`; otherwise energy
  and overlap convergence, not dimension counting, support acceptance.
- Exact-sum energy error is below
  `min(1e-4 E_C, 0.01 Δ₂)`.
- The gap agrees with ED within 1% and, once stochastic evaluation is used,
  within two combined standard errors.
- Exact overlap exceeds 0.99 when computable.
- No state passes only because the state-averaged loss is acceptable.

### 12.5 Response gate

- Both chiral operator families satisfy rank-two tensor commutators to
  `1e-10` and the declared adjoint relation to `1e-12`.
- At least 99% of the ED spectral sum-rule weight is recovered.
- A chirality claim requires a resolved unnormalized channel contrast and the
  expected interchange under reversal of monopole orientation.

## 13. Stop conditions

Stop before NQS training if the Hilbert-space, gauge, Hamiltonian, or rotational
gate fails.

Stop calling the target state a graviton if no dominant rank-two response pole
is demonstrated.

Stop making a chirality claim if only `Δ₂`, `⟨L²⟩`, or multiplet degeneracy is
available.

Stop any finite-size extrapolation if it is unstable under removal of one size
or under reasonable fit-form changes.

Stop the scalable fusion phase if its small-`N` Gram rank, amplitudes, or
recoupling relations disagree with the exact exterior-power construction.

Stop increasing system size if the required Pfaffian rank shows unresolved
growth, the amplitude cost exceeds the recorded resource envelope, or
independent rank extrapolations disagree beyond the target gap uncertainty.

## 14. Reproducibility and outputs

Tracked source code and documentation live under:

```text
tracks/qmc/solutions/frustration-free/challenge-15/
```

Generated numerical artifacts live under:

```text
tracks/qmc/results/frustration-free/challenge-15/<run-id>/
```

Every run records:

- all physical and numerical configuration;
- random seeds;
- Python/JAX and dependency versions;
- Git revision;
- source-input SHA256 values;
- raw and background-corrected energies;
- eigenpair, symmetry, gauge, and sum-rule residuals;
- convergence and statistical diagnostics.

Large PDFs, source archives, checkpoints, raw samples, and scheduler logs are
not committed. Their source URLs and SHA256 values are recorded in
`references/SOURCES.md`.

## 15. Explicit non-goals of the minimum deliverable

- No Landau-level mixing.
- No ordinary scalar-coordinate SO(3) network.
- No unconstrained `Laughlin × NN` correction.
- No parity or time-reversal constraint at fixed `Q`.
- No claim that DeepHall directly solves the challenge.
- No chirality inference from `M=±2`.
- No thermodynamic or beyond-ED scaling claim from the complete multiplicity
  basis.
