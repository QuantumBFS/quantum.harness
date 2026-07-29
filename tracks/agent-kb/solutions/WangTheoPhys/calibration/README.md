# Registered blind calibration

This directory publishes the non-secret evidence from the 2026-07-29
QuantumBFS issue #124–#128 calibration of the TN problem generator.

The generator received only the source-snapshot date, ten literature
identifiers, target count, and four scoring dimensions. It did not receive
issue statements, links, target identifiers, statement digests, matching
keys, or earlier discussion. Candidate generation completed before an
operator supplied the five sealed statements to a separate deterministic
evaluator.

Files:

- `manifest.json`: registered sources, dimensions, statement digests, and
  thresholds;
- `blind-candidates.json`: the five public generator outputs;
- `report.json`: deterministic scores and hidden matching results.

The candidate file has SHA-256
`101bf35d22607b08ad0b160b893392e021bf7f8ac9d54aaefce91007f3b37be8`.
The semantic report digest is
`sha256:ee4acc0b035c0678d05997fa6d6a5991a99e708d42e30d4c5caea90fb519e85f`.

The report passed all registered campaign thresholds:

- meaningful-gap recovery: `1.0`;
- executable/non-gameable gate: `1.0`;
- strong/weak separation: `0.7876666666666667`;
- hidden-target match: `0.8`.

An unregistered preflight found that ASCII token matching was
language-dependent. Before the registered run, matching was changed to exact
set-Jaccard over each candidate's required source-literature identifiers and
the per-target threshold was raised from `0.16` to `0.75`. The campaign-level
`0.8` threshold did not change.

Passing this calibration validates the generator protocol. It does not count
as a human-accepted new challenge, a fresh numerical solve, or a publication.
The sealed issue statements are intentionally absent; only their public
digests remain.
