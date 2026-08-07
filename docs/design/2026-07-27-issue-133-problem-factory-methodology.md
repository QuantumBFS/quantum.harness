# Issue #133 Problem Factory Methodology

Date: 2026-07-27  
Context: Harnessing Quantum 2026, agent-kb track  
Issue: <https://github.com/QuantumBFS/quantum.harness/issues/133>

## Positioning

The problem factory should start as a **design and solution-layer methodology**, not as a core runtime change to Quantum Harness.

Recommended staging:

1. **Methodology document in `docs/design/`**: capture the architecture, assumptions, gates, rejection rules, and conversation prompts.
2. **Prototype under `tracks/agent-kb/solutions/`**: implement a minimal end-to-end demo that generates, rejects, solves, and reports problem cards.
3. **Only promote reusable parts into core harness** after the prototype proves which abstractions are stable.

Why not add it directly to core first:

- Issue #133 is still exploratory: premature core integration risks hardcoding the wrong abstraction.
- The existing harness philosophy keeps runtime stable; dev scaffolding belongs in `docs/` until validated.
- A solution-layer prototype is easier to review during the hackathon and easier to discard or reshape.

What can later move into core:

- Problem-card schema.
- Gate validation interface.
- Novelty fingerprinting helper.
- Provenance and rejection-log conventions.
- Heuristic-library update workflow.

## Core Thesis

The factory should not ask an agent to freely invent research problems. It should ask the agent to produce **auditable, gate-first problem cards**.

Bad order:

```text
interesting idea → vague research question → maybe a validation method
```

Preferred order:

```text
executable gate → compatible model family → constrained mutation → frozen problem card → solve or reject
```

The central artifact is not a paragraph of inspiration. It is a structured problem card with:

- source seed;
- mutation recipe;
- exact system setup;
- target observable;
- frozen gate;
- novelty fingerprint;
- compute budget;
- rejection conditions;
- provenance log.

## Minimal Architecture

```text
seed corpus
  ↓
mutation engine
  ↓
candidate problem cards
  ↓
gate validator ── reject if no executable frozen gate
  ↓
novelty checker ── reject if duplicate or too close
  ↓
accepted problem archive
  ↓
solver runner
  ↓
verifier / skeptic pass
  ↓
report writer
  ↓
heuristic library update
```

### 1. Seed Corpus

The seed corpus contains known safe model families and known observable families. It is not a literature database yet.

Example seeds:

- XXZ spin chain;
- transverse-field Ising chain;
- J₁-J₂ Heisenberg chain;
- Bose-Hubbard small clusters;
- simple quantum circuit simulation benchmarks;
- polynomial-optimization / SDP toy certificates.

Each seed should state:

- model name;
- supported sizes;
- safe methods;
- known observables;
- allowed mutations;
- references or local knowledge cards.

### 2. Mutation Engine

Generate problems by constrained mutation, not free invention.

Useful mutation classes:

| Mutation | Example | Why useful |
|---|---|---|
| Parameter-window mutation | Δ = 0.8, 1.0, 1.2 around XXZ point | Easy to gate and sweep |
| Boundary mutation | open → periodic | Changes physics while preserving solver |
| Perturbation mutation | add weak J₂ term | Produces nearby but distinct problems |
| Observable mutation | energy → gap → correlation → entanglement | Reuses solver, changes question |
| Certification mutation | raw result → bootstrap / interval / bound | Makes problem more harness-native |
| Solver mutation | ED baseline → DMRG / QMC / SDP cross-check | Turns solution experience into method guidance |

### 3. Problem Card

A problem card is the frozen contract between generator, solver, and reviewer.

Suggested fields:

