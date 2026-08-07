# Challenge #121 submission report

**Team:** No Negative Vibes (Zibo Jin and Xianzhi Pan)

**Challenge:** [Sign-problem free hunter, issue #121](https://github.com/QuantumBFS/quantum.harness/issues/121)

**Submission PR:** [QuantumBFS/quantum.harness#178](https://github.com/QuantumBFS/quantum.harness/pull/178)
**Track:** `qmc`

## Executive summary

This submission is the complete research record, not only the strongest positive
result. It contains proved positive constructions, exact counterexamples and
no-go results, large numerical screens, physical Hamiltonian/auxiliary-field
mappings, known-class reductions, and explicitly labelled unfinished work.

The strongest theorem-level contribution is an explicit five-dimensional,
four-letter alphabet

```text
{B(1/1000), B(1/1000)^T, B(4/5), B(4/5)^T}
```

with an exact rational four-state Lorentz path-metric certificate proving
`det(I+W)>0` for every finite word. Exact Gordan--Stiemke and
Majorana/Wei certificates exclude a common real quadratic metric and the
fixed-`J1,J2` Majorana contraction explanation. The same alphabet gives a
positive-field Hermitian, number-conserving, interacting five-mode transfer.
This is the main publication candidate, with locality and thermodynamic scaling
left open.

Other rigorous positive mechanisms were also found or reconstructed: the
totally nonnegative path/TN semigroup, odd positive-monomial and fixed-partition
block-TN factorization, a graded-monomial compensation mechanism,
tensor-square positivity, and local orthogonal-contraction models. Their
novelty audits are part of the result: several reduce to known
split/Kramers/Wei, stoquastic, Majorana-square, triangular, or integrable
mechanisms. We do not call those reductions new sign-free physics.

The strongest local-model survivor is now the orthogonal-contraction
plaquette Hamiltonian. Its positivity is the known doubled-Majorana square,
but the interacting sum is local, extensive, nonstoquastic, nonquadratic,
outside the audited claw-free generalized-JW class, and generates full
fixed-number sector algebras modulo exact Hodge chirality. Its 4/6/8-mode
chiral ground states violate Wick factorization. We therefore retain it as an
active QNC model candidate, not as a new positivity theorem or a proved
classical-hardness result.

## Evidence grades

| Grade | Meaning |
|---|---|
| Exact theorem/certificate | Solver-independent rational or symbolic replay, or a written general proof |
| Exact negative/no-go | An exact negative weight, exact infeasibility certificate, or general obstruction |
| Numerical screen | Reproducible protocol and seeds; useful for discovery/triage but not a proof |
| Open/in flight | Preserved hypothesis, finite-depth survivor, or running search; not a submitted theorem |

## Complete result ledger

### A. Rigorous positive constructions and their final novelty status

| Construction | Positive result | Physical result | Final status / boundary | Evidence |
|---|---|---|---|---|
| Four-letter oddcycle alphabet | Exact arbitrary-depth `det(I+W)>0` from four rational Lorentz path metrics, 16 transition gaps, and coherent time orientation | Positive-field Hermitian, number-conserving, interacting five-mode transfer | Main publication candidate; no common real quadratic metric and outside the fixed-`J1,J2` Wei class; finite cluster is generally nonlocal | [paper draft](docs/ODDCYCLE_PAPER_DRAFT.md), [path certificate](docs/ODDCYCLE_PATH_METRIC_CERTIFICATE.md), [metric separation](docs/ODDCYCLE_NO_COMMON_METRIC_CERTIFICATE.md), [physical transfer](docs/ODDCYCLE_PAIR_PHYSICAL.md), [Wei audit](docs/ODDCYCLE_MAJORANA_WEI_AUDIT.md) |
| Robust oddcycle frontier point | Independent exact rational path certificate and exact dual replay after 4,302 successful solver calls | Same transfer recipe available | Replication/robustness evidence, not a separate mechanism | [paper draft §3.3](docs/ODDCYCLE_PAPER_DRAFT.md), [protocol](protocols/oddcycle-robust-candidate-v1/README.md) |
| Symmetric-oddcycle interval family | Exact arbitrary-depth theorem for a continuous alphabet | Five-mode interacting transfer | Exact common signature `(1,4)` metric was later found; retained as a positive control in the known Wei semigroup | [interval family](docs/SYMMETRIC_ODDCYCLE_INTERVAL_FAMILY.md), [novelty filter](docs/ODDCYCLE_NOVELTY_FILTER.md) |
| Totally nonnegative path/TN semigroup | Arbitrary dimension/depth: exponentials and products are entrywise nonnegative, hence `det(I+D)>=1` | Open Hubbard and repulsive `t-V` chains; exact asymmetric positive-field bond decomposition | Rigorous and algorithmically useful; physical examples are known one-dimensional/Jordan--Wigner classes | [theorem](docs/TOTAL_NONNEGATIVE_PATH_CLASS.md), [physical frontier](docs/TN_PHYSICAL_MAPPING_FRONTIER.md) |
| Odd positive-monomial / block-TN | Odd permutation cycles factor the determinant into positive factors; fixed global block partition also works | Model factory exists for a fixed global partition | Matrix result rigorous; elementary cycle factorization is known and natural local crossed partitions fail | [result](docs/SPECULATIVE_STRUCTURE_RESULTS.md), [locality audit](docs/ODD_BLOCK_TN_LOCALITY_AUDIT.md) |
| Graded monomial | History grade cancels determinant parity exactly | Local odd-ring attractive spinless model | Rigorous but reducible to Majorana reflection positivity / fixed orbit gauges | [candidate](docs/GRADED_MONOMIAL_CANDIDATE.md), [audit](docs/GRADED_MONOMIAL_RESULTS.md) |
| Tensor-square | For real `X`, `det(I+X tensor X)>=0`; the weight factorizes into modulus-square and real-square pieces | Four-mode plaquette, multi-channel models, and exact `-log` transfer | `m=2` is split; `m=3` has an exact no-fixed-metric result. Positivity is rigorous, while independent physical novelty and phase structure remain open | [result](docs/TENSOR_SQUARE_RESULTS.md), [effective model](docs/TENSOR_SQUARE_EFFECTIVE_MWE.md), [three-candidate audit](docs/THREE_CANDIDATE_AUDIT_RESULTS.md) |
| Local orthogonal contraction | Products of real orthogonal local vertices give nonnegative determinant weights at arbitrary history depth | Local, extensive, four-body overlapping-plaquette Hamiltonian; non-Gaussian chiral low-energy states | Known doubled-Majorana positivity, but no diagonal stoquastic gauge, quadratic/common-orbital reduction, claw-free JW solver, or small sector algebra; active QNC candidate with complexity and thermodynamic scaling open | [audit](docs/ORTHOGONAL_CONTRACTION_HAMILTONIAN.md), [code](oracle/orthogonal_contraction_physics.py) |
| Tensor-square phase program | Determinant factorization, Hermiticity, number conservation, ED, and stabilized DQMC gates passed | `m=3,4` pilots and an `m=4,6,8` finite-temperature map | 675/675 coarse cells completed; a robust response ridge was found, while Stage-4 sampler proposals were stopped by preregistered efficiency gates. This is a finite-size signal, not a new phase claim | [status](tensor-square-phase-diagram/STATUS.md), [model](tensor-square-phase-diagram/MODEL.md) |
| Fixed weighted `l_infinity` contraction | Common norm contraction implies positivity | No successful Hamiltonianization | Rigorous common-contraction control, not a new mechanism | [screen](docs/SPECULATIVE_STRUCTURE_RESULTS.md), [reappraisal](docs/POSITIVE_HAMILTONIAN_REAPPRAISAL_LEDGER.md) |
| Reciprocal-parabolic and commuting controls | Triangular reciprocal factorization and common commuting algebra give positive weights | No new model | Known triangular/integrable controls | [screen](docs/SPECULATIVE_STRUCTURE_RESULTS.md) |

### B. Exact counterexamples, reductions, and no-go results

| Route closed or delimited | Certificate / conclusion | Evidence |
|---|---|---|
| Classical groups | Exact negative/complex certificates close universal positivity for `SL(2/3,R)`, `Sp(2/4,R)`, `SU(1,1)`, `SU(2,1)`, `SU(3)`, `U(2)`, and `U(1,1)`; zero-failure `O(p,q)`, `SU(2)`, `USp` cases reduce to known mechanisms | [baseline](docs/BASELINE_RESULTS.md), [exact fixtures](fixtures/exact_certificates.json) |
| Hermitian AZ tenfold screen | A/D/C have complex weights; AI/AIII/CI have exact depth-three negative weights; BDI is split and AII/DIII/CII are Kramers | [AZ table](docs/AZ_TENFOLD_RESULTS.md) |
| Rotated Majorana cones | Exact two-layer weight `-4 sin(theta) sinh(q)^2`; every nonzero angle fails, even though a shared reality structure keeps the weight real | [Majorana screen](docs/MAJORANA_CONE_RESULTS.md), [analytic counterexample](docs/SMALL_ANGLE_COUNTEREXAMPLE.md) |
| Rotated split-cone union | Exact `16[1-q^2 sin^2(theta)]`; every nontrivial principal angle fails for sufficiently large `q` | [frontier screen](docs/FRONTIER_SEMIGROUP_RESULTS.md) |
| BDI two-sided relaxation | Exact `16(1-q^2)` negative branch | [AZ survivor cones](docs/AZ_SURVIVOR_CONE_RESULTS.md) |
| Path graph generalizations | Cycle, star, dense Metzler graphs and slice-dependent sign gauges have stable negative weights | [frontier screen](docs/FRONTIER_SEMIGROUP_RESULTS.md) |
| Ordinary TN locality | Continuous generators, positive Gaussian sums, and particle-sector gauges leave only labelled open paths; rings/branches contain exchange-sign obstructions | [physical frontier](docs/TN_PHYSICAL_MAPPING_FRONTIER.md), [compound-gauge no-go](docs/COMPOUND_GAUGE_NO_GO.md) |
| Crossed odd block-TN partitions | Exact shortest counterexample `det(I+XR)=-2` | [locality audit](docs/ODD_BLOCK_TN_LOCALITY_AUDIT.md) |
| Even monomial route | Exact `q=2` counterexample `-9/4` | [speculative screen](docs/SPECULATIVE_STRUCTURE_RESULTS.md) |
| Moving metrics, reciprocal feedback, near commuting | 80-digit negative replays close the naive relaxations | [speculative screen](docs/SPECULATIVE_STRUCTURE_RESULTS.md) |
| Odd block-TN revival | A common count-sector `+/-1` gauge maps the fixed-partition family to a stoquastic/worldline class | [stoquastic no-go](docs/ODD_BLOCK_TN_STOQUASTIC_NO_GO.md) |
| Fock--CP finite Klein library | 520 cells; all bridge directions vanish already in the Hermiticity-preserving span | [screen](docs/FOCK_CP_SCREEN_RESULTS.md) |
| R01 overlapping Klein/Hodge | Exact double-dual/Farkas certificates force all tested cross-cluster hopping/pairing anchors to zero for the frozen transform | [candidate audit](docs/candidates/R01_OVERLAPPING_KLEIN_FOCK.md), [fixtures](fixtures/overlap_klein_r01.json) |
| Exterior seed61 | A length-150 exact negative determinant closes a candidate that survived shallower cone/word tests | [counterexample](docs/SEED61_EXACT_COUNTEREXAMPLE.md) |
| Gauge/cocycle ladder | Exact local cancellation works at four/six modes, but the compensating Wilson support and locality radius grow with ladder length | [gauge audit](docs/GAUGE_COCYCLE_RESULTS.md) |
| Adjoint lift | Exact fixed-metric calculation places the whole family in an identity component of known `O(p,q)` / split orthogonal structure | [three-candidate audit](docs/THREE_CANDIDATE_AUDIT_RESULTS.md) |
| Grade-charge ancilla | Exact conserved-sector decomposition shows a static direct sum, not new ancilla dynamics | [three-candidate audit](docs/THREE_CANDIDATE_AUDIT_RESULTS.md) |
| Symmetric-oddcycle continuum | Exact common `(1,4)` metric reduces it to the known Wei contraction semigroup; it is not the new-mechanism claim | [novelty filter](docs/ODDCYCLE_NOVELTY_FILTER.md) |

### C. Numerical and finite-depth campaigns

| Campaign | Work completed | Proper interpretation |
|---|---:|---|
| Classical-group baseline | 900,000 products, 900/900 cells | Discovery screen backed by exact representatives |
| Hermitian AZ tenfold | 720,000 products, 720/720 cells | Standard `4 x 4` representation only |
| Majorana rotated cones | 448,000 broad + 252,000 small-angle weights | Now superseded by an analytic counterexample |
| Frontier semigroups | 720,000 broad + 672,000 split stress weights | Negative cases replayed at 80 digits; survivors separately proved/reduced |
| AZ survivor cones | 140,000 weights | First-round number-conserving cones, not a full BdG/Pfaffian classification |
| Speculative structures | 192,000 weights | Candidate discovery and falsification; proof/audit determines final status |
| Main determinant-screen subtotal | **4,044,000 weights** | Does not include exact-card word enumeration below |
| Exterior exact cards | 2,304 exact cards; staged depth 4/8/12/16 pressure and high precision | Many shallow survivors removed; exact gates prevent float-only claims |
| Oddcycle seeds `117/132/147` | Each seed exhaustively positive for all nonempty binary words through depth 27 (`268,435,454` raw words each), plus 448 long-word winners at lengths 60--1800 | Strong finite-depth evidence only, not an arbitrary-depth theorem |
| Untyped distant oddcycle pair | 22,369,620 words through depth 12 plus 100,000 random words through depth 40 | Joint common base metric was numerically absent; arbitrary-depth theorem remains open |
| Fock--CP screen | 13 depth-two circuits × 20 cuts × 2 families = 520 cells | Numerical rank/no-bridge screen; the finite library is not a general non-Klein no-go |
| Local-H first batch | Route A 20/20 and Route B 16/16 numerically infeasible; Route D 4/4 exact positive transfers | No exact local Hamiltonian through word length four; not a no-go theorem |
| Tensor-square validation | 54 noncommuting histories; `m=3,4` ED; DQMC/ED cross-checks | Direct/factorized weights, Hermiticity, number conservation, eigensolvers, and low-temperature stabilization passed |
| Tensor-square coarse map | `m=4,6,8` × `beta=2,4,8` × 5 coupling ratios × 5 hopping ratios × 3 chemical potentials = 675/675 cells | 14 SURVIVE, 27 EXTEND, 34 STOP regions; half-filled response ridge is a short-system candidate, not a phase statement |
| Tensor-square Stage 4 | 90-cell pilot contract, production ranking, `m=10` sentinel, autocorrelation diagnosis, temporal-block and channel-reflection A/B tests | Sign/stability gates passed; temporal-block and channel-reflection proposals stopped on frozen efficiency/ESS gates. Stage 5 was not released; these are algorithm stops, not physics no-go results |
| Orthogonal-contraction physics | 4/6/8-mode half-filled ED; six-mode `so(6)`/sector-commutant audit; Hodge-resolved Wick tests | Full irreducible sector algebras modulo chirality and non-Gaussian ground states; finite-size physics, not a thermodynamic phase claim |

### D. Physical constructions and final attribution

The repository contains explicit Hamiltonian, auxiliary-field, or transfer
constructions for:

1. open Hubbard and repulsive `t-V` chains;
2. an exact asymmetric positive-field `t-V` bond decomposition;
3. a three-site parity-string hopping vertex;
4. a graded-monomial odd-ring model;
5. tensor-square plaquette, multi-channel, and effective `-log` models;
6. fixed-partition odd block-TN model factories;
7. Wilson-string constrained fermion--gauge constructions;
8. a local orthogonal-contraction overlapping-plaquette family;
9. the five-mode interacting oddcycle transfer.

Their mathematical correctness and physical novelty are different questions.
The tables above retain constructions that later reduced to known mechanisms,
because those reductions and reusable oracles are useful research results.

### E. Explicitly unfinished work

- **Survivor A:** an exactly positive rational transfer (seed `20260730`,
  cell `portfolio-l2`, sample `122`, shift `42`, vacuum value `44`, row margin
  `12213/15625`) with numerical interacting/non-Gaussian diagnostics. It is
  not an exact local Hamiltonian.
- **Current local-H portfolios:** preserved remote WSL/CPU runs and settings
  are nonterminal. No result from an unfinished cell is used in a theorem.
- **Oddcycle seeds `117/132/147`:** very deep finite evidence, no
  arbitrary-depth proof.
- **Tensor-square `m>=3`:** exact positivity and useful numerics exist;
  ED and stabilized DQMC agree at their validation points, and the 675-cell
  coarse map found a half-filled response ridge. Thermodynamic scaling and a
  new-phase claim remain open; two Stage-4 sampler proposals were correctly
  stopped rather than overinterpreted.
- **Local orthogonal contraction:** positivity is a known Majorana-square
  mechanism, while the local interacting Hamiltonian survives the audited
  conventional solvers. General complexity and thermodynamic scaling remain open.
- **Complex Majorana/Pfaffian formulation:** the full simple matrix theorem
  requested by the challenge remains open.
- **Majorana parity pattern and non-Klein typed exterior cones:** hypotheses or
  partial programs, not completion claims.

## Why the submission is useful

1. It gives a compact exact arbitrary-depth certificate that can be checked
   without trusting an SDP solver.
2. It separates path-dependent Lorentz certificates from common quadratic
   metrics and from one fixed Majorana contraction class.
3. It provides reusable determinant, Spin/Fock-trace, exact-arithmetic,
   high-precision, candidate-card, and resumable distributed-search tooling.
4. It maps a large natural candidate space into proved positive, exactly
   falsified, known-reduction, and genuinely open regions, preventing repeated
   searches.
5. It preserves failed routes and minimal counterexamples, which are directly
   useful when designing future sign-free QMC conditions.
6. It adds sector-algebra, Hodge-chirality, JW-frustration, stoquastic-cycle,
   and Wick-residual audits that distinguish a known positivity identity from
   an actually conventionally solved interacting Hamiltonian.

## Correctness and claim boundaries

- Every universal positive claim cited as exact has a proof or
  solver-independent exact replay.
- Every universal class rejected as exact has an exact counterexample or
  written general obstruction; floating-point-only failures are labelled as
  numerical.
- Random survival is never promoted to a theorem.
- Full Fock/grand-canonical positivity is not silently claimed for each fixed
  particle-number or parity sector.
- A finite five-mode transfer is not presented as a scalable local lattice
  Hamiltonian.
- Reduction outside a *particular* sufficient class is not called a complete
  novelty classification.

## Submission verification

Fresh local verification used the recorded `quantum_harness` Conda
environment (Python 3.11.15):

| Gate | Result |
|---|---|
| `python -m oracle.oddcycle_final_certificate` | `all-exact-gates-passed`; exact payload SHA-256 `176712dc90cd3483e31549aa177ecf418a0162515fe0ccdb89136a68c65aece1` |
| Main theorem, negative controls, teammate mechanisms, and Survivor A focused suite | `112 passed, 1 skipped, 2 xfailed` |
| Tensor-square phase-diagram suite | `73 passed` |
| Orthogonal-contraction focused suite | `17 passed in 1.56s` |
| Challenge report renderer | Standard `skills/report/render_report.py` completed; self-contained HTML written under the ignored result root |

The single Windows skip is a POSIX-shell fake-`git` timing test already
covered by the WSL regression. The two strict expected failures specify the
not-yet-implemented high-precision `analyze_hamiltonian` task and are not
submission evidence.

## Reproduction

Start with [REPRODUCE.md](REPRODUCE.md). The fastest publication replay is:

```bash
cd tracks/qmc/solutions/no-negative-vibes
PYTHONPATH=. python -m oracle.oddcycle_final_certificate
PYTHONPATH=. pytest -q \
  tests/test_oddcycle_path_metric.py \
  tests/test_oddcycle_metric_dual.py \
  tests/test_oddcycle_pair_physical.py \
  tests/test_oddcycle_majorana_wei_audit.py \
  tests/test_oddcycle_final_certificate.py
```

Large generated cells and the offline HTML challenge report live under
`tracks/qmc/results/no-negative-vibes/` and are intentionally excluded from
Git. Protocol settings, exact fixtures, compact results, seeds, source hashes,
and replay code are tracked under this solution directory.

## Branch integration provenance

| Source | Integrated content |
|---|---|
| `ZiboJin/quantum.harness:challenge/qmc-sign-free-hunter` | Original registration and PR #178 head |
| `no-negative-vibes/quantum.harness:research/no-negative-vibes` | Reviewed team baseline and teammate PR merges |
| `xianzhipan/quantum.harness:codex/positive-hamiltonian-reappraisal` | 28 commits covering Fock--CP, tensor-square, gauge/cocycle, odd-block-TN, orthogonal contraction, unconventional-model audits, ledgers, code, fixtures, protocols, and tests |
| `no-negative-vibes/quantum.harness:work/zibo/representation-cones` | Exact-card exterior campaign, oddcycle theorem/novelty/physical transfer, local-H portfolio, Survivor A, distributed checkpoints, and publication package |
| `ZiboJin/quantum.harness:work/zibojin/tensor-square-phase-diagram` | 23 commits covering ED, stabilized DQMC, 675-cell dual-machine map, Stage-4 statistics, sampler early stops, source, tests, and result summaries |

Equivalent early teammate commits already merged into the shared research
branch were not duplicated. The two previously unmerged scientific branches
were merged with their history intact before this report was finalized.

## Detailed ledgers

- [Exhaustive project master summary (Chinese)](docs/PROJECT_MASTER_SUMMARY.zh-CN.md)
- [Compact results ledger](docs/RESULTS_LEDGER.md)
- [Organizer-direction audit](docs/ORGANIZER_DIRECTION_AUDIT.md)
- [Challenge completion and novelty audit](docs/ODDCYCLE_CHALLENGE_AUDIT.md)
- [Publication draft](docs/ODDCYCLE_PAPER_DRAFT.md)
- [Local-H result and claim boundary](docs/ODDCYCLE_LOCAL_HAMILTONIAN_PORTFOLIO.md)
- [Tensor-square phase status and stop decisions](tensor-square-phase-diagram/STATUS.md)
