# Problem Factory — Generator-Side Interface (for the generation half of the team)

> You build the factory (mine literature → propose problems → judge → attempt).
> We run the launch site (independent QC gate → experiments → verdict).
> The boundary is **files, not function calls**. Everything below is a contract:
> conform and your output drops straight into the pipeline.
>
> **Status:** §2–§4 are live (QC gate, dedup, static fire, hop, verdict all run
> today). §5–§7 are **contracts frozen ahead of implementation** — heuristics
> consumption, briefs, and cluster launches are being built on our side;
> producing these artifacts now means they get consumed the moment the
> machinery lands.

## 1. Where your four stages land

| Your stage | Pipeline position | What crosses the boundary |
|---|---|---|
| Literature → new problem | mine + crystallize | problem card (interface A) |
| "Is it a good problem?" | prior declaration, **not a veto** | `quality_rationale` field on the card |
| Attempt a solve | first-attempt data | optional `attempt` block; we re-judge independently (fresh evaluation) |
| "Is it worth solving?" | prior declaration | `value_claim` field on the card |
| Feedback to logs | heuristics library | lesson entries (interface C) |
| Physics-picture writeup | per-problem brief | `briefs/<id>.md` |
| Final solvable list | battle report | produced by the verdict stage from telemetry — no manual list needed |
| Cluster runs | Level 1/2 launches | must follow §5 launch discipline |

**Key rule:** your judgments are recorded as *priors*, never as gates. The
rubric, static fire, and hop test judge independently. Agreement builds trust;
**disagreement is itself a deliverable** (it calibrates AI taste against
experimental verdicts — the meta-question of issue #133).

## 2. Interface A — problem card (YAML, one per file, into `cards/`)

```yaml
id: sawtooth-erosion-001          # kebab-case, unique
model: xxz_j2_chain               # MUST be in the solver registry (see §4)
convention: spin                  # spin (S=σ/2) | pauli
setup:
  boundary: pbc
  sizes: [16, 20, 24]             # first-principles-feasible sizes
  params: {j2: [2.0, 2.05, 2.1]}  # FIRST value of the swept axis = baseline
observable: {name: gap, definition: E1 - E0, sector: sz=0}
gate:                             # frozen at generation time, never edited later
  type: gap_trend
  frozen: true
  kill_if: {decisiveness_below: 2.0}
static_fire: [bethe_delta1, sz_conservation]   # checks the launch site must have

# --- generator declarations (priors, recorded, non-blocking) ---
quality_rationale: "why you believe this is a good problem"
value_claim: "why it is worth solving; expected publishable unit"
provenance: {papers_mined: ["PRL 88, 167207"], run_id: "gen-2026-07-28-03"}
attempt:                          # optional: your own solve attempt
  solver: your-stack
  result: "..."
```

Hard requirements (a card missing any of these dies as `uncrystallizable`):
frozen gate with kill criterion · baseline-first parameter grid · a literature
anchor (pinned number + reference) inside `quality_rationale` or provenance.

Quality classes the QC gate (pf/rubric.py) recognizes:
- **record**: one scalar merit to push past a pinned number.
- **map**: a curve family over a *declared* uncharted region, with an analytic
  cross-check (`merit.curve` + `merit.analytic_check` on the card).

## 3. Interface B — telemetry (what you get back, JSONL)

```json
{"problem_id": "...", "verdict": "survivor|deferred|dead", "reason": "...",
 "metrics": {"decisiveness": 0.0, "gradient_vs_L": 0.0, "effect": 0.0, "noise": 0.0}}
```

The verdict report (`results/report.md`) IS the solvable-problem list:
survivors with metrics, deferred with cost-to-decision estimates, dead with
structured causes. If your prior disagreed with the verdict, that pair is
flagged for the value-calibration dataset.

## 4. Solver registry handshake

Cards referencing models our solver cannot build die as `no_solver` (not your
fault — a capability signal). Current registry: `xxz_j2_chain` (ED, Sz=0, full
pipeline), `sawtooth_chain` (builder + first-principles anchors: flat band,
h_sat Lucas degeneracy; hop runner for erosion sweeps in progress), and
`tfim_2d` (chain/square/triangular/honeycomb PBC clusters, even-parity ED,
Binder-cumulant crossings; anchors incl. Jordan–Wigner cross-check — added for
the issue #148 flight, see `briefs/tfim-ratio-sqrt5-001.md`). Batch
statistics of `no_solver` after the first exchange tell us which builders to
add — or which models your generator should avoid.

## 5. Launch discipline (cluster / SSH runs)

No exceptions — these are the launch site's flight rules:

1. **No card without a frozen gate and telemetry definition occupies a launch
   window.** Raw exploratory SSH runs happen outside the pipeline and their
   results do not count as verdicts.
2. Cost estimate BEFORE the first run (memory × wall); non-trivial jobs go
   through the harness's `/using-slurm` + array scripts, not hand-rolled ssh.
3. Every run emits machine-readable telemetry (interface B); a run without
   telemetry is treated as never having happened.
4. Monitor through settle-time; "RUNNING" is not success.

## 6. Interface C — heuristics library entries (your feedback logs)

One YAML per lesson, into `heuristics/`:

```yaml
problem_id: sawtooth-erosion-001
verdict: dead
root_cause: {category: no_signal, evidence: "decisiveness 0.3 at all L"}
lesson: "detuning probes at this size need fidelity susceptibility, not gap"
physics_brief: briefs/sawtooth-erosion-001.md   # optional link
```

The library and its growth curve are a reported output of issue #133 — your
feedback entries are first-class deliverables, not scratch notes.

## 7. Physics briefs

Per problem (survivors and instructive deaths), a short `briefs/<id>.md`:
the physical picture in plain language — what the model is, what the exact
anchor says, what the experiment showed, what the verdict means. Audience:
the mentors at Friday review.

## 8. First exchange (dry run)

Send ONE sample card (any model in the registry) + optionally your solve
attempt. We pour it through QC → dedup → static fire → hop → verdict and
return the telemetry. Zero format errors = the interface holds; then batch.