```yaml
id: spinchain-xxz-j2-gap-001
title: Detect finite-size spectral-gap shift in a weakly perturbed XXZ chain
domain: quantum-many-body
status: candidate

source:
  seed: xxz-chain
  mutation:
    - add_next_nearest_neighbor_zz
    - scan_delta_window
  provenance:
    generated_by: problem-factory-v0
    prompt_log: logs/generation_trace.jsonl

system:
  model: xxz_chain
  hamiltonian_convention: harness-default-xxz
  boundary: periodic
  sizes: [6, 8, 10]
  parameters:
    delta: [0.8, 1.0, 1.2]
    j2: [0.0, 0.05, 0.1]

observable:
  name: spectral_gap
  definition: E1 - E0 in the declared symmetry sector or full Hilbert space

gate:
  type: exact_diagonalization_gap_trend
  frozen: true
  success_conditions:
    - compute all declared parameter points
    - emit machine-readable gap table
    - compare J2 > 0 against J2 = 0 baseline
  rejection_conditions:
    - missing executable gate
    - duplicate fingerprint
    - unsupported method under declared budget
    - solver failure
  tolerance:
    eigenvalue_absolute: 1.0e-8

novelty:
  fingerprint: spinchain/xxz/periodic/spectral-gap/j2-perturbation/L6-10
  duplicate_of: null
  novelty_score: null

budget:
  max_runtime_seconds: 300
  max_memory_mb: 4096
```

### 4. Gate Validator

The gate validator is the main anti-garbage mechanism.

Reject a candidate if:

- there is no gate;
- the gate is not frozen at generation time;
- the success condition is natural-language-only and not executable;
- the solver method is unavailable;
- the required compute exceeds the declared budget;
- the observable is not defined precisely enough to reproduce.

Gate-first rule:

> A problem without an executable frozen gate is not a problem-factory output. It is only a brainstorming note.

### 5. Novelty Checker

Do not let the agent merely assert novelty. Start with deterministic fingerprints.

Fingerprint template:

```text
model / geometry / boundary / observable / parameter-window / method / gate
```

Example:

```text
spinchain/xxz/periodic/spectral-gap/j2-perturbation/ed-gap-trend/L6-10
```

MVP checks:

- duplicate fingerprint inside generated cards;
- overlap with existing local challenge folders;
- overlap with known seed problem IDs.

Later checks:

- similarity search over knowledge cards and issue texts;
- literature title / abstract retrieval;
- LLM skeptic review;
- human gatekeeper declaration.

### 6. Solver Runner

The solver should be selected from the gate, not from agent preference.

Example mapping:

| Gate | Solver route |
|---|---|
| `exact_diagonalization_gap_trend` | `/method-ed` or local ED script |
| `bootstrap_observable_shift` | parameter sweep + resampling report |
| `sdp_lower_bound_gap` | `/method-polyopt` or NCTSSOS route |
| `cost_model_crossover` | resource-estimation script |
| `cross_method_consistency` | primary method + `/cross-method-check` |

The first prototype only needs one working solver. Exact diagonalization on small spin chains is the safest first route.

### 7. Skeptic Pass

Every accepted result should be attacked before being reported.

Skeptic questions:

- Was the gate changed after generation?
- Is the Hamiltonian convention explicit?
- Is the symmetry sector explicit?
- Is the result just a duplicate of an existing challenge?
- Did the solver exceed the budget?
- Is the effect stable enough to report?
- Was any parameter cherry-picked after seeing the answer?

The skeptic can downgrade a solved problem to:

- `solved_but_unverified`;
- `failed_gate`;
- `needs_cross_check`;
- `rejected_after_solve`.

### 8. Report Writer

The report should be short, mechanical, and auditable.

Minimum report sections:

1. candidate count;
2. accepted count;
3. rejected count by reason;
4. solved count;
5. problem-card paths;
6. result paths;
7. gate status;
8. heuristic-library updates;
9. unresolved risks.

Example summary:

```text
Generated: 3
Accepted: 1
Rejected: 2
Solved: 1
Gate passed: 1
Heuristics added: 2
```

This is more credible than claiming five successful discoveries on day one.

### 9. Heuristic Library

The heuristic library is the knowledge product of the factory. It records what worked, what failed, and how future agents should choose.

Example entry shape:

```markdown
## H001: Prefer gate-first generation

**Observation:** Problems generated from executable gates survive validation more often than open-ended prose ideas.

**Why:** The gate determines whether the problem can be solved, rejected, and reviewed without moving the goalposts.

**How to apply:** Choose the gate first, then generate only compatible model, observable, and parameter mutations.
```

Failure entries are valuable:

```markdown
## H002: Reject frontier-scale claims without a small-instance oracle

**Observation:** Candidate 2D Hubbard phase-discovery problems were too broad for the declared compute budget.

**Why:** Without a small-instance oracle, the gate cannot distinguish discovery from solver noise.

**How to apply:** Require ED, mean-field, or literature-limit anchors before allowing expensive many-body methods.
```

## Recommended MVP for Day 1

