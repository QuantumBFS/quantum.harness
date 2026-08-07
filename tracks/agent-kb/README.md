# AI Agent and Knowledge Base

A track about **AI for science**, on two coupled fronts:

1. **Using AI agents to do research** — agents that plan, run, and interpret
   scientific computations (the harness itself is one working example).
2. **Building scientific knowledge bases for AI** — turning the scientific
   literature and method craft into structured, machine-consumable knowledge that
   grounds those agents (the harness's `.knowledge/` cards are one instance).

Unlike the method tracks (ED, MPS, PEPS, QMC, …), the deliverable here is not a
reproduced physics figure but a **more capable research agent or a better
scientific knowledge base for AI**: agent reasoning and tool use, retrieval and
grounding faithfulness, knowledge-card design and coverage, or an evaluation that
measures any of these.

This track suits participants from AI / systems / data backgrounds who want to
advance how AI does science, rather than a single computational method.

**Track leads:** [Kun Chen (陈锟)](https://scholar.google.com/citations?user=YItDGoIAAAAJ),
[Jin-Guo Liu (刘金国)](https://scholar.google.com/citations?user=4edw228AAAAJ).

## Reproduction target

**Chosen (2026-07-28, team Fveritas):** the meta-challenge
[#133 — the problem factory](https://github.com/QuantumBFS/quantum.harness/issues/133):
a harness that generates, solves, and publishes its own autoresearch problems.
Solution lives in [`solutions/problem-factory/`](solutions/problem-factory/)
(one-command demo, calibration gate against #124–#128 + held-out #112,
heuristics library).

Onboarding reproduction anchor: issue #112 (sawtooth-chain localized-magnon
erosion, detuning axis) — solved at reconnaissance scale, all closed-form
anchors reproduced to 1e-8–1e-10 and cross-checked with XDiag; see
`solutions/problem-factory/README.md` § Reproduce for the 5-prompt mentor
quickstart.

## References

To be populated when the target is chosen. Foundational directions for this track:
retrieval-augmented generation, tool-use / reasoning-and-acting agents, agent
evaluation and grounding faithfulness. Use `/download-ref <arXiv-id|DOI>` to fetch
the chosen references into `.knowledge/literature/` with correct metadata rather
than hand-entering citations here.
