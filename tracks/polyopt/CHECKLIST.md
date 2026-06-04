# PolyOpt workflow coverage checklist (generic)

Reusable status map of the end-to-end reproduce-paper / solve workflow for **any**
polynomial-optimization problem — not tied to a specific paper or size. ✅ `[x]` =
already clarified (mostly by the reused **polyopt-guide**, plus the harness adapters
`method-polyopt` / `using-nctssos`); ⬜ `[ ]` = gap to add. Source in parentheses.
polyopt-guide stays ground truth on modeling; gaps live in our adapters.

## Most important (workflow integration)
- [x] Reuse polyopt-guide as modeling ground truth — explicit delegation + precedence rule (method-polyopt)
- [x] Slot into the reproduce-paper spine: proposal → confirm → run → report → verify (design)
- [x] Per-run target captured (model, observable, scan axis, sizes) in `run.json` (reproduce-paper spine)
- [ ] `run.json` figure shape for polyopt — "bound vs scan axis" with a reference overlay + published values as `expected`; build_report rendering unverified (gap)

## Method scope (is polyopt the right method)
- [x] What problems suit it — certified bounds: ground-state energy, Bell, state/trace (method-polyopt + polyopt-guide St.1)
- [x] Route-elsewhere — bound not the state; SDP scaling limits (method-polyopt)
- [x] Certification role / cross-check framing (method-polyopt)
- [ ] Worked-examples with literature scales — what's been solved, at what operator count / order (gap; no general table)

## Method routing (which variant / algebra)
- [x] Variant routing — operator vs state-poly vs trace/tracial vs Bell (polyopt-guide St.1)
- [x] Algebra selection — Pauli / Fermionic / Bosonic / Unipotent / Projector / free (polyopt-guide St.2)
- [x] Operator-vs-tracial formulation for Bell (polyopt-guide St.2)
- [x] Handoff to `/using-nctssos` (method-polyopt)

## Method setup — parameter choice (modeling tricks)

| Parameter | Controls | Covered | Where |
|---|---|:---:|---|
| Relaxation order d | SDP size / bound tightness | ✅ | polyopt-guide St.4 |
| Algebra | which relations are enforced | ✅ | polyopt-guide St.2 |
| Monomial basis / level | moment-matrix rows | ✅ | polyopt-guide (sparsity_guide) |
| Correlative sparsity `cs_algo` | clique decomposition | ✅ | polyopt-guide St.4 |
| Term sparsity `ts_algo` | block structure | ✅ | polyopt-guide St.4 |
| Constraints (eq/ineq, localizing) | feasible set | ✅ | polyopt-guide St.3 |
| Objective sign (min vs max) | minimize −f to maximize | ✅ | polyopt-guide St.3 |
| `ComplexF64` for Pauli | complex coeffs from σ products | ✅ | polyopt-guide St.3 |
| GNS knobs (`H_deg`, `hankel_deg`) | reconstruction quality | ✅ | polyopt-guide St.5 |
| Symmetry reduction (`SolverConfig(symmetry=…)`) | shrink the SDP via problem symmetry — key for large-system scaling | ⬜ | gap (polyopt-guide doesn't emphasize it) |

## Software setup — parameter choice (solver / env)

| Parameter | Controls | Covered | Where |
|---|---|:---:|---|
| `optimizer` = Clarabel | default open-source SDP backend | ✅ | using-nctssos / polyopt-guide |
| Julia env / `make install nctssos` | NCTSSoS + Clarabel into julia-env | ✅ | using-nctssos |
| Clarabel vs Mosek decision | speed / accuracy on large SDPs | ⬜ | gap |
| Mosek install + license | MosekTools.jl + `MOSEKLM_LICENSE_FILE` | ⬜ | gap (recipe installs only Clarabel) |
| SDP tolerances (eps / `*_TOL_*`) | convergence + certificate validity | ⬜ | gap |
| Solver threads | wall time | ⬜ | gap |
| `dualize` (in `cs_nctssos`) | primal/dual form, conditioning | ⬜ | gap (undocumented) |
| Solver verbosity / `set_silent` | progress visibility | ⬜ | gap (NCTSSoS silences internally) |

## Cost estimate (complexity)
- [x] Generic SDP cost heuristic — ~O(nᵈ) moment matrix, memory-bound (method-polyopt + using-nctssos)
- [x] Probe-before-scale (probe at low order, read reported sizes) (using-nctssos)
- [ ] Source-anchored estimate — moment-matrix sizes / solve cost from the reference, when one exists (gap)
- [ ] Concrete local-vs-cluster threshold + `/using-slurm` for large instances (gap; only generic mention)

## Verification — mid-stage
- [x] Solver status + residual shrinking (method-polyopt)
- [x] Bound monotone across relaxation orders (method-polyopt)
- [x] Flatness trend (method-polyopt)
- [ ] Certificate-validity caveat — loose solver tolerance ⇒ reported value not a sound lower bound (gap; ties to software tolerances)

## Verification — final
- [x] Cross-method bracket — E_SDP ≤ E₀ ≤ E_upper (variational / QMC) (method-polyopt)
- [x] Flatness (`test_flatness`) ⇒ exact (method-polyopt + polyopt-guide)
- [x] Limits / small-instance analytic checks (method-polyopt)
- [x] Literature comparison — published reference values, when available (method-polyopt)
- [ ] Expert "Criticize:" list — what to flag in a student's run (gap; deferred earlier)

---

## Gap summary — three real additions (all in our adapters, not polyopt-guide)
1. **Software / solver layer** (using-nctssos + `install-nctssos`) — Clarabel↔Mosek decision, Mosek install + license, tolerance / threads, certificate-validity link. The biggest one.
2. **Symmetry reduction** as a method knob (large-system scaling).
3. **`run.json` figure shape + source-anchored cost** for the reproduce-paper report.
