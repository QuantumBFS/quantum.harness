# Challenge 66 Post-Deadline Supplement

Status: computation closed at user request on `2026-07-30 18:19:56 CST`.
This supplement records evidence
produced after the frozen `2026-07-30 15:27 CST` deadline. It does not change
the deadline disposition `inconclusive_at_deadline`, authorize a headline
claim, or spend the sealed holdout budget.

## Discovery Phase 3

Post-deadline replacement analysis job `23023314` completed on xh5 in
59 minutes 43 seconds with exit `0:0`. Every artifact digest was independently
recomputed and matched `analysis-checksums.sha256`.

- 2,240 cells and 1,960 policy-versus-none comparisons;
- 179,200,000 cumulative cell-shots;
- 81 cells reached the registered failure target and 2,159 continue;
- 4 physical groups reached the lockstep target and 276 continue;
- provisional classifications: 502 `helpful` and 1,458
  `no_significant_difference`;
- headline claims remain unauthorized;
- analysis-manifest SHA-256:
  `b931304d23102e52657d4282c9ed189dddf245b6a8da2d57bdff39eb6ba41fbd`;
- continuation-plan SHA-256:
  `5cea54fa7dbb8a881d9e90015bf1433bc2aef7f5f6d82f7459e9c17331700fc0`;
- continuation-bundle summary SHA-256:
  `35d443423ade41e9beee2351cf364d1f24ef3bfb373dd8b2cf85d18b64bc05ee`.

The accepted artifact root is
`results/discovery/analysis/phase-3/23023314`. Phase 4 array `23025296`
contained 11 large registered bundles for 276 groups and 2,208 cells. Three
array elements completed before closeout; the remaining elements and dependent
analysis job `23027672` were cancelled at `2026-07-30 18:19:56 CST`. Because
the array was incomplete and no dependent analysis or manifest was published,
all partial Phase-4 output is excluded.

## Independent-Seed Confirmation

Post-deadline job `23023521` failed closed after its contract tests because a
non-exact transferred candidate directory did not match the frozen candidate
tree. A read-only hash audit identified
`reference-0a73ba3-scnet-exact` as the unique transferred root matching frozen
tree SHA-256
`829ade4b3ab7408c9151a6a06222e6779df6c65096b8d2e2d947e26238140482`.
Replacement job `23023740` used that exact root on xh5 and was cancelled at
closeout after 2 hours 28 minutes 42 seconds. No later artifact was accepted;
Phase 5 remains the highest verified confirmation artifact.

## Closeout

Slurm accounting records `CANCELLED by 49799` for confirmation resume
`23023740`, Discovery Phase-4 array `23025296`, and dependent analysis
`23027672`. The queue was empty for all three job IDs after cancellation. No
new phase, cost-sensitivity run, or holdout query is authorized after this
closeout.

Holdout query budget: `0 / 1`, unspent.
