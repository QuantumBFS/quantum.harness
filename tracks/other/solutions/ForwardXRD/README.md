## Team

| | |
|---|---|
| **Team name** | ForwardXRD |
| **Members** | rainforest580 |

## Challenge

| Row | |
|---|---|
| **Challenge** | Solve crystal structures directly from powder X-ray diffraction patterns by fine-tuning the pretrained CrystalFormer prior with RL against a pymatgen-simulated pattern-fit reward — going beyond gradient-descent and random-move Monte Carlo solvers, whose rough loss landscape strands them among look-alike wrong structures, by keeping every proposal on the manifold of chemically real crystals. |
| **Catalog issue** | `Addresses #68` — "Solving crystal structures from powder XRD with a generative prior", released by Lei Wang (王磊), IOP CAS. |
| **Track** | `other` — our call. The issue names no solution folder, and its `Method` field ("Generative modeling / inverse problems") maps to none of the seven tracks; follows the precedent of PR #132. |

## Progress

[**SUMMARY.md**](SUMMARY.md) — full write-up: what we built, how it differs from the approach the
issue proposes, and the measurements behind each choice.

**Result:** 7/7 benchmark structures recovered at rms ≤ 0.0015 (strict `ltol = stol = 0.05`),
spanning five crystal systems and 1–9 free internal coordinates, with the unit cell derived from
peak positions alone — no ground-truth cell anywhere in the pipeline.

**Headline finding:** the generative prior is essential; the variational RL machinery around it
never became necessary. What made the problem tractable was indexing the cell classically,
conditioning the prior on the space group, and refining coordinates within their Wyckoff freedom.
See SUMMARY.md §6 for the argument and its scope.
