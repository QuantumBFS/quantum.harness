---
title: "Challenge 148: Stage 7 Report - ParaToric Independent-Route Qualification"
date: 2026-07-29
tags:
  - quantum-harness
  - challenge-148
  - stage-report
  - paratoric
  - quantum-monte-carlo
  - exact-diagonalization
status: gate-pending
stage: 7
related:
  - Harnessing Quantum 2026/Challenge 148 - TFIM Critical-Field Ratio.md
  - Harnessing Quantum 2026/Challenge 148 - Protocol Revision 6.md
  - Harnessing Quantum 2026/Challenge 148 - Protocol Revision 7.md
  - Harnessing Quantum 2026/Challenge 148 - Protocol Revision 8.md
  - Harnessing Quantum 2026/Challenge 148 - Stage 5 Report.md
---

# Challenge 148: Stage 7 Report

## 1. Stage status

| Item | Status |
|---|---|
| ParaToric v1.0.3 source pin | Qualified |
| External build compatibility patch | Hashed and limited to compilation fixes |
| ParaToric core build | Pass |
| ParaToric upstream tests | 2/2 pass |
| Dual coupling and lattice mapping | Frozen in Protocol Revision 6 |
| Periodic trace ensemble | Fixed against nondegenerate square $L=3$ ED |
| Small-torus energy-component checks | Four comparisons tagged `Agreement` |
| Charge-sector checks | Pass; zero observed star defects |
| Honeycomb-target finite-size comparison | Revision 6 pass; equilibration repair pending |
| Revision 7 raw-series sampler and cost planner | Implemented and tested |
| Revision 7 independent analysis adapter | Implemented; production validation pending |
| Revision 7 bounded cost pilots | 16/16 chains pass in corrected `v2` runs |
| Remote production route | **Blocked by unprovisioned SSH aliases** |
| Independent thermodynamic-limit critical fields | **Not started** |
| **Overall stage** | **Gate-pending** |

ParaToric is qualified as an independent normalization route. This is not an
independent thermodynamic-limit result and does not authorize the sealed
verdict.

## 2. Previous work

The Stage 0 preregistration selected ParaToric as the preferred independent
continuous-time QMC implementation, subject to normalization, sector, ED, and
finite-size qualification. Stages 1-5 established the direct SSE model and
finite-volume ED oracle, then showed that the direct production precision is
not locally feasible under the current cost model.

Protocol Revision 6 freezes the exact ParaToric route before any independent
critical scan.

Protocol Revision 7 subsequently freezes the periodic winding-probability
Binder statistic as the independent primary locator, the SIT Binder statistic
as its supporting locator, both exact target-field grids and size sequences,
the paper-matched update cadence, raw-series gates, the finite-size fit, and
the separate per-lattice acceptance rules. No critical-observable data existed
when Revision 7 was written.

## 3. Pinned external build

The qualified checkout is `.training/tools/paratoric-v1.0.3` at upstream
commit

`e7bc78446ba083aeeae1ada9c883fa03bf205890`.

The local compiler required a build-only compatibility patch:

1. add the missing `<print>` include;
2. replace indexed `std::println` placeholders with standard `{}`
   placeholders.

Exact patch SHA-256:

`3bd7a5231c38f048035f13f23bb20162b6f6e1f2264270dbeb61e2ce35073d30`.

The ParaToric core and both upstream tests build and pass with the separately
provisioned shared Boost 1.88 libraries. No ParaToric source or Boost binary is
vendored into the training contribution.

## 4. Frozen dual route

For the target TFIM

$$
H=-\sum_{\langle ij\rangle}\sigma_i^z\sigma_j^z
  -h\sum_i\sigma_i^x,
$$

the ParaToric `x`-basis parameters are

$$
h_{\rm eTC}=1,\qquad J_{\rm eTC}=h,\qquad
\lambda=0,\qquad\mu=64,
$$

with periodic boundaries.

| Target TFIM | ParaToric gauge lattice |
|---|---|
| Square audit | Square |
| Triangular | Honeycomb |
| Honeycomb | Triangular |

The comparison observables are the exchange and transverse-field Hamiltonian
components. Their sum provides a secondary total-energy identity.

## 5. Ensemble qualification

An even-spin-flip-sector ED comparison was initially considered because a
periodic toric-code duality can impose a global constraint. The nondegenerate
square $L=3$ audit decisively distinguishes the two ensembles: ParaToric's
periodic observable trace follows the full TFIM thermal trace, while the even
sector is measurably shifted.

The full trace is therefore the comparison oracle. Even-sector ED remains in
the output as a diagnostic to catch accidental ensemble changes.

## 6. Small-torus cross-method result

