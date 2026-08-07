# SCNet core experiment gate 6760394

- Date: 2026-07-29
- Slurm state: `FAILED`
- Exit code: `1:0`
- Elapsed: `00:00:13`
- Script: `slurm/test-experiment-core.sbatch`
- Raw logs: `/work/home/hesicheng5/quantum-harness-ch66/test-experiment-core-6760394.{out,err}`

The gate reported five failures and prevented every dependent pilot job from
running. Four failures shared one production defect: multiple independent data
fault mechanisms reached the same virtual boundary edge, while
`MatchingGraph.build` used PyMatching's `disallow` merge strategy. The exported
`d=3`, memory-X geometry confirms that each parallel group has one logical
parity, so the correct effective mechanism is the XOR of independent
probabilities. Commit `9460fe77c9d93b8149ef5fa015f2eb870da93e43`
uses PyMatching's independent merge and makes the standalone oracle combine the
same mechanisms from LLRs before exhaustive enumeration.

The fifth failure was a synchronization omission:
`research/database/benchmark_families.json` was absent on SCNet. The frozen file
was copied to the canonical project directory before the corrected gate was
submitted.

The new super-stabilizer quotient test itself passed in this failed job. The
corrected gate additionally checks all eight `d/T/basis` geometries and the
numeric LLR of every parallel boundary group. No pilot artifact was produced by
this attempt.
