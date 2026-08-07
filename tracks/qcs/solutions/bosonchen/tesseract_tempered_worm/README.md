# Tempered logical-sector sampler

This directory is a clean break from the final-v5/v6/v7 optimization line. It
does not patch Tesseract's A* loop. Instead, it uses one bounded Tesseract graph
trial only to construct a syndrome-valid seed, builds the logical homology of
the detector error model over GF(2), and compares logical sectors by their
finite-temperature free energy.

The target distribution at inverse temperature `beta=1` is

```text
P(x | Hx=s) proportional to exp(-sum_i w_i x_i).
```

This is a finite-temperature logical-class decoder, not a zero-temperature
single-error MLE search. Direct cross-sector replica exchange is retained as a
mixing diagnostic, but it is not the primary estimator: low-noise logical
sectors are separated by a large free-energy barrier, so direct counts suffer
from a zero-sample problem.

The primary phase-0 estimator uses a domain-wall construction. For a logical
kernel move `g`, two chains remain in the fixed sectors represented by `x` and
`x xor g`. Forward and reverse work samples are combined with the Bennett
acceptance-ratio equation to estimate

```text
Delta F_g = F(x xor g) - F(x).
```

This compares sectors without waiting for an exponentially rare logical
transition.

BAR is allowed to change the bounded Tesseract seed only when both directions
have measurable overlap (`overlap_score >= 0.01`) and at least 50 accepted
fixed-sector local proposals. When this reliability gate fails, the candidate
falls back to the seed unless an algebraic bridge explicitly produces a lower
energy syndrome-valid correction. This prevents a handful of correlated
samples from being reported as an entropic advantage.

The expensive comparison is activated only for a low-confidence seed or when
the minimum enumerated domain-wall energy is below 20. High-gap shots still
pay for complete logical-sector enumeration and screening, and that cost is
included in the per-shot candidate timing.

## Current scope

- General detector-error hypergraphs with at most 64 logical observables.
- A static library of exact `Hz=0` moves:
  - zero-detector errors;
  - pairs of errors with identical detector signatures;
  - randomly and logically seeded generalized Tanner-graph worms;
  - deterministic algebraic bridges obtained by closing logical DEM columns
    against a low-cost, zero-logical detector-syndrome basis.
- GF(2) rank checks and composition of bridge generators. A rank-12 BBC model
  therefore exposes all `2^12 - 1 = 4095` nontrivial logical sectors even when
  random worms expose none.
- Fixed-sector Bennett free-energy comparisons at `beta=1`.
- Replica exchange across a ladder from `beta=0` to `beta=1`, used as a
  falsification and mixing diagnostic.
- Mixing diagnostics: distinct logical sectors, top-two margin, indicator ESS,
  move/exchange acceptance, and temperature round trips.
- A full upstream Tesseract decode is run as an oracle in phase 0 only.

The phase-0 timing is exploratory. It excludes move-library preprocessing and
does not exclude warm-up. It must not be reported as challenge-certified
speedup.

## Phase-0 result

The original direct-count idea was falsified: representative BBC and TransCX
models produced no random logical worm moves, and the Surface chain showed no
`beta=1` logical transition. The algebraic bridge construction repaired sector
reachability, but easy low-noise shots currently show almost no accepted
within-sector local moves. Consequently their Bennett estimate reduces to the
domain-wall energy difference, with no resolved entropic correction.

The final three-case smoke test used ten paired shots per case:

| Case | Logical rank | Reachable nontrivial sectors | Online ratio | Baseline mismatches | Reliable BAR comparisons |
|---|---:|---:|---:|---:|---:|
| Surface d=11 | 1 | 1 | 12.39x | 0 | 0 |
| BBC NLR10 d=18 | 12 | 4095 | 10.80x | 0 | 0 |
| TransCX d=13 | 2 | 3 | 27.89x | 0 | 0 |

These ratios are exploratory. They exclude one-time preprocessing, use only ten
shots, and do not implement the issue's complete warm-up/back-to-back timing
gate. The archived TransCX run also used `pqlimit=200000`; the official long
preset is `pqlimit=1000000`. This made the archived baseline faster rather than
slower. `phase0.slurm` now selects the correct value per preset, but the table
above intentionally preserves the configuration of the archived JSON. Direct
replica exchange produced zero target-temperature logical
transitions and zero completed temperature round trips. BAR triggered on two
BBC shots but no comparison passed the overlap/local-acceptance gate.

The defensible conclusion is therefore:

```text
complete algebraic sector reachability
does not imply
finite-temperature dynamical mixing
```

The observed online savings come from the bounded syndrome-valid Tesseract seed
and algebraic screening, not from a demonstrated Monte Carlo free-energy
advantage. A next-generation method should introduce intermediate alchemical
coupling windows or another rejection-free bridge instead of directly crossing
the full logical domain wall.

## Remote layout

The source is staged as

```text
/home/chentao/tesseract_20x_full_bosonchen/baseline-audit-work/tempered_worm
```

against the clean upstream source at commit
`9c73ca0acb1a48fd1dc797f5f6deabbb5f5d3feb`.
