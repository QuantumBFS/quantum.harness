# Invalid live-tree development-validator run: jobs 6760460-6760462

Matrix generation job `6760460` completed successfully. The reference array
`6760461` was then invalidated by a concurrent source synchronization while
its cells were reading the live project directory. Cell 4 detected the
change after its second candidate run and rejected with
`candidate-source-tree-mutated`. This is the intended integrity-guard
behavior, not a simulator, replay, or seccomp failure.

At collection time six cells had completed successfully, cell 4 had failed,
and another cell was running. The remaining array work and dependent score
job `6760462` were cancelled deliberately to avoid spending GPU allocation on
an unscorable mixed-source run. No score or scientific claim is admissible
from this chain.

The replacement workflow stages code and the generated matrix into a unique,
checksummed snapshot. Both the array runner and score aggregator import from
that snapshot, so later project synchronization cannot alter a running
validator.
