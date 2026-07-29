# Challenge #121 completion audit

Audit target: [Quantum Harness issue #121, “Sign-problem free
hunter”](https://github.com/QuantumBFS/quantum.harness/issues/121).

## Executive verdict

**Research core: complete.  Public submission: in progress.**

The final four-letter oddcycle candidate now has:

- a human-readable arbitrary-depth determinant theorem;
- a solver-independent exact rational certificate;
- an exact dual separation from every common real symmetric
  split-contraction metric of the tested form;
- a positive-field Hermitian interacting five-mode realization;
- a frozen empirical protocol and one-command exact replay;
- a paper draft centered on the final, rather than the overturned,
  candidate.

The remaining blockers are publication and novelty-boundary work, not more
finite-depth scanning.  The broadest safe claim is:

> a coherently time-oriented finite-state Lorentz path-metric criterion
> strictly extends the common-metric criterion for this exact alphabet.

We do not yet claim inequivalence to every complex Majorana,
fermion-bag, loop, or hidden-basis formulation.

## Final candidate

\[
B(p)=
\begin{pmatrix}
0&0&2&0&0\\
2&0&0&0&0\\
0&2&0&p&0\\
0&0&0&1&1\\
0&0&-1&0&1
\end{pmatrix},
\]

\[
\mathcal A=
\{B(1/1000),B(1/1000)^{\mathsf T},
  B(4/5),B(4/5)^{\mathsf T}\}.
\]

For every nonempty word \(W\in\mathcal A^*\),

\[
\det(I_5+W)>0.
\]

The previous continuum alphabet around \(p=1\) is not the final result: an
exact common metric places it inside the known Wei-type contraction class.

## Requirement-by-requirement status

| Issue #121 requirement | Status | Final evidence |
|---|---|---|
| Correct determinant oracle and product order | **complete** | `oracle/weights.py`, baseline exact fixtures, and oracle tests |
| Positive and negative controls for split orthogonal / semigroup theorems | **complete** | baseline, classical-group, AZ, and semigroup protocols |
| State-of-the-art map and reduction checklist | **complete at project level** | `FOUNDATIONS.md`, `LITERATURE_GAP_2026.md`, `CANDIDATE_CARD.md` |
| Precisely defined structured generator set | **complete** | final alphabet above and `ODDCYCLE_PATH_METRIC_CERTIFICATE.md` |
| Large tests over dimensions/depths with protocol | **complete for this candidate** | frozen `protocols/oddcycle-path-metric-v1`; 1,398,100 exhaustive words through depth 10 plus 100,000 seeded histories through depth 40; historical production exhausted 22,369,620 words through depth 12 |
| Exact replay of any delicate numerical claim | **complete** | rational path metrics, exact Gordan--Stiemke dual, exact physical transfer; the theorem does not rely on floating survival |
| Human-readable proof for arbitrary depth | **complete** | finite-state Lorentz--Stein theorem in `ODDCYCLE_PATH_METRIC_CERTIFICATE.md` and `ODDCYCLE_PAPER_DRAFT.md` |
| Novelty beyond a common split/contraction metric | **complete, narrowly stated** | exact dual certificate proves no common real symmetric metric satisfies all four forward/transpose gaps |
| Broad equivalence audit against all known sign-free mechanisms | **partial** | common metric, basic Kramers, fixed split group, block and simple gauge routes are addressed; full complex Majorana/MTR and fermion-bag/loop equivalence remain |
| Physical determinantal-QMC weight | **complete at cluster level** | exterior Fock trace is `det(I+W)` for the same alphabet |
| Positive auxiliary-field prefactors | **complete** | exact coefficients `(37,1,1,1,1)/41` |
| Hermitian interacting model | **complete at cluster level** | `T/41=exp(-H)`; exact SPD gate; Gaussian identity fails in 58 entries |
| Connected local lattice / small-\(\Delta\tau\) family | **not claimed** | current result is a five-mode transfer-matrix cluster, generally nonlocal and up to five-body |
| Grand-canonical versus fixed filling | **complete limitation** | theorem is for the full Fock trace; fixed-particle positivity is not claimed |
| One-command machine-readable replay | **complete** | `python -m oracle.oddcycle_final_certificate` reports commit, versions, certificate hash, gates, dimensions, counts, and physical constants |
| Public endgame | **partial** | final-candidate paper draft exists; references, collaborator review, and MO/arXiv submission remain |

## Mathematical evidence chain

1. Four rational metrics \(R_i\) have inertia \((1,4)\).
2. All 16 matrices
   \(R_i-A_j^{\mathsf T}R_jA_j\) are exactly positive definite.
3. Four rational time vectors and 16 exact orientation scalars make every
   inverse transition future preserving.
4. The inequalities telescope around every word, producing a strict Stein
   inequality.
5. Stein inertia gives one simple unit-disk eigenvalue; cone
   Perron--Frobenius makes it positive.
6. Every letter has determinant eight, so every determinant
   \(\det(I+W)\) is strictly positive.
7. A positive dual of total trace one excludes any common strict metric.
8. The exact Fock transfer closes the physical and positive-field gates.

## What is new, and what is not

Multiple Lyapunov functions on labelled graphs and path-complete
certificates are known in switched-system control.  The paper must not
claim that generic architecture as new.  The proposed contribution is the
indefinite-inertia version with:

- coherent Lorentz time orientation;
- an arbitrary-word fermion-determinant sign corollary;
- an exact QMC alphabet where multiple metrics work but one common metric
  provably cannot;
- a positive-field interacting realization.

The 2024 contraction-semigroup framework is formulated in a fixed
Majorana metric and permits complex orthogonal basis changes.  The present
five-dimensional common-metric dual is strong evidence of separation but
is not, by itself, a complete no-go for every 10-Majorana formulation.
Until that focused audit is finished, use the narrow novelty statement
above.

## Physical scope

The model is a valid interacting, number-conserving, grand-canonical
five-mode cluster transfer.  Issue #121 requires an interacting model and
awards special credit for stronger lattice settings; it does not make a
connected local lattice a formal prerequisite.  Nevertheless, a local
tiling or fixed-Hamiltonian interval \(0<\Delta\tau<\Delta\tau_0\) would
substantially strengthen a journal submission.

Do not claim:

- canonical fixed-filling positivity;
- a connected lattice;
- two-body locality;
- sign freedom under arbitrary additional hopping or chemical potential;
- classification of all sign-free mechanisms.

## Remaining minimum closure plan

1. Complete a focused literature/equivalence audit for the final
   four-letter candidate, especially the 10-Majorana lift and indefinite
   path-complete control literature.
2. Obtain collaborator review of the theorem, exact certificate, physical
   interpretation, and novelty wording.
3. Run the final one-command replay and relevant full solution test suite
   at the exact submission commit; archive the JSON output and hashes.
4. Finish references and convert the Markdown paper into an arXiv/MO-ready
   manuscript.
5. Push the final commits, update the shared PR, and only then prepare the
   organizer-facing submission.

Further Hodge enumeration and repetition of failed positive-automaton
cones are explicitly not on the critical path.
