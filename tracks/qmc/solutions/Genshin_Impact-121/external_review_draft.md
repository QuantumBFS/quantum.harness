# External expert review draft: a contractive matrix family for issue #121

Status: expert-review draft backed by the completed formal verifier. It has not been posted to MathOverflow or arXiv.

This text evaluates the mathematical and physical claims on their present scope.
It is not an endorsement of novelty or a substitute for independent reproduction.

## Executive assessment

The submission proposes an explicit open family of real one-body generators.
Every finite word generated from that family has a nonnegative determinant weight.
The relevant weight is det(I+T), with T a product of one-particle propagators.

The main positivity mechanism is a common ell_infinity contraction, not total nonnegativity.
This distinction is conceptually useful for quantum Monte Carlo sign-problem searches.
The construction also includes algebraic tests intended to separate it from familiar sufficient criteria.

Those separation tests are meaningful only within the precisely stated representation class.
They do not prove that the family has never appeared in an equivalent formulation.

The proposed many-body realization uses overlapping S3-twirled Gaussian vertices.
It is interacting and non-Gaussian at the operator level for sufficiently small positive tau.
Its continuous-time operator-string expansion nevertheless has nonnegative configuration weights.

The full preregistered verifier and compact hash record are now posted in PR #261.
The current appropriate recommendation is independent specialist review, not unconditional acceptance.

## Background and relation to issue #121

Issue #121 asks for useful sets of matrices whose finite products obey

    det(I+T) >= 0.

Here T has the ordered-product form

    T = exp(A_m) ... exp(A_2) exp(A_1).

In auxiliary-field or continuous-time fermion methods, this determinant is a Fock-space trace.
For number-conserving bilinears, the identity is

    Tr_Fock[Gamma(T)] = det(I+T).

Thus a matrix-semigroup condition can become a configuration-wise sign-free condition.
The challenge is not positivity for one specially chosen matrix.
The challenge is positivity for arbitrary word length, ordering, times, embeddings, and allowed parameters.
The proposed answer addresses that stronger closure requirement.

## The A/B family

The wider seven-parameter generator is

    A(theta) = [ -a-b-delta_1     a             -b         ]
               [      0          -c-delta_2      c         ]
               [      d               0         -d-delta_3 ],

where a,b,c,d,delta_1,delta_2,delta_3 are positive.
Let

    S = diag(1,1,-1)

and define

    B(theta) = S A(theta) S.

Permutation conjugates P A P^T and P B P^T are included in the local alphabet.

The concrete rational point used in the draft is a specialization, not an isolated solution.
It sets a=c=1, d=2, b=epsilon, and delta_1=delta_2=delta_3=kappa.
At that point

    A(epsilon,kappa) = [ -1-epsilon-kappa    1           -epsilon ]
                       [       0            -1-kappa       1       ]
                       [       2               0          -2-kappa ].

The displayed numerical example epsilon=1/100 and kappa=1/1000 lies inside an open parameter region.
It should therefore be presented as a convenient exact certificate point.
It should not be described as the only matrix that works.

## Arbitrary-depth positivity from a common ell_infinity contraction

For any real matrix X, define its logarithmic ell_infinity norm by

    mu_infinity(X) = max_i [X_ii + sum_(j != i) |X_ij|].

Each row of A(theta) has logarithmic rate exactly -delta_i.
Conjugation by S changes signs but preserves the absolute row sums.
Permutation conjugation merely reorders the same row estimates.

Consequently every allowed local generator X obeys

    mu_infinity(X) <= -delta_min < 0,

where delta_min=min(delta_1,delta_2,delta_3).
For propagation time t>=0, the logarithmic-norm estimate gives

    ||exp(tX)||_infinity <= exp(-t delta_min) <= 1.

Submultiplicativity then applies to every finite word without a depth restriction.
For a strictly three-dimensional word with positive total time, one obtains ||T||_infinity<1.

For a local three-site block embedded in a larger one-particle space, spectator directions contribute identity blocks.
The embedded factor therefore satisfies the non-strict bound ||T_factor||_infinity<=1.
Products of differently embedded factors retain ||T||_infinity<=1.

Hence every eigenvalue lambda of T satisfies |lambda|<=1.
Real eigenvalues contribute factors 1+lambda>=0 to det(I+T).
Nonreal eigenvalues occur in conjugate pairs and contribute |1+lambda|^2>=0.