Implement or document a prototype that produces exactly this shape:

```text
Generated candidates: 3
Accepted: 1
Rejected: 2
Solved: 1
Report: 1
Heuristic updates: 2
```

Candidate set:

1. **Accepted**: XXZ chain with weak J₂ perturbation, spectral-gap trend, small ED gate.
2. **Rejected**: vague 2D Hubbard novel-phase discovery, because gate is not executable under budget.
3. **Rejected**: duplicate XXZ gap problem, because fingerprint matches candidate 1.

This demonstrates the full issue #133 workflow in miniature:

- generate;
- freeze gate;
- reject invalid problems;
- solve valid problem;
- preserve provenance;
- update reusable heuristics.

## Conversation Prompts for Agents

Use these as reusable prompts during development or challenge reporting.

### Prompt 1: Generate Candidate Cards

```text
Generate three quantum many-body problem cards from the provided seed corpus.
Use gate-first generation: choose an executable verification gate before writing the problem.
Each card must include model, boundary, sizes, parameters, observable, gate, rejection conditions, novelty fingerprint, and budget.
At least one card should be intentionally rejectable so the factory demonstrates filtering.
Do not claim novelty by assertion; express novelty as a fingerprint and a check plan.
```

### Prompt 2: Gatekeeper Review

```text
Review these candidate problem cards as a strict gatekeeper.
Reject any card whose gate is not executable, not frozen, over budget, missing setup conventions, or too vague to reproduce.
Return accepted cards and rejected cards with one machine-readable rejection reason each.
Do not improve the problem after seeing the gate failure; rejection records are part of the deliverable.
```

### Prompt 3: Novelty Skeptic

```text
Act as a novelty skeptic for these accepted problem cards.
Compare fingerprints against the known challenge list and seed corpus.
Flag duplicates, near-duplicates, parameter-only relabels, and source-paper restatements.
Return a novelty status, duplicate target if any, and a short reason.
```

### Prompt 4: Solver Setup

```text
For the accepted problem card, restate the exact Hamiltonian convention, boundary condition, symmetry sector, observable, system sizes, parameter grid, and compute budget.
Do not run until this setup is ratified.
After ratification, choose the solver implied by the gate and emit machine-readable results.
```

### Prompt 5: Post-Solve Skeptic

```text
Attack this solved problem result.
Check whether the frozen gate was preserved, whether all parameter points were solved, whether the Hamiltonian convention is explicit, whether the observable matches the card, whether the result exceeds budget, and whether any conclusion depends on cherry-picking.
Return gate_passed, gate_failed, or needs_cross_check.
```

### Prompt 6: Heuristic Update

```text
Extract reusable heuristics from this factory run.
Include both successes and failures.
For each heuristic, write Observation, Why, and How to apply.
Prefer operational advice that future agents can follow without this conversation.
```

## Where This Should Live

Current recommended placement:

```text
docs/design/2026-07-27-issue-133-problem-factory-methodology.md
```

Prototype placement:

```text
tracks/agent-kb/solutions/problem-factory/
```

Do not put this whole methodology into `AGENTS.md`. `AGENTS.md` is loaded into every session and should remain stable, concise, and method-agnostic. If this pattern proves reusable, add a short pointer later, not the full design.

Possible future promotion:

```text
.knowledge/physics/problem-generation/PHYSICS.md
skills/problem-factory/SKILL.md
scripts/problem_factory/
```

Promotion criteria:

- at least one end-to-end run;
- repeated reuse across more than one challenge;
- stable card schema;
- clear evidence that the gate and novelty checks reduce bad outputs;
- challenge-report or PR review confirms the artifact is useful.

## Success Criteria for the Hackathon PR

A strong PR does not need to solve the entire issue #133 vision. It should prove the harness pattern.

Minimum convincing evidence:

- methodology document exists;
- one runnable prototype or scaffold under `tracks/agent-kb/solutions/`;
- generated accepted and rejected problem cards;
- frozen gate field visible in cards;
- at least one machine-readable solver result or dry-run result;
- rejection log preserved;
- heuristic library updated;
- README explains how this scales toward five problems and external review.

The pitch:

> This contribution turns problem generation from free-form ideation into a gate-first, auditable, rejectable, reproducible workflow. It is a small prototype of issue #133's research factory, designed so bad problems fail early and good problems become solvable challenge cards.
