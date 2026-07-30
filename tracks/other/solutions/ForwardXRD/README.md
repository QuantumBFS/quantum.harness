## Team

| | |
|---|---|
| **Team name** | ForwardXRD |
| **Members** | Yulin Cai |

## Challenge

| Row | |
|---|---|
| **Challenge** | Solve crystal structures directly from powder X-ray diffraction patterns by fine-tuning the pretrained CrystalFormer prior with RL against a pymatgen-simulated pattern-fit reward — going beyond gradient-descent and random-move Monte Carlo solvers, whose rough loss landscape strands them among look-alike wrong structures, by keeping every proposal on the manifold of chemically real crystals. |
| **Catalog issue** | `Addresses #68` — "Solving crystal structures from powder XRD with a generative prior", released by Lei Wang (王磊), IOP CAS. |
| **Track** | `other` |

## Progress

[**SUMMARY.md**](SUMMARY.md) — full write-up: what we built, how it differs from the approach the
issue proposes, and the measurements behind each choice.

**Result:** 7/7 benchmark structures recovered at rms ≤ 0.0015 (strict `ltol = stol = 0.05`),
spanning five crystal systems and 1–9 free internal coordinates, with the unit cell derived from
peak positions alone — no ground-truth cell anywhere in the pipeline. Extended with a held-out
benchmark on 15 real, never-tuned-against Materials Project structures (a substitute for the
issue's SimXRD-4M benchmark step, whose public release turns out to carry no recoverable ground
truth — see SUMMARY.md): **11/15 solved**, spanning cubic through monoclinic, 1–18 dof. Extended
further with a head-to-head run against SmartCellSolver (arXiv:2605.24594).

**Headline finding:** the generative prior is essential; the variational RL machinery around it
never became necessary. What made the problem tractable was indexing the cell classically,
conditioning the prior on the space group, and refining coordinates within their Wyckoff freedom.
See SUMMARY.md for the argument and its scope.
