# Registered blind calibration

This directory publishes the non-secret evidence from the 2026-07-29
QuantumBFS issue #124–#128 calibration of the TN problem generator.

The generator received only the source-snapshot date, ten literature
identifiers, target count, and four scoring dimensions. The operator record
states that it did not receive issue statements, links, target identifiers,
statement digests, literature grouping, repository access, or earlier
discussion, and that generation completed before the five statements were
supplied to a separate evaluator. These public files bind content and
arithmetic; they do not independently prove that chronology or generator
isolation because no external signed or timestamped blind-run receipt exists.

Files:

- `manifest.json`: registered sources, dimensions, statement digests, and
  thresholds;
- `blind-candidates.json`: the five public generator outputs;
- `weak-controls.json`: the three public weak controls used by separation;
- `report.json`: deterministic scores and hidden matching results.

The local `.gitignore` rejects `sealed/*` except a possible explanatory
`sealed/README.md`; the test suite also allowlists every committed calibration
file so nested statement payloads fail review.

The candidate file has SHA-256
`101bf35d22607b08ad0b160b893392e021bf7f8ac9d54aaefce91007f3b37be8`.
The semantic report digest is
`sha256:ee4acc0b035c0678d05997fa6d6a5991a99e708d42e30d4c5caea90fb519e85f`.

The report passed all registered campaign thresholds. Its `0.8` matching
score means that 4 of 5 literature groups met the per-target `0.75` threshold;
it is not a 5-of-5 semantic comparison with the sealed issue prose.

- meaningful-gap recovery: `1.0`;
- executable/non-gameable gate: `1.0`;
- strong/weak separation: `0.7876666666666667`;
- blind literature-group recovery: `0.8` (`4 of 5`).

The first three values are arithmetic over self-reported candidate fields.
Meaningful-gap recovery reads `meaningful_gap`; executable/non-gameable gate
reads `gate_executable && gate_attack_passed`; separation compares the
candidate-supplied novelty/publishability scores with `weak-controls.json`.
The evaluator checks schemas, digests, allowed literature, and arithmetic; it
does not independently verify those scientific self-reports.

An unregistered preflight found that ASCII token matching was
language-dependent. Before the registered run, matching was changed to exact
set-Jaccard over each candidate's required source-literature identifiers and
the per-target threshold was raised from `0.16` to `0.75`. The campaign-level
`0.8` threshold did not change.

Passing this calibration shows that the five outputs satisfied the registered
self-report and literature-grouping metrics. It does not count as a
human-accepted new challenge, a fresh numerical solve, or a publication. The
sealed issue statements are intentionally absent; their digests and the
post-run target-to-literature grouping remain public so the digest and score
chain can be replayed.