The final qualification run is `results/c148-paratoric-ed-v3/` with four
independent ParaToric chains, 200,000 thermalization updates, 50,000 stored
samples per chain, and 100 updates between stored samples.

| Target case | Gauge lattice | Compared components | Result |
|---|---|---:|---|
| Square $L=3$ | Square | Exchange and transverse field | 2/2 `Agreement` |
| Triangular $L=2$ | Honeycomb | Exchange and transverse field | 2/2 `Agreement` |

The QMC uncertainty is the maximum of base-block, doubled-block, and
independent-chain standard errors. All four absolute differences lie within
five combined standard errors; the largest standardized difference is 2.36.
Every sampled star observable remained exactly $+1$, so the maximum observed
star defect is zero. The recorded analytic charge-pair acceptance bounds are
below $2\times10^{-109}$ for the square case and below $5\times10^{-47}$ for
the triangular-target case.

The ParaToric triangular gauge lattice at $L=2$ is degenerate and was excluded
as a honeycomb-target oracle. A dense ED calculation at the first valid size,
$L=4$, would require 32 TFIM spins and is infeasible. The first valid
honeycomb-target check therefore compares ParaToric with the independently
implemented direct SSE route at the same finite volume.

The accepted comparison is `results/c148-paratoric-sse-honey-l4-v2/` at
$L=4$, $h=2.1325$, and $\beta h=L$. It uses four ParaToric chains with 200,000
thermalization updates, 50,000 stored samples, and 100 updates between samples,
plus four direct-SSE chains split evenly between hot and cold starts. Both
exchange and transverse-field energies are tagged `Agreement`. The
standardized differences are 0.78 and 0.16, respectively. ParaToric emitted no
autocorrelation warnings, all sampled stars remained $+1$, the direct-SSE sign
remained one, and the independent component-sum identity passed.

A subsequent start-state audit found that the direct-SSE transverse-field
component has a hot/cold standardized difference of 10.1535; the exchange
component gives 3.2523. Revision 6 required the two start types but did not
freeze a start-agreement threshold, so the historical `Agreement` tag is not
rewritten. Proposed Protocol Revision 8 adds the missing equilibration gate
and a higher-thermalization repair run before this finite-volume comparison is
treated as final physical evidence.

## 6.1 Revision 7 cost pilots

The first triangular-target pilot attempt
`c148-paratoric-triangular-critical-pilot-v1` exposed an implementation error:
the protocol hash generated unsigned 32-bit seeds while ParaToric accepts a
positive signed `int`. Seven cells failed at argument parsing and one happened
to use an in-range seed. The failed manifests are retained and no `v1` data
enter a cost model.

The corrected driver maps protocol hashes deterministically into
$1\ldots2^{31}-1$ and records sampler stderr on failure. Both `v2` pilots pass
8/8 cells with zero star defects:

| Target | Pilot sizes | Median cell walls | Projected CPU time | Ideal wall at 16 workers |
|---|---|---|---:|---:|
| Triangular | 8, 16 | 0.16 s, 1.46 s | 39.33 h | 2.46 h |
| Honeycomb | 10, 16 | 0.22 s, 0.98 s | 18.01 h | 1.13 h |

Both projections exceed the ten-minute local threshold. The provisioned
`scnet` and `qdeshell` profiles currently have no installed per-account SSH
host/key configuration, so both mandatory prechecks return `ssh_ok: false`.
No production job has been submitted.

## 7. Artifacts and provenance

| Artifact | SHA-256 |
|---|---|
| `cross-method-check.csv` | `4e979d3c9a36b2979e91642e941d43e4a37755049d9407abc5b3cd6c870d971d` |
| `metadata.json` | `c2159b7bc21064466ac4bbe6b94c2937dd7be6c5018b6c440cf4cb3f6deb26d8` |
| `paratoric-raw.csv` | `a1dcec570b8009cbd84d8bf0268a4794ebb2bcec310e0ae522a210a60f263e56` |

Honeycomb-target $L=4$ direct-SSE comparison:

| Artifact | SHA-256 |
|---|---|
| `cross-method-check.csv` | `3ff0eabda620e0e38f944a6aa6ee9f53810a8596fa329aa3e5e76d9baee17600` |
| `metadata.json` | `73fd8e230539b04c970871351a2e53927e3b630e2bb8310afa5ad0f071561d85` |
| `paratoric-raw.csv` | `3b369bcc1885552c3b56f1bb2ba804605a2a8800853d2ad3de37c2ee8fb6f886` |
| `sse-raw.csv` | `12ae260bb60340c5959ab50ee5a0587049a1db35cb8e9d8370fedb0acd9e3d9d` |

The original optional audit target, parity-resolved ED support, runner, tests,
and Protocol Revision 6 are committed in the training worktree at
`e2b8323d79deb41b3916c1d8ef2a018e3e5f65f8`. The $L=4$ comparison metadata
records that the new direct-SSE component route was still an uncommitted source
change and pins both executable hashes plus the driver hash.

