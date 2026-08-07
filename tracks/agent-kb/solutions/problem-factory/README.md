# Problem Factory — a rocket-test approach to issue #133

**One command:** `python3 run_demo.py` · **Judging this work?** Read [ARGUMENT.md](ARGUMENT.md) — the case for correctness and usefulness, with reproduction evidence. **Challenge report:** [report/report.html](report/report.html) (self-contained, figures embedded; regenerate via prompt 5 below).

## Reproduce (mentor quickstart — 5 prompts)

From a fresh clone, each numbered line is one short prompt to the agent (or run
the command directly). Expected output is what reproduction success looks like.

```bash
# 0. dependencies (one command; numpy scipy pyyaml matplotlib)
python3 -m pip install -r requirements.txt
cd tracks/agent-kb/solutions/problem-factory
```

| # | prompt | runs | expect |
|---|---|---|---|
| 1 | "Run the problem factory's first flight" | `python3 run_demo.py` (~2 s) | `launched 5: survivor 1, deferred 1, dead 3` |
| 2 | "Run the calibration gate" | `python3 run_calibration.py` (<1 s) | `-> CALIBRATED` (dev 5/5 pos, test 1/1 pos) |
| 3 | "Reproduce the issue #112 sawtooth solve" | `python3 tests/test_sawtooth.py && python3 run_sawtooth.py` (~20 s) | `all anchors green` + two figures in `briefs/figures/` |
| 4 | "Build the challenge run folder" | `python3 build_run.py` (<1 s) | `tracks/agent-kb/results/20260728-sawtooth-erosion/run.json` |
| 5 | "Generate the challenge report" | `/challenge-report` | interactive report → `report.html` next to `run.json` |

Optional: close the learning loop — `python3 tests/test_learning_loop.py &&
python3 run_learning_loop.py` (~10 s) replays round 1, regenerates a
heuristics-licensed round-2 fleet, and reports budget waste dropping
29% → 0% (`results/learning_loop.md`).

Optional (needs Julia + XDiag, `make` toolchain): cross-check the anchors with
an independent ED stack —
`julia --project=julia-env scripts/xdiag_crosscheck.jl`.
Skip if Julia is unavailable; the anchors are already Harness-anchor verified.

## The idea

Issue #133 asks for a factory that generates, solves, and publishes new quantum
many-body research problems. The hard part is not generating problems — it is
judging them. Multi-agent debate about "which problem is good" drifts into
plausible-sounding vagueness, so this factory does not let agents judge at all.
**Problems are judged by experiments**, the way SpaceX judges rockets:

| rocket test | problem factory |
|---|---|
| success criteria frozen before launch | gate frozen in the card before any solve |
| static fire | first-principles checks: Bethe-ansatz energy, [H, Sz] = 0 |
| hop test | small-size ED grid over the declared parameters |
| telemetry or it didn't happen | one machine-readable JSON per card |
| explosion is data | every dead card is recorded with a root cause |

The demo launches 5 cards and shows the factory has teeth in both directions:

```
launched 5: survivor 1, deferred 1, dead 3
  xxz-j2-gap-001       survivor  — J2=0.3 shifts the gap 5.5σ above finite-size noise
  xxz-j2-deferred-004  deferred  — J2=0.05 visible (0.93) but indecisive: launch bigger
  xxz-j2-tiny-002      dead      — no_signal: J2=0.001 invisible at these sizes
  xxz-bad-setup-003    dead      — setup_error: pauli/spin convention mix-up caught
                                   by the Bethe oracle (E/N off by 4×)
  xxz-j2-gap-001-dup   dead      — duplicate_fingerprint
```

Three distinct death causes, each detected by a different mechanism — that is
the deliverable, not the one survivor.

## Layout

