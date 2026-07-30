# Initial independent-seed confirmation replacement: job 23003086

Status: failed during the pre-simulation contract gate; no simulation result or
scientific claim was produced.

Job `23003086` was the first replacement for `23002898`. It retained the frozen
candidate, seed family, 8 groups, 40 cells, 20,000 shots per cell, and 40-CPU
single-allocation execution design. It used orchestration commit
`b4d3439d9c8b1da43aa09175bbad66aa3d167f2a`, archive SHA-256
`d6d93501e085c14781c4cac2abf1ea8b5a64d2fa40953bc74b6cc4a734e9d094`,
and snapshot `bundle-confirm-b4d3439` with manifest SHA-256
`eb3a97212e60a018e8a37de7ecafd89a97659d6cd6cea080eb67184002a3d059`.

Slurm reported `FAILED`, exit `1:0`, after 9 seconds. The contract run produced
19 passes and 4 failures. All four failures came from the confirmation test
fixture deriving `confirmation_families.json` as a sibling of
`Q66_INSTANCE_FILE`: the generated instance database was pinned at the live
project database path, while the family file existed only in the immutable
snapshot. Negative controls, matrix generation, simulation, and exact replay
never started.

The next replacement must place the already frozen instance database directly
inside a new immutable orchestration snapshot before generating and verifying
its checksum manifest. This does not change the database bytes, candidate,
model, seed, matrix, or stopping rule.