Generated raw data, the external ParaToric checkout, and Boost libraries
remain ignored local runtime artifacts.

## 8. Validation evidence

| Validation | Result |
|---|---|
| Default challenge build | Pass |
| Default challenge CTest | 9/9 pass; 230.20 s |
| Python analysis tests | Pass |
| Optional `paratoric_crosscheck` target | Builds |
| Optional `paratoric_critical_sampler` target | Builds |
| Fixed-seed critical-sampler reproducibility | Byte-identical raw output |
| Corrected signed-seed cost pilots | 16/16 cells pass |
| Revision 7 analysis unit tests | Pass, including Binder and corrected-fit recovery |
| ParaToric upstream CTest | 2/2 pass |
| Small-torus component comparisons | 4/4 `Agreement` |
| Charge-sector gates | 3/3 pass |
| Honeycomb-target $L=4$ direct-SSE components | 2/2 `Agreement` |
| Direct-SSE component-sum identity | Pass |
| `git diff --check` | Pass |

## 9. Deviations and unresolved risks

1. The compatibility patch is external and must be reapplied exactly from its
   recorded hash on a fresh machine until upstream compiler compatibility is
   fixed.
2. Dense ED is infeasible for the first nondegenerate honeycomb-target size;
   the required $L=4$ finite-volume check instead passes against direct SSE.
3. Energy-component agreement does not validate ParaToric's critical
   observable convention or finite-size scaling pipeline.
4. The generic harness `scripts/scaling_fit.py --form data-collapse` cannot
   implement the frozen Revision 7 analysis: it lacks the registered analytic
   correction terms, fixed exponents, weighted joint fit, registered-variant
   envelope, and chain-plus-circular-block bootstrap. The accepted estimate
   must therefore use a ParaToric adapter around the existing challenge-specific
   corrected fitter; substituting the generic collapse fit would require a new
   protocol revision.
5. The Revision 7 raw-series sampler and cost driver are implemented, but the
   production analyzer has not yet consumed a complete production grid.
6. The stored honeycomb-target $L=4$ direct-SSE field-energy chains fail a
   post-hoc hot/cold diagnostic at 10.1535 standard errors. Proposed Revision 8
   freezes a transparent repair rather than silently changing Revision 6.
7. Both available remote profiles fail SSH precheck because their per-account
   aliases and credentials are not provisioned; the measured production jobs
   are too large for the local threshold.
8. No target-lattice critical-observable scan or finite-size extrapolation has
   been run.
9. No independent critical field or thermodynamic extrapolation is accepted.
10. The independent route therefore cannot yet enter the final uncertainty or
   verdict gate.

## 10. Stage-gate decision

| Gate | Status |
|---|---|
| Exact source and patch provenance | Pass |
| Dual coupling normalization | Pass on qualified finite volumes |
| Correct periodic trace ensemble | Pass |
| Charge-sector suppression | Pass on qualified finite volumes |
| Triangular-target ED comparison | Pass at $L=2$ |
| Honeycomb-target direct-SSE comparison | Revision 6 pass; Revision 8 repair pending |
| Additional selected direct finite-size comparisons | **Pending** |
| Independent thermodynamic extrapolation | **Pending** |

**Stage 7 remains gate-pending.** The normalization route is qualified, but
the preregistered independent thermodynamic-limit requirement is not met.

## 11. Next work plan

1. Use the completed cost projections to keep production on a remote CPU
   cluster under the harness resource thresholds.
2. Ratify and run the proposed Revision 8 $L=4$ equilibration repair.
3. Provision one authenticated CPU-cluster SSH profile, probe its queue, and
   ratify the production partition and array request.
4. Build and smoke-test the pinned ParaToric source on the selected remote
   environment.
5. Run the clean-source Revision 7 production grids and analyze them with the
   completed ParaToric adapter.
6. Extend the ParaToric and direct-SSE comparison to predeclared target finite
   sizes without using the sealed ratio to tune sizes or fields.
7. Run the production scan only after the source tree, analysis adapter,
   sampling gates, and compute-resource gate all pass.
8. Accept an independent critical field only after finite-size and
   thermodynamic-limit agreement; do not average discrepant routes.
9. Proceed to Stage 8 only after both Stage 5/6 precision gates and the Stage 7
   independent-route gate pass.

## 12. Agent Review and Suggestions

### 2026-07-29 local-compute closeout

Per the workstation resource limit, local work stopped after a basic software
checkpoint. The current training commit passed the Python analysis suite,
Python compilation of both ParaToric critical-scan tools, the Release build,
and all 9 CTest cases in 231.58 seconds. No production scan was started.

