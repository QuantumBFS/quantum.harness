---
name: method-ed
description: Use when an exact diagonalization track, ED reproduction, full spectrum, symmetry sector, scar, level statistics, or finite-cluster oracle needs method-level route and tool selection.
---

# Method ED

Exact diagonalization is the finite-Hilbert-space oracle track. Use it to decide what ED route is scientifically required, then invoke the selected tool skill for software setup, parameters, and timing.

## Sources

- Track README: `tracks/ed/README.md`
- Method card: `.knowledge/methods/ed/METHOD.md`
- Interview notes: `docs/ed/interview.html`
- Review notes: `docs/ed/review.html`
- Tool skills: `/using-xdiag`, `/using-quspin`

## Route

1. Inspect the paper target first. Full-spectrum scars, ETH, overlaps across many eigenstates, and level statistics usually require dense full diagonalization inside a fully specified sector.
2. Identify basis, constraints, boundary, and every conserved sector before recommending software.
3. Recommend `/using-xdiag` by default for research-grade ED, symmetry blocks, Lanczos/Krylov, and Julia harness runs.
4. Recommend `/using-quspin` when the paper/official code is Python or QuSpin, when a QuSpin example matches, or when `user_basis` is the clean constrained-basis route.
5. If neither tool can express the target cleanly, present official code / web search / custom implementation as the setup fork, then record it as a deviation.

## Tool Handoff

After selecting the route, invoke the chosen tool skill:

- `/using-xdiag` owns XDiag parameter setup, dense vs sparse estimate, and cluster threshold.
- `/using-quspin` owns QuSpin basis/operator setup, sparse/dense estimate, and Python runtime caveats.

This method skill does not ask tolerance, thread, or matrix-construction details directly; it uses the tool skill for those questions.