- `pf/ed.py` — minimal XXZ+J2 exact diagonalization (Sz=0 sector, scipy, ~50 lines) + sawtooth-chain builder
- `pf/cards.py` — template-generated demo cards + fingerprint dedup (interface A)
- `pf/static_fire.py` — first-principles checks (Bethe E/N at Δ=1, Sz conservation, sawtooth flat band & Lucas degeneracy)
- `pf/probe.py` — hop test: full (L, Δ, J2) grid, decisiveness vs finite-size noise
- `pf/verdict.py` — three-state verdict + battle report (`results/report.md`)
- `pf/rubric.py` + `run_calibration.py` — quality-class ruler (record/map), calibrated against #124–#128 + held-out #112. **Superseded as a taxonomy** by the engineering/abstract framework in [`docs/design/problem-generation.md`](docs/design/problem-generation.md) (badness filter + decomposition granularity); the code refactor lands next round — behavior and calibration are unchanged for now
- `pf/heuristics.py` — deposits every verdict into the `heuristics/` library (issue #133's growth-curve deliverable)
- `pf/budget.py` + `pf/round2.py` + `run_learning_loop.py` — hop-compute accounting and the heuristics-licensed round-2 fleet (§ The loop closes)
- `pf/sawtooth.py` + `run_sawtooth.py` — the issue #112 detuning-axis solve (below)
- `build_run.py` — materializes the gitignored challenge-run folder (`tracks/agent-kb/results/…/run.json`) for `/challenge-report`
- [`docs/user-manual.md`](docs/user-manual.md) — fresh-session playbook for a new domain: literature mining → card → launch → solve, with the issue #133 capability checklist
- `tests/` — anchor tests, plain asserts: `python3 tests/test_sawtooth.py`
- `AGENTS.md` — card schema, telemetry schema, coding style for agent sessions

## Solved: issue #112 detuning axis (reconnaissance scale)

**One command:** `python3 run_sawtooth.py`

Deliverables (committed):

- `briefs/sawtooth-erosion-001.md` — physics picture, method, results, conclusions, honest novelty assessment
- `briefs/figures/magnetization_curves.png` — the jump at δ=0 smearing into staircases for δ≠0
- `briefs/figures/erosion_metrics.png` — W(δ), ΔM(δ), Γ(δ) vs one-magnon bandwidth
- `briefs/data/erosion.json` — all raw data (N=12,16; δ=−0.3…+0.3)
- `docs/sawtooth-ed-feasibility.md` — machine/complexity feasibility report (local to N=20, cluster for N=28)

Headline: all closed-form anchors reproduced to 1e-8–1e-10; the jump smearing
Γ(δ) tracks the one-magnon bandwidth — smearing is single-particle physics.
Candidate new observation (unverified): Γ exceeds the bandwidth for δ<0 but
not δ>0 — needs N=20–28 + degenerate-PT cross-check before it is a claim.

## The loop closes (Day 4): verdicts change the next fleet

**One command:** `python3 run_learning_loop.py`

A factory that only filters cards is a screening machine. The point of the
heuristics library is that **verdicts feed back into generation** — the
system is a sequential decision loop, not a generator + judge:

```
literature open problems -> boundary cards -> experiment -> verdict
        ^                                                    |
        └──────── heuristics library (lessons) <─────────────┘
```

Round 1 flies blind and pays for it: 18 of 63 hop ED solves (29%) are
wasted on a card whose perturbation sits below the finite-size noise floor.
Its five verdicts deposit five heuristics entries. Round 2's fleet is
generated under those lessons — every card names its `licensed_by` entries
in `cards/round2/`:

- `xxz-j2-tiny-002` → never launch |J2| below the noise floor
- `xxz-bad-setup-003` → generator pins `convention: spin`
- `xxz-j2-gap-001-dup` → fleet is pre-deduped by fingerprint
- `xxz-j2-gap-001` (decisive at J2=0.3) + `xxz-j2-deferred-004` (indecisive
  at 0.05) → probe where the decision boundary lies; relaunch 0.05 bigger

| round | launched | survivor | deferred | dead | hop EDs | wasted on no_signal |
|---|---|---|---|---|---|---|
| 1 (no heuristics) | 5 | 1 | 1 | 3 | 63 | 18 (29%) |
| 2 (heuristics applied) | 3 | 1 | 2 | 0 | 54 | 0 (0%) |

Zero deaths, zero wasted solve — and the loop sharpens the map: the
decision boundary is bracketed between J2=0.1 (decisiveness 1.85) and 0.2
(3.70); the relaunched J2=0.05 card improved 0.93 → 1.60 but stays
deferred, so the library now recommends L≥14 — the next fleet is already
written by this round's telemetry. New problems grow from results; the
sawtooth detuning asymmetry above is the same phenomenon at research scale.

Honesty note: the round-2 fleet is rule-generated, each choice citing its
heuristic entry — this demonstrates the loop mechanism, not an LLM
generator. Anchors: `tests/test_learning_loop.py`.

## Key design decisions

1. **Gate-first.** A card without a frozen, executable gate never enters the
   pipeline. Gates are declared per card (`gate.kill_if`), never edited after launch.
2. **Decisiveness, not discussion.** The quality metric is
   |gap(J2) − gap(J2=0)| measured against the baseline's own finite-size noise.
   No agent opinion appears anywhere in the verdict path.
3. **Deferred is a first-class verdict.** Signals that are visible but
   indecisive at small sizes are not killed and not passed — they go back to
   the human with a "launch bigger" recommendation. (One lesson already learned:
   in a gapless phase both the gap and its perturbation shrink as 1/L, so a
   raw "effect must grow with L" criterion is wrong for gap observables.)
4. **Failures are assets.** `results/telemetry.jsonl` + the mishap review are
   the seed of the heuristic library issue #133 asks for.

## Next steps (Day 2+)

- Scale hop tests to the cluster via `scripts/harness_array_sbatch.sh`
  (L=12–16, more Δ/J2 points) for deferred cards.
- Replace `pf/cards.py` templates with an LLM generator behind the same schema
  (interface A is the contract; the generator is swappable).
- Turn repeated death causes into heuristic-library entries.

## Harness contributions (PR element ①)

Solving #112 surfaced a knowledge-discovery gap (the sawtooth model was
invisible to the agent) — fixed mechanism-level, not just for this session:

- `.knowledge/solvable/sawtooth-localized-magnon/` — exact-solution oracle card
  (runnable `oracle.py`, 6 self-test anchors, registered in the solvable INDEX)
- `.knowledge/models/sawtooth-chain/MODEL.md` — model card (method routing,
  validation pointers) cited by the oracle card
- `skills/quantum-model/SKILL.md` — dispatcher whitelist now includes
  sawtooth-chain, so the model is discoverable by any future session
- root `AGENTS.md` — "no card, make the card" rule: a computation targeting a
  model with no KB card must deposit one as part of the session's deliverable
- root `.gitignore` — `.venv/` now ignored (commit b6b1279), removing a
  trap every fresh setup hit
- `scripts/xdiag_crosscheck.jl` — scipy↔XDiag cross-check upgrading the
  sawtooth anchors to *Harness anchor* provenance
