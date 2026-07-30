# Issue #71: train-only shared BDD route

This directory is an independent experiment arm.  It consumes only an official
`train.csv`; revealed arithmetic semantics are used only after fitting for an
exhaustive audit.

For each output bit, the learner builds a prefix acceptor in a candidate
variable order and merges compatible wildcard transition pairs bottom-up.
All output roots share one canonical reduced BDD manager.  The compiler maps
BDD MUX nodes to the challenge gate basis with free phases and global gate CSE.

Order selection uses a seed-42 training/validation split:

1. blocked input order,
2. LSB-interleaved order,
3. MSB-interleaved order,
4. bounded seed-42 sifting,
5. adjacent-swap hill climbing.

The independent auditor reparses every emitted netlist, checks gate ordering and
arity, and exhaustively compares all inputs against the organizer-revealed
function.  It shares no netlist parser or simulator with the learner.