It follows that

    det(I+T) >= 0

for arbitrary finite depth and arbitrary ordering of allowed factors.

This proof allows a zero determinant when an embedded word develops an eigenvalue -1.
It does not replace nonnegativity by an unjustified strict-positivity claim.

It also makes clear why the exact entries of the example are not essential.
Positivity persists throughout any parameter region that keeps all row rates negative.

## Separation from several standard sufficient structures

The draft supplies a no-common-H certificate for the A/B orbit.
The tested condition is the existence of one positive-definite quadratic form H shared by every generator.
At the rational point, the A and B inequalities reduce to incompatible exact rational bounds.

The seven-parameter version uses a test vector x=(1,1,t), with 0<t<1.
It defines a linear quantity G_t(theta) and positive coefficients p_t and q_t.
When G_t(theta)>0, the A inequality requires a scalar r<0 while the B inequality requires r>0.

Equivalently, the exact Farkas combination gives

    (p_t+q_t)G_t <= 0,

contradicting p_t>0, q_t>0, and G_t>0.

At the stated point and t=3/4, the draft records

    G_t=1679/16000,
    p_t=10109/16000,
    q_t=15375/16000.

The formal verifier regenerated and verified all three values using exact Fraction arithmetic.

The formal verifier confirmed exact Fraction span rank nine in M_3(R).
That full-span result rules out an explanation confined to a proper linear subspace of 3x3 matrices.
Together, full span and no common H strengthen the claim that the ell_infinity mechanism is structurally distinct.

The draft further gives a fixed, same-dimensional Wei/CAR separation argument.
The intended conclusion is limited: no single allowed same-dimensional one-body basis change places the full alphabet in the compared Wei cone.
The sign convention for the Wei linear matrix inequality must be stated explicitly.
Using eta versus -eta reverses the displayed inequality and can otherwise look like a sign error.

This separation does not cover enlarged ancilla spaces.
It does not cover configuration-dependent changes of basis.
It does not cover nonlinear rewritings or a different Hubbard-Stratonovich decomposition.
It also does not establish global inequivalence to every known sign-free formulation.

## Interacting S3-twirled physical model

For X=A or B, define the local Fock-space twirl

    M_X(tau) = (1/6) sum_(sigma in S3) Gamma(exp(tau P_sigma X P_sigma^T)).

The individual Gaussian vertices need not be Hermitian.
The complete S3 average is Hermitian by its sector decomposition.
Overlapping copies are placed on triangular subsets of a lattice or hypergraph.

With positive couplings g_A and g_B, the shifted Hamiltonian is

    H_bar = sum_Delta [g_A(I-M_A,Delta)+g_B(I-M_B,Delta)]
          = G_0 I - V.

Here V is the positive linear combination of all resolved Gaussian vertices.
The identity shift is physically and statistically important.

Each twirl acts as one on the Fock vacuum, so H_bar annihilates the vacuum.
For the finite four-site benchmark, the verifier checked H_bar>=0 within tolerance: the minimum eigenvalue was 4.440892098500626e-16 and the Frobenius hermiticity residual was 1.7216638914240724e-17.
The operator is not merely a quadratic free-fermion Hamiltonian.

At epsilon=1/100 and kappa=1/1000, exact Taylor coefficients give interaction certificates

    I_A=15062013/3000000,
    I_B=3056033/3000000,

and non-Gaussian certificates

    G_A=363599/360000,
    G_B=797/120000.

All four multiply tau^2 at leading nonzero order.
Their nonzero values imply interaction and failure of Gaussian closure for sufficiently small positive tau.
This is an analytic local statement, not evidence that every tau is admissible.

## Positive continuous-time expansion

Write the resolved vertex activities as lambda_alpha>0 and let G_0=sum_alpha lambda_alpha.
Expanding exp(-beta H_bar) gives the ordered-string series

    Z_bar = exp(-beta G_0) sum_m beta^m/m! sum_(alpha_1...alpha_m) lambda_alpha_1...lambda_alpha_m det(I+U_m...U_1).

Every scalar coefficient is nonnegative.
Every determinant is nonnegative by the common ell_infinity argument.
Thus every resolved configuration has nonnegative weight.

An equivalent audit samples m from Poisson(beta G_0).
Conditional labels are sampled with probability lambda_alpha/G_0.
Under that normalized measure, the unbiased estimator of Z_bar is simply det(I+U_m...U_1).