As a focused estimator check, square $3\times3$ at $h=3$ and $\beta=4$ gave
SSE $\xi/L=0.3461983990$ versus exact ED $0.3461010817$, a relative difference
of $2.81\times10^{-4}$. This evidence supports leaving the equal-time
estimator unchanged.

Recommendation: retain `gate-pending`, defer Protocol Revision 8 and both
Revision 7 production grids to authenticated cluster resources, and do not
unseal the ratio until the independent-route and precision gates pass.

### 2026-07-29 production-contract audit

Training commit `e1de23fd213257136821d613f7bf8cec41fa47da` hardens the
ParaToric production boundary without changing the frozen protocol. Execution
now requires the clean source commit recorded by the plan; successful resume
revalidates the raw hash; manifest collection verifies planned and observed
provenance, artifact size and hash, and diagnostics recomputed from raw rows.
The raw contract additionally checks $\mu$ and constant nonnegative package
autocorrelation times. The analyzer resolves observable columns by name and
requires the direct-route `accepted` field to be a JSON boolean.

Regression evidence comprises the Challenge 148 analysis suite, Python
compilation, 36/36 generic parameter-scan tests, both corrected eight-chain
pilot sets passing the hardened validator, and a clean-source plan smoke pinned
to `e1de23f`. The cost projections remain 39.33 CPU hours for triangular and
18.01 CPU hours for honeycomb.

One software gate remains open before production acceptance: the repository
does not yet generate the accepted Revision 7 direct-SSE `summary.json` that
the ParaToric analyzer consumes. This must be implemented and tested; it does
not justify local production or unsealing the ratio.

### 12.1 Requested review focus

- Re-derive the full-trace ensemble result from ParaToric's periodic update and
  topology conventions, independently of the numerical square audit.
- Audit periodic plaquette incidence for the first triangular gauge sizes and
  freeze the smallest nondegenerate honeycomb-target sequence.
- Review the independent-route observable and uncertainty plan before any
  large ParaToric run.

### 12.2 Suggestions log

| Reviewer | Date | Finding | Disposition | Status |
|---|---|---|---|---|
| Independent-route audit | 2026-07-29 | ParaToric periodic data match full-trace rather than even-sector ED on square $L=3$ | Freeze full thermal trace in Revision 6 | Resolved |
| Independent-route audit | 2026-07-29 | ParaToric triangular $L=2$ has degenerate periodic plaquette incidence | Exclude it as a honeycomb-target oracle; start at $L\geq4$ | Resolved; $L=4$ direct-SSE comparison passes |
| Independent-route audit | 2026-07-29 | Honeycomb-target $L=4$ has 32 TFIM spins and cannot use dense ED | Compare energy components against direct SSE with independent-chain and reblocking budgets | Resolved; 2/2 `Agreement` |
| Independent-route audit | 2026-07-29 | Finite-volume energy agreement alone does not satisfy Stage 7 | Keep stage gate open until independent thermodynamic extrapolation | Open |
| Independent-route audit | 2026-07-29 | ParaToric's package Binder convention is inverse to direct $Q_L$ and its periodic percolation observable is a winding projector | Freeze $U_\Pi$ labeling, SIT support, axes, raw-series gates, and fit in Revision 7 before critical data | Resolved in protocol; compute pending |
| Scaling-fit audit | 2026-07-29 | The generic data-collapse script does not represent the frozen corrected joint fit or chain-plus-block bootstrap | Keep the preregistered challenge-specific fitter and implement a ParaToric raw-series adapter before production | Resolved; adapter implemented and unit-tested |
| Cost-pilot audit | 2026-07-29 | Unsigned 32-bit protocol seeds exceed ParaToric's signed-int parser | Preserve failed `v1`; constrain deterministic seeds to the signed range and start corrected `v2` run IDs | Resolved; 16/16 `v2` cells pass |
| Equilibration audit | 2026-07-29 | Stored $L=4$ direct-SSE field-energy chains retain a 10.1535-sigma hot/cold difference | Draft Revision 8 with a predeclared higher-thermalization rerun and explicit start gate | Open; ratification pending |
| Resource audit | 2026-07-29 | Revision 7 production projects to 2.46 h and 1.13 h at 16 ideal workers, while both remote SSH aliases are unprovisioned | Do not launch locally; provision and probe an authenticated CPU cluster | Open |
| Production-contract audit | 2026-07-29 | Resume, raw-field, provenance, and direct-summary type checks were incomplete | Harden runner/analyzer contracts and add tamper regressions | Resolved in `e1de23f` |
| Direct-summary audit | 2026-07-29 | No producer emits the accepted Revision 7 direct-SSE summary required by the independent analyzer | Implement and test the frozen direct-route summary contract before production acceptance | Open |