No extra factor exp(+beta G_0) belongs in the shifted estimator.
The one-particle determinant should also be compared with an independent direct Fock-space trace.
Time ordering should be identical in those two calculations.

## Reproducibility package available for review

- Issue discussion: [quantum.harness issue #121](https://github.com/QuantumBFS/quantum.harness/issues/121)
- Pull request: [PR #261](https://github.com/QuantumBFS/quantum.harness/pull/261)
- Executable commit: [9fe85a6317132983b48c12cbe3628b2da2945a19](https://github.com/QuantumBFS/quantum.harness/commit/9fe85a6317132983b48c12cbe3628b2da2945a19)
- [Verifier source at the executable commit](https://github.com/QuantumBFS/quantum.harness/blob/9fe85a6317132983b48c12cbe3628b2da2945a19/tracks/qmc/solutions/Genshin_Impact-121/issue121_verification.py)
- [Preregistered manifest at the executable commit](https://github.com/QuantumBFS/quantum.harness/blob/9fe85a6317132983b48c12cbe3628b2da2945a19/tracks/qmc/solutions/Genshin_Impact-121/issue121_full_run.json)
- [Compact tracked verification record](verification_record.md)
- Remote row-level artifacts: `tracks/qmc/results/Genshin_Impact-121/20260730-021845-9fe85a6/`

Protocol `ae54430bfb17790c197fabed523138ed6ba3a632881978b5665367e1517a2e20`
passed 224/224 cells: 35,840 candidate words, 4,480 control words, 336 direct
Fock checks, exact Fraction and twirl certificates, and 16,384 physical Poisson
strings. All candidate and physical weights were nonnegative. The 448 inconclusive
numeric classifications were exactly the preregistered mixed-component O(1,1)
zero controls; the unexpected count was zero. Near-singular cases triggered 672
100-digit rebuilds. The four-site ED/Poisson benchmark passed at all four beta
values, and the test suite passed 39 tests.

The compact record contains SHA256 values for the manifest, verifier, independent
support oracle, reports, exact and physical artifacts, samples table, and COMPLETE
sentinel. The 9.6 MB `samples.csv` remains in the durable remote result directory
rather than being copied into the PR. No DOI or independent archival snapshot is
claimed.
## Scope and limitations

This work does not by itself prove literature priority.
A documented search can support novelty assessment but cannot establish universal absence.

The fixed-dimensional separation does not exclude an ancilla-assisted representation.
It does not exclude an alternative Hubbard-Stratonovich channel.
It does not exclude a different Gaussian support for the same many-body operator.

The demonstrated shifted model has a vacuum state with zero energy.
The present benchmark is therefore not a finite-density metallic example.
The construction is not the standard repulsive or attractive Hubbard model.
Calling it "Hubbard" without qualification would obscure its S3-twirled multi-site structure.

The finite four-site calculation is a validation fixture, not a thermodynamic phase study.
Sign-free configuration weights do not alone imply an efficient autocorrelation time.
The physical accessibility of the interactions remains a separate question.

## Questions for the authors

1. Please state the exact maximal open parameter cone currently proved, rather than only sufficient slices of it.

2. Please write the fixed same-dimensional Wei/CAR separation as a standalone theorem with its sign convention and allowed transformations explicit.

3. Please identify which parts of the novelty search were checked against primary literature and which possible equivalences remain unresolved.

4. Please provide an independent reproduction of every Fraction certificate, all four O(n,n) controls, and the full preregistered row counts from the immutable manifest.

5. Please determine whether a non-vacuum or finite-density extension preserves configuration-wise positivity without doubling by a conjugate flavor.

6. Please identify lattice-scale observables or phases that distinguish this model from a formally sign-free but physically trivial projector construction.

## Provisional recommendation

The arbitrary-depth contraction proof is short, transparent, and potentially reusable.
The open seven-parameter family makes the result more meaningful than one numerical matrix.
The no-common-H and full-span certificates are valuable diagnostics when kept within scope.
The interacting twirl supplies a concrete route from matrix algebra to a many-body operator expansion.

Publication value will depend on three remaining standards.

First, the theorem and representation-class boundaries must survive specialist scrutiny.
Second, the completed preregistered verifier should be independently reproduced.
Third, the literature audit must justify a carefully worded novelty claim.

Subject to independent review, I would encourage a full technical submission rather
than dismiss the construction as a numerical curiosity.
