# Occam's Circuit optimization log

## Objective and acceptance rule

Optimize the four exact Boolean netlists under the official cost model:

- Allowed fanin-2 gates: `AND OR XOR NAND NOR XNOR`, each costs one.
- Inversion on any operand or output is free.
- A candidate replaces the current best only after:
  1. the generated text netlist parses successfully;
  2. every input in the complete domain matches the arithmetic formula;
  3. every supplied training row matches exactly.

Approximate circuits are kept only as research notes and never replace an exact
best circuit.

## Baseline — 2026-07-27

| Instance | Function | Gates | Exhaustive verification | Training verification |
|---|---|---:|---:|---:|
| mystery-A | `x + y` | 37 | 65,536 / 65,536 | 2,000 / 2,000 |
| mystery-B | `abs(x - y)` | 53 | 16,384 / 16,384 | 1,500 / 1,500 |
| mystery-C | `x * y` | 168 | 4,096 / 4,096 | 1,200 / 1,200 |
| mystery-D | `x**2 + y**2` | 127 | 1,024 / 1,024 | 400 / 400 |

Baseline architectures:

- A: ripple-carry adder, one half adder followed by seven full adders.
- B: ripple-borrow subtraction followed by conditional two's-complement.
- C: 36 partial products followed by column-wise half/full-adder reduction.
- D: square-specific diagonal/off-diagonal terms followed by column reduction.

## Initial optimization hypotheses

1. **Free-polarity full adders.** Because inversion is free and XOR/XNOR have
   equal cost, propagate inverted carry signals between adjacent cells and seek
   four-gate full-adder variants in context, rather than treating every full
   adder as an isolated five-gate macro.
2. **Global multi-output synthesis.** Shared subexpressions across output cones
   may beat independent bit synthesis. Any external synthesis flow must be
   mapped to the exact six-gate library and reverified after mapping.
3. **Architecture search.** Compare ripple/borrow, carry-save compressor,
   Dadda/Wallace, Booth, small-block multiplication, and direct truth-table
   synthesis. At 5–8 bits, asymptotically superior architectures may lose to
   simpler networks because recoding overhead dominates.
4. **Exact local rewriting.** Exhaustively synthesize small windows with fixed
   boundary signals, then splice smaller equivalent windows into the global
   circuit. Whole-circuit exact synthesis is likely too large; 3–6 gate cones
   are tractable.
5. **BDD/MPS diagnostics.** Variable ordering and low bond dimension can expose
   reusable state (carry/borrow) and guide decomposition, but a compact
   BDD/MPS does not automatically minimize the target two-input gate count.

## Public-result and tool audit — 2026-07-27

- GitHub issue/PR search found one other public registration, PR
  `QuantumBFS/quantum.harness#181` (`quantumevolve`), but its current qcs
  solution contains only a registration README and no circuits or gate counts.
- No public leaderboard-quality A–D netlists were found. The packaged example
  confirms only A = 37 gates.
- The local machine initially had no Yosys, Berkeley ABC, Espresso, Z3, or
  Verilog simulator. A workspace-local Berkeley ABC build was selected because
  it supports multi-output Boolean optimization and custom standard-cell
  libraries without modifying the system environment.
- A's 37-gate structure equals the direct `2 + 7*5 = 37` half/full-adder count.
  It is a strong baseline and likely has much less easy slack than B/C/D,
  although optimality has not been proven.

## Iteration 1 — custom-library ABC remapping

ABC was run with the exact challenge library (six two-input gates, unit area;
inverter area zero). Mapped BLIF was converted back to challenge syntax by
propagating inverter aliases, then independently parsed and exhaustively tested.

| Instance | Baseline | ABC candidate | Result |
|---|---:|---:|---|
| A | 37 | 37 | Exact; tie, not promoted |
| B | 53 | **51** | Exact; promoted |
| C | 168 | 174 | Exact but worse; rejected |
| D | 127 | 132 | Exact but worse; rejected |

B verification after promotion:

- Full domain: 16,384 / 16,384 exact.
- Training data: 1,500 / 1,500 exact.

Interpretation: in the baseline conditional two's-complement stage, the least
significant output performs two XORs that algebraically cancel. ABC removes
those two gates. This is a genuine two-gate improvement, not merely a polarity
remapping.

Structural count audit:

- C = 36 partial-product ANDs + 24 full adders × 5 gates + 6 half adders ×
  2 gates = 168.
- D = 20 off-diagonal square-term ANDs + 19 full adders × 5 gates + 6 half
  adders × 2 gates = 127.

Thus C and D already saturate the isolated-module count for these weighted-bit
representations. Further improvement must jointly restructure partial-product
generation and compression, use cheaper multi-cell identities, or start from a
different functional decomposition.

## Iteration 2 — broader ABC script search

Seven classic AIG scripts (`resyn`, `resyn2`, `resyn2a`, `resyn3`,
`compress2`, `resyn2rs`, `compress2rs`) were mapped and exhaustively tested.

- B: every script returned 51 gates.
- C: candidates ranged from 168 to 177; best was a 168-gate tie.
- D: old ABC `resyn3` improved 127 → 126 gates; exact and promoted.

Direct synthesis from complete truth-table PLAs was also tested. For C it
produced a 6,176-gate mapping. This route was rejected: collapsing arithmetic
structure into flat minterms destroys the useful carry/partial-product
factorization before synthesis can rediscover it.

## Iteration 3 — current OSS CAD Suite and iterative topology evolution

Installed the official `oss-cad-suite-windows-x64-20260727` bundle locally
under `solution71/tools`:

- Yosys `0.67+94`;
- Berkeley ABC compiled 2026-07-25.

The older source build attempt using the locally available 32-bit Strawberry
GCC failed because ABC requires 64-bit pointer-sized integer types. This is an
infrastructure failure, not a circuit result; the official x64 build replaced
it.

RTL synthesis starting from `+`, `*`, and conditional subtraction was tested.
It did not beat the hand-structured baselines:

- A: 38 gates;
- B: 74 gates;
- C: 178 gates;
- D: 206 gates.

All were rejected. The result supports retaining arithmetic structure and
optimizing locally rather than relying on generic RTL bit blasting.

On D, repeated topology-changing passes were allowed to promote equal-size
circuits as new search starting points. Every generation was exhaustively
tested. The successful trajectory was:

`127 → 126 → 125 → 124 → 123`

The first additional step came from current `resyn3`; the next steps alternated
`resyn3` and SAT-guided `drwsat2`. Subsequent perturbations with `rwsat`,
`dc2`, `compress`, `resyn2`, and `resyn2a` stabilized at 123 or became worse.

## Iteration 4 — SAT don't-care window resynthesis

The most effective flow so far is:

1. retain the current arithmetic-derived logic network;
2. run high-effort `mfs2` with SAT-derived local don't-cares;
3. enlarge the transitive-fanout window;
4. remap with the exact challenge gate library;
5. propagate free inversions;
6. exhaustively test the emitted challenge netlist.

Results:

- C: `168 → 167` with the initial `mfs2` flow, then `167 → 166` with a
  six-level, high-conflict-budget window.
- D: `123 → 122` with the same six-level window.
- A remained 37; B remained 51.

Ten repeated six-level generations and an eight-level follow-up were tested for
both C and D. They stabilized at 166 and 122. High-effort `mfs` edge swapping
also tied these results.

## Current exact best — 2026-07-27

| Instance | Baseline | Current best | Gates saved | Exhaustive verification |
|---|---:|---:|---:|---:|
| A | 37 | **37** | 0 | 65,536 / 65,536 |
| B | 53 | **51** | 2 | 16,384 / 16,384 |
| C | 168 | **166** | 2 | 4,096 / 4,096 |
| D | 127 | **122** | 5 | 1,024 / 1,024 |

Every current best also matches every supplied training row exactly.

## High-value directions not yet exhausted

1. **Architecture-diverse C seeds.** Generate radix-4 Booth, 3×3 block, and
   Karatsuba-style 6×6 multipliers, then apply the same SAT-window flow. They may
   start larger but expose different subfunctions that optimize below 166.
2. **Exact synthesis of cut windows.** Extract 4–8 input / 2–4 output cones and
   prove the minimum number of challenge gates with SAT, then splice certified
   replacements. `mfs2` is heuristic and does not prove local optimality.
3. **Gate-library-aware evolutionary search.** Mutate valid DAGs while using
   bit-parallel truth tables as the fitness oracle. Exactness remains mandatory;
   equal-size structural diversity is valuable.
4. **Tensor/BDD-guided cuts.** Use small communication rank across variable
   partitions to identify compact carry-state boundaries. This is more useful
   for choosing exact-synthesis windows than for directly emitting gates.
5. **Polarity-state dynamic programming.** Optimize each arithmetic cell with
   both output polarities as states, then globally choose polarities because
   inversion is free. Generic mapping partially does this, but an
   arithmetic-aware DP may preserve compressor semantics better.

## Iteration 5 — topology-diverse multiplier islands

Generated 100 exact 6×6 multiplier seeds by randomizing:

- the ordering of the 36 partial products;
- which three bits each full adder consumes;
- which selected bit occupies the carry-in role;
- the order in which newly generated sum/carry bits re-enter a column.

All 100 source seeds had 168 gates and passed 4,096/4,096 exhaustive tests
before optimization.

First-stage six-level SAT-window results:

- 98 seeds completed; seeds 028 and 056 triggered an internal ABC assertion and
  were discarded without reusing stale output.
- Distribution: 17 at 166 gates, 21 at 167, 59 at 168 or worse.
- No candidate beat the current 166-gate C.

All 17 distinct 166-gate candidates then received an eight-level SAT window
plus `drwsat2/resyn3`, followed by eight-generation island evolution. Every
candidate remained exact; none fell below 166.

Conclusion: random compressor ordering changes optimization quality, but 166 is
a strong fixed point across the sampled conventional partial-product family.
The next C architecture search should change the partial products themselves
(Booth/block/Karatsuba), not only their reduction order.

## Iteration 6 — topology-diverse square-sum islands

Generated 200 exact 5-bit `x²+y²` seeds by randomizing weighted-term and
compressor ordering. Every 127-gate source seed passed 1,024/1,024 exhaustive
tests before synthesis.

Seeds 1–100:

- 97 completed; three ABC internal failures (033, 092, 093) were discarded.
- First-stage distribution ranged from 120 to 126 gates.
- Seed 003 reached 120 gates.
- Alternating `mfs2` and `rwsat` reduced it to 119.
- Multi-island evolution was essential: another 120-gate topology, seed 012,
  followed a different path `120 → 118 → 117`.

Seeds 101–200:

- 99 completed; seed 183 failed inside ABC and was discarded.
- One seed reached 119 directly, four reached 120, and seven reached 121.
- Further island evolution reached 118 on one island but did not beat 117.

The 117-gate D network was promoted only after complete-domain and training-set
verification. Twenty-four further alternating generations stabilized at 117.

## Current exact best — later 2026-07-27 checkpoint

| Instance | Original baseline | Current best | Gates saved | Exhaustive verification |
|---|---:|---:|---:|---:|
| A | 37 | **37** | 0 | 65,536 / 65,536 |
| B | 53 | **51** | 2 | 16,384 / 16,384 |
| C | 168 | **166** | 2 | 4,096 / 4,096 |
| D | 127 | **117** | 10 | 1,024 / 1,024 |

The official training sets remain exact: A 2,000/2,000, B 1,500/1,500,
C 1,200/1,200, D 400/400.

## Tool behavior worth retaining

- `&satsyn` in this ABC build advertises `-O` but rejects both `-O` and `-o`;
  without that option it reported a failed transformation. It produced no
  accepted optimization.
- Flat truth-table synthesis and generic arithmetic RTL synthesis are much
  worse than arithmetic-structured seeds.
- Equal-gate topology promotion is useful, but only across genuinely different
  islands. Repeating deterministic passes on one stabilized topology has no
  effect.
- Every ABC invocation in population searches must use a unique output path and
  check its exit code. Otherwise an internal assertion could accidentally leave
  a stale candidate that appears to belong to the next seed.

## Iteration 7 — full-adder symmetry in A and B

### B: absolute difference

A full subtractor can be represented as a full adder on
`(~x_i, y_i, borrow_i)`:

- the full-adder carry is the next borrow;
- the full-adder sum is the complement of the difference bit, available for
  free under the challenge polarity model.

Because a full adder is symmetric in its three inputs, 50 structurally
different 51-gate absolute-difference seeds were generated by permuting the
propagate pair at each bit. Every source seed passed all 16,384 inputs.

After an eight-level SAT window plus `rwsat/resyn3`, all 50 seeds independently
converged to **49 gates**. Seed 001 was promoted and passed:

- full domain: 16,384 / 16,384;
- training: 1,500 / 1,500.

Twenty-four further alternating generations stabilized at 49.

### A: addition

The same full-adder input-role randomization generated 50 distinct 37-gate
8-bit adders. Every source and every optimized candidate passed all 65,536
inputs. All 50 optimized candidates remained at **37 gates**.

This is not a formal global optimality proof, but it is strong evidence that
37 is a robust optimum within a broad ripple/full-adder topology family.

## Current exact best — full checkpoint

| Instance | Original baseline | Current best | Gates saved | Exhaustive verification |
|---|---:|---:|---:|---:|
| A | 37 | **37** | 0 | 65,536 / 65,536 |
| B | 53 | **49** | 4 | 16,384 / 16,384 |
| C | 168 | **166** | 2 | 4,096 / 4,096 |
| D | 127 | **117** | 10 | 1,024 / 1,024 |

All four current files also match every supplied training row exactly.

## Iteration 8 - `mfs3` / `mfse` local don't-care resynthesis

The latest OSS CAD Suite build was tested directly on the current 166-gate C
and 117-gate D networks.

### `mfs3`

On C, `mfs3` crashed with Windows access-violation status `-1073741819`.
This happened for the default command and for each isolated option family
tested: area mode, delay/area effort, simulation, large K/window/round limits,
and multi-input/zero-cost mode. No output BLIF was produced, so no result was
accepted. This confirms that checking both the process exit status and the
existence of a unique output file is necessary; reusing an old output here
would create a false optimization result.

### `mfse`

`mfse` requires an SOP logic network (`logic`) rather than the AIG produced by
`strash`. After adding this conversion, five C variants were tested:

- default;
- Ashenhurst mode;
- decomposition mode;
- a 6-level, 1,000-node window;
- a 10-level, 5,000-node high-effort window.

All five mapped to 166 gates and independently passed 4,096/4,096 exhaustive
cases plus 1,200/1,200 training rows. The same four representative variants on
D all mapped to 117 gates and passed 1,024/1,024 exhaustive cases plus
400/400 training rows.

Conclusion: `mfse` is stable and exact here, but these two current networks are
fixed points for all tested window/decomposition settings. `mfs3` is unusable
in this Windows build on C. No current best file was changed.

## Iteration 9 - architecture changes, exact cones, and stochastic synthesis

### Multiplier architecture changes

The Yosys 0.67 radix-4 `booth` pass was applied explicitly to the 6x6
multiplier, followed by the same ABC area mapping and high-effort `mfs2` flow
used for the current best. It produced 222 counted gates. A 3x3-split
Karatsuba implementation produced 239 gates, and applying Booth encoding to
Karatsuba's internal 4x4 product produced 262 gates. All three candidates
passed 4,096/4,096 exhaustive cases and 1,200/1,200 training rows, but were
rejected because they are much larger than 166.

This is a useful small-width result: the reduction from 36 simple partial
products does not repay Booth recoding/control or Karatsuba add/subtract
overhead at six bits under this challenge's equal two-input-gate cost.

### ABC deep synthesis library

The official ABC six-input LMS library was located at Berkeley and downloaded
as `tools/rec6Lib_final_filtered3_recanon.aig`:

- size: 37,989,867 bytes;
- SHA-256:
  `814CEF3831552A0DFAA7F2389A306EF43577A4E13F166ABEE2341DB1AA24E007`.

After `rec_start3`, `&deepsyn` ran successfully. A bounded ten-second run
searched many depth/AIG Pareto points, but the imported result mapped to 446
challenge gates. The algorithm optimizes AIG depth/node count rather than the
free-inverter XOR/AND/OR cell metric, so this result was rejected. One earlier
long smoke run exceeded its external wrapper timeout; its exact process was
terminated and no output was accepted.

### Exact two-input-gate synthesis

ABC's `twoexact` is directly aligned with this gate metric: AND/XOR plus free
input/output complementation spans the six allowed two-input gates. For the
standalone six-input function giving product bit 2, exact synthesis found an
8-gate implementation; the conventional standalone cone uses 9 gates.

This does not reduce the full multiplier: the conventional cone's intermediate
nodes also generate carries used by higher product bits, while an independent
8-gate replacement would duplicate that shared work.

`enumerate_mffcs.py` was added to enumerate safely replaceable maximal
fanout-free cones and emit their exact truth tables. Results on the current
networks:

- C has no fanout-free cone of at least four gates with at most eight boundary
  variables;
- D has one four-gate/five-boundary cone;
- B has one four-gate/five-boundary cone;
- `twoexact` proved that neither four-gate cone has a three-gate realization;
- every listed three-gate cone has four essential boundary variables, so it
  cannot be implemented by only two fanin-2 gates.

Thus every small independently replaceable cone inspected is locally optimal.
Future improvement must restructure shared multi-output logic, not merely
replace an isolated small cone.

### Orchestration and RRR stochastic resynthesis

ABC `orchestrate` at K=8 and K=12 left C at 166 gates. K=16 triggered an
internal assertion because the implementation requires `K < 16`; no output was
accepted. Four `&rrr` modes produced exact C candidates between 171 and 174
gates.

On D, orchestration produced 119 and 120 gates. Four RRR modes produced
121, 123, 122, and one structurally different 117-gate candidate. Every
candidate was exhaustively verified. Further alternating SAT/orchestration
evolution of the 117-gate island produced 118-120 gates and did not improve
the current best.

### Buffer-enabled exact-polarity library

The original zero-cost library omitted a buffer, causing ABC to warn that
parts of supergate mapping were disabled. Both a 0.01-cost inverter/buffer
library and a new zero-cost inverter/buffer library were tested on all four
current networks. The converter folded all inverter/buffer cells before
counting.

Both libraries reproduced exactly A=37, B=49, C=166, D=117. Every candidate
passed its full domain and training set. The buffer removes the mapper warning
but does not change the best gate counts.

## Iteration 10 - XAG extraction, semantic resubstitution, and eSLIM

Because free complementation collapses the six legal gate names into AND-family
and XOR-family nodes, several XAG-oriented flows were tested.

### XOR extraction

ABC `&extract -K 3` produced a structurally different C candidate with 166
gates and depth 56, versus depth 58 for the current file. Larger K, AND
extraction, DSD collapsing, DSD balancing, and SOP balancing produced 167 to
5,142 gates. Reapplying global or 12-level high-effort `mfs2` to both the
current topology and the new 166-gate XOR-extracted island left all candidates
at 166.

On A, XOR extraction tied 37. On B and D it increased the counts to 55-63 and
122-131 respectively. Every written candidate was exhaustively verified.

### Full-domain semantic resubstitution

`semantic_resub.py` was added as an implementation-independent check against
missed ABC resubstitutions. It uses complete truth tables and searches all
non-descendant wires for:

- a one-gate replacement of every multi-gate MFFC;
- a two-gate replacement whose final gate is XOR/XNOR;
- a two-gate replacement whose final gate is from the AND family with
  arbitrary free input/output polarity;
- for four-gate MFFCs, two independent one-gate expressions followed by XOR.

No improving replacement was found in A, B, C, or D. This strengthens the
local-optimality evidence without relying on ABC's own SAT/window machinery.

### Multi-output compressor check

Exact synthesis was used to investigate replacing full-adder chains with
binary population-count blocks. A four-input, three-output binary population
count has a 9-gate realization; attempts at 7 or 8 gates found no solution
within the configured exact-synthesis conflict budget. This is not better than
the 7-gate redundant compression obtained from one full adder plus one half
adder, explaining why a conventional carry-save tree remains preferable under
this metric.

### eSLIM exact local synthesis

The new `&eslim` command combines exact synthesis with SAT-based local
improvement and can explicitly allow XOR gates. On C:

- a 20-second, six-gate-window run reduced its internal AIG from 229 to 206
  nodes, but remapped to 168 challenge gates;
- preprocessing with XOR extraction, followed by the same eSLIM setup, mapped
  to 177 gates.

Both candidates passed 4,096/4,096 exhaustive inputs and 1,200/1,200 training
rows. They were rejected because their internal AIG objective does not track
the final free-inverter XAG cell count closely enough.

### Public-state check

The challenge issue still has no result comments. Public PR #181 contains only
the other team's registration/readme for issue #71 and no circuit files or
gate counts. There is therefore still no public score against which to compare
37/49/166/117.

## Stopping checkpoint requested by the user

Final retained files:

| Instance | Gates | Exhaustive | Training | Dead / constant / duplicate-complement |
|---|---:|---:|---:|---:|
| A | **37** | 65,536 / 65,536 | 2,000 / 2,000 | 0 / 0 / 0 |
| B | **49** | 16,384 / 16,384 | 1,500 / 1,500 | 0 / 0 / 0 |
| C | **166** | 4,096 / 4,096 | 1,200 / 1,200 | 0 / 0 / 0 |
| D | **117** | 1,024 / 1,024 | 400 / 400 | 0 / 0 / 0 |

Optimization stopped after this completed and verified round at the user's
request. No eSLIM or equal-count island candidate replaced a retained file.

## Iteration 11 - Tensor-network contraction and graph windows

Optimization was resumed specifically to test tensor-network ideas rather
than using that phrase only as an analogy. Three increasingly general routes
were implemented.

### Exact tensor train over the complete multiplier

`tensor_train_synth.py` represents all twelve multiplier output functions as
a shared complemented-edge deterministic tensor train, equivalently a
multi-output reduced ordered decision diagram. Eighty random variable orders
plus adjacent-swap hill climbing evaluated 717 orders.

The best order was the complete reverse input order. It required 1,155 tensor
states and compiled to 3,093 legal challenge gates. A safe ABC rewrite reduced
this to 2,547 gates. Both versions were exact on all 4,096 multiplier inputs,
but were rejected because they are far larger than 166 gates. This is direct
evidence that one-variable matrix-product cuts have excessive bond dimension
for integer multiplication and that selector-tensor compilation is a poor
match for the gate-count objective.

### Contiguous multi-output contraction

`tensor_window_search.py` contracts each local circuit interval into one exact
Boolean boundary tensor and jointly synthesizes all boundary outputs.

For C, gate intervals of size four through ten produced 196 unique eligible
tensors. All tested windows with at most five boundary inputs, all size-five
and size-six representatives with six inputs, all tested seven-gate
representatives, and nearly all tested eight-gate representatives synthesized
to exactly their original gate counts. The hardest nine- and ten-gate tensors
timed out. No improving replacement was found.

This result is stronger than the earlier single-output MFFC check because
carry and sum outputs were optimized jointly.

### Non-contiguous graph tensor regions

`tensor_graph_windows.py` grows connected regions in the circuit hypergraph,
rejects regions that leave and later re-enter, contracts the remaining region,
and deduplicates candidates by their complete multi-output boundary tensor.

For C, 20,000 samples produced 1,647 eligible regions and 1,138 unique
tensors with at most five inputs and four outputs. Thirteen non-contiguous
four-input, seven-gate regions were each proved to require seven gates. The
best four-input, eight-gate region was proved to require eight gates. Larger
regions exhausted the short SAT budgets. C therefore remains at 166 gates.

For D, the same method found a ten-gate region with four inputs and three
outputs that has a nine-gate realization. After embedding it and rebuilding
the tensor graph, an eight-gate subregion had a seven-gate realization.
Together these two certified replacements reduced D from 117 to 115 gates.

The bundled ABC revision has an export defect for asymmetric two-input gates:
its SAT solution is correct, but the default SOP BLIF reverses the two local
truth-table axes. The first attempted embedding was rejected immediately by
global verification. Swapping the two fanins of each asymmetric exported node
restored the intended tensor. Both retained replacements were checked first
on all sixteen boundary states and then over the full D input domain.

### Retained checkpoint

- A: 37 gates; 65,536 of 65,536 exhaustive inputs and 2,000 of 2,000 training
  rows correct.
- B: 49 gates; 16,384 of 16,384 exhaustive inputs and 1,500 of 1,500 training
  rows correct.
- C: 166 gates; 4,096 of 4,096 exhaustive inputs and 1,200 of 1,200 training
  rows correct.
- D: 115 gates; 1,024 of 1,024 exhaustive inputs and 400 of 400 training rows
  correct.

The final structural audit reports no dead gates, constants, or
duplicate/complement groups in any retained file.

## Iteration 12 - Large joint tensor rewriting

This iteration moved beyond local seven- and eight-gate windows and targeted
multi-diagonal multiplier regions containing up to 24 gates.

### Low-rank functional decomposition

`tensor_rank_decompose.py` was added to perform exact Boolean tensor
factorization. For a boundary function F over input groups X and Y, it merges
all X assignments that induce the same multi-output function of Y. The result
is an exact decomposition into a front tensor H of X and a back tensor G of H
and Y. Only decompositions with at most three interface bits and at most six
inputs per factor were retained.

Hundreds of exact low-rank factor pairs were found. However, low interface
rank did not translate directly into low challenge-gate count. The best
17-gate region split into a four-gate front factor and a back factor that ABC
initially mapped to sixteen gates. Relation synthesis reduced the back factor
to thirteen gates, making the factorized construction tie the original at
seventeen gates. Fixed-size exact synthesis attempts targeting twelve or
thirteen back-factor gates timed out after fifty seconds, so no unverified
factorization was embedded.

`factor_abc_synth.py` was added for this two-stage heuristic-plus-exact
workflow.

### Whole-region relation synthesis

`extract_tensor_region.py` was added to turn any topologically convex graph
region into a standalone boundary netlist. This lets eSLIM choose internal
interface functions instead of fixing the low-rank encoding in advance.

A 22-gate low-product region was selected with seven boundary inputs and five
boundary outputs. It spans several multiplication diagonals and has boundary
inputs x1, x2, x3, x4, x7, x8, and x9. Its boundary outputs are w4, w11, w19,
w25, and w31.

- Ordinary resynthesis mapped the region to 25 gates.
- Six-gate relation windows mapped it back to 22 gates.
- Seven-gate relation windows found a 21-gate realization.
- The candidate matched all 128 boundary assignments.
- After embedding, C matched all 4,096 complete-domain inputs and all 1,200
  training rows.

This reduced C from 166 to 165 gates.

After rebuilding the graph, further large regions were tested:

- a 19-gate middle region tied at 19;
- a 20-gate high region mapped to 22;
- a 24-gate high-product region tied at 24;
- a fresh exact graph-window pass proved the tested six-, seven-, and
  eight-gate regions locally optimal.

### Retained checkpoint

- A: 37 gates.
- B: 49 gates.
- C: 165 gates.
- D: 115 gates.
- Total: 366 gates, reduced from the original total of 385.

All four files pass their complete input domains and training sets. The final
structural audit reports no dead gates, constants, or duplicate/complement
groups.

## Iteration 13 - Parallel topology portfolio and joint-region search

This iteration deliberately used several independent search lines so that the
current winner would not become the only optimization parent.

### Current C winner, multi-region and multi-seed search

The retained 165-gate multiplier was sampled 7,000 times. This produced 120
eligible convex regions and 117 distinct boundary tensors. Nine representative
regions containing 18 through 28 gates were selected across the low, middle,
high, and top parts of the multiplier.

Twenty-seven short eSLIM runs covered relation sizes six, seven, and eight.
Three of the smallest-boundary regions also received 120-second long runs.
Those relation runs timed out before producing mapped candidates. Thirty-six
ordinary ABC-flow results were obtained: five regions tied their original gate
counts and four became larger. No local reduction was found.

The full record is in
`abc-work/parallel/c165_multiseed/REPORT.md`.

### Alternative C mother topologies

A portfolio audit parsed 331 historical C files. Of these, 305 were correct
within the requested gate bound, representing 112 different internal semantic
fingerprints. In particular, 29 distinct verified 166-gate topologies were
identified.

Three structurally different 166-gate mothers were selected at depths 31, 36,
and 58. Across them, 1,535 large convex regions were enumerated, yielding
1,491 distinct boundary tensors. Six representative joint regions were sent
to relation synthesis. The best completed result tied its source region.
No mother yielded the two-gate local reduction needed to beat the retained
165-gate circuit.

This negative result is important: the search explicitly tested whether the
previous optimization path had hidden easier regions in older parents. It did
not find such a region in this sample, but the verified topology archive is
retained for future non-monotone search.

The full record is in
`abc-work/parallel/c_alt_topologies/REPORT.md`.

### B and D joint tensor search

The B and D line performed 72,000 graph samples and found 466 eligible large
regions, with 465 unique tensors within individual runs. It tested regions of
18 through 28 gates with at most eight boundary inputs and six boundary
outputs.

For B, both the retained 49-gate circuit and a distinct depth-16, 49-gate
mother were tested. Completed replacements either tied or increased the
source region, so B remains at 49 gates.

For D, a 26-gate region of the 115-gate parent had seven boundary inputs and
five boundary outputs. eSLIM relation size six with seed 73 produced a
25-gate realization. The replacement matched all 128 boundary assignments.
After embedding, the complete circuit matched all 1,024 input assignments and
all 400 training rows. A second rewrite pass on the new 114-gate circuit tied
at best, so the verified 114-gate candidate was promoted.

The full record is in
`abc-work/parallel/bd_tensor/REPORT.md`.

### Retained checkpoint

- A: 37 gates, depth 15.
- B: 49 gates, depth 21.
- C: 165 gates, depth 59.
- D: 114 gates, depth 28.
- Total: 365 gates, reduced from the original total of 385.

All four retained files pass their complete input domains and training sets.
The structural audit reports no dead gates, constants, or
duplicate/complement groups.

## Iteration 14 - Sergeev 158 reproduction and constrained-state reduction

The 158-gate upper bound from Sergeev's multiplier construction was rebuilt
directly rather than inferred from a synthesized netlist. The generated
six-bit multiplier contains:

- 36 partial-product gates;
- 6 half adders;
- 3 ordinary three-input full adders;
- 1 encoded-input Stockmeyer full adder;
- 10 modified double full adders;
- 11 XOR gates that create encoded bit pairs.

The component accounting is 36 + 12 + 15 + 4 + 80 + 11 = 158 gates.
The construction is reproducible with `build_sergeev_multiplier.py`, and its
unchanged output is retained at
`abc-work/sergeev-158/mystery-C.txt`.

The direct 158-gate network passed all 4,096 possible inputs and all 1,200
training rows.

### Global reachable-state simplification

A semantic resubstitution pass evaluated every internal wire over the full
12-input domain. It found that the four-gate maximal fanout-free cone driving
the most significant product bit can be replaced by two gates. The original
cone is required if its boundary signals are treated as independent, but
those boundary assignments are not all reachable from multiplier inputs.

On the reachable states, the final output is

`g36 AND (g29 OR g154)`.

The OR is represented by one NAND with two complemented inputs, followed by
one AND. Removing the old four-gate cone and adding these two gates yields
156 gates. The transformation is reproducible with
`optimize_sergeev_multiplier.py`.

The 156-gate candidate passed all 4,096 possible inputs and all 1,200 training
rows. It has depth 36, no dead gates, no constant wires, and no duplicate or
complement-equivalent internal wires. It was promoted to `mystery-C.txt`; the
previous 165-gate winner was retained at
`abc-work/pre-sergeev-165/mystery-C.txt`.

### Searches after reaching 156

- Semantic resubstitution found no additional one-, two-, or three-gate
  replacement for the remaining fanout-free cones.
- Exact synthesis proved all completed six- and seven-gate contiguous tensor
  windows equal to their current gate counts.
- Eight- through twelve-gate exact windows exceeded the short proof budget,
  so they remain open rather than being classified as optimal.
- A whole-network eSLIM run exceeded its bounded runtime without producing a
  mapped candidate and was terminated.

The next promising search target is a constrained multi-output rewrite that
crosses a partial-product gate and two adjacent MDFA columns. Ordinary
boundary-tensor synthesis loses the multiplier reachability constraints that
enabled the 158-to-156 reduction, so future exact searches should encode
those constraints explicitly.

### Retained checkpoint

- A: 37 gates, depth 15.
- B: 49 gates, depth 21.
- C: 156 gates, depth 36.
- D: 114 gates, depth 28.
- Total: 356 gates, reduced from the original total of 385.

All four retained files pass their complete input domains and training sets.
## Iteration 15: public-record audit after the 158-to-156 reduction

The surprisingly short path from Sergeev's 158-gate construction to the verified
156-gate circuit required a stricter audit of what “best known” means.

### Why the two-gate reduction was available

Sergeev's 158 figure is a constructive upper bound obtained from a uniform
column-compression scheme.  It is not a proof that every exact 6-by-6 multiplier
needs 158 gates.  The construction's local compressor interfaces are designed
for generic input combinations, whereas a fixed 6-bit multiplier reaches only
a constrained subset of those interface assignments.

The semantic resubstitution search enumerated all 4096 primary-input pairs and
used those reachable states.  It replaced a four-gate MSB cone with the two-gate
expression equivalent on every reachable state:

```text
g159 = NAND ~g29 ~g154
g160 = AND g159 g36
```

Equivalently, the final bit is `g36 AND (g29 OR g154)`.  This is not an identity
for three arbitrary independent Boolean inputs; it is valid because these
signals are correlated inside this particular multiplier.  Consequently, a
purely local optimizer that regards the cut signals as independent can miss it.

### Literature audit

- Sergeev's 2016 paper uses the same six two-input gate types and reports 158 as
  the size of its constructed 6-bit standard multiplier.  The paper supplies an
  upper bound, not a matching lower bound or an optimality claim.
- The 2026 STACS paper *Smaller Circuits for Bit Addition* supplies newer generic
  adder and multiplier generators, but its multiplication comparison still
  points to Sergeev for the sharper small multiplier sizes.  Its public Cirbo
  generator does not provide a smaller exact 6-bit circuit in this metric.
- Searches by the exact small-size sequence, title citations, author
  bibliography, and later multiplier-circuit literature did not uncover a
  published exact 6-by-6 count below 158 under this precise unit-cost gate
  model.  This is evidence about the public literature checked, not proof that
  no unpublished circuit exists.

### Public challenge audit

Public pull requests linked to QuantumBFS challenge 71 were downloaded and
verified independently:

- PR 213 contains a 168-gate C circuit; exhaustive verification passes all 4096
  input pairs.
- PR 220 contains a 167-gate C circuit; exhaustive verification passes all 4096
  input pairs.
- Other inspected registrations did not expose a lower C netlist.

Thus no public challenge entry below 156 was found in the inspected issue and
pull-request history.

### Independent optimizer audit

The official SPbSAT Simplifier was built locally and run on the 156-gate circuit
after BENCH conversion.  BENCH has explicit inverter gates while the challenge
scores complemented wires for free, so the result was normalized by removing
explicit inverter cost.  Simplifier returned the same normalized score of 156;
a second pass was unchanged.  This is a useful independent negative check, but
not an optimality proof because its native cost model is not identical to the
challenge's free-inversion model.

### Current defensible claim

The 156-gate circuit is the smallest exact 6-by-6 multiplier found in this audit
under the challenge gate model, and its complete netlist is locally inspectable
and exhaustively verified.  Because it has not yet been published in the
challenge repository, the defensible wording is that it is a new candidate
upper bound.  It improves the published 158-gate upper bound, but it must not
yet be called a proven global minimum or an uncontested world record.  A private
circuit, an unindexed result, or a better future synthesis may be smaller.

The most promising implication is that additional reductions should target
larger multi-output cones under globally reachable cut states.  Optimizers that
assume independent boundary variables can systematically hide exactly the kind
of opportunity that produced 156.

## Iteration 16: D reduced from 114 to 113 gates

This iteration tested both reachability-aware local simplification and larger
multi-output graph regions on the retained 114-gate D circuit.

### Searches that did not reduce the circuit

- Full-domain semantic resubstitution tested all eligible one- and two-gate
  replacements for 24 roots and found no reduction.
- A three-gate-chain extension tested two four-gate maximal fanout-free cones
  and approximately 20.7 million candidate chains without finding a valid
  reduction.
- Convex graph regions were ranked by the fraction of boundary assignments
  reachable from the ten primary inputs. Forty low-occupancy regions were
  synthesized with explicit external don't-care assignments. None mapped below
  its original local gate count under the tested flows.

These are bounded negative results for the tested roots, regions, flows, and
budgets; they do not establish local or global optimality.

### Verified 27-to-26 joint-region replacement

A larger search selected a 27-gate convex region with eight boundary inputs and
six boundary outputs. An eSLIM run with maximum subcircuit size six and seed 102
produced a 26-gate realization.

The replacement passed all 256 assignments of the eight boundary inputs. After
embedding and topological reconstruction, the complete 113-gate circuit passed
all 1,024 primary-input assignments and all 400 training rows.

The retained 113-gate circuit has depth 27 and gate composition:

- 42 AND;
- 29 NOR;
- 29 XNOR;
- 10 XOR;
- 2 NAND;
- 1 OR.

Structural analysis found no dead gates, constant wires, or
duplicate/complement-equivalent internal-wire groups.

### Follow-up search on the 113-gate circuit

Full-domain one-, two-, and three-gate semantic resubstitution found no further
reduction. Three of the largest newly sampled joint regions, containing 30, 26,
and 26 gates, respectively, tied their source counts at best. Standard
whole-network ABC flows remapped the circuit to 115 through 117 gates. A bounded
whole-network eSLIM attempt exceeded its runtime without producing a mapped
candidate and was terminated.

No 112-gate circuit was found in this iteration. This is not an optimality
claim; larger constrained regions and other retained parent topologies remain
possible search directions.

### Retained checkpoint

- A: 37 gates, depth 15.
- B: 49 gates, depth 21.
- C: 156 gates, depth 36.
- D: 113 gates, depth 27.
- Total: 355 gates, reduced by 30 gates from the original total of 385.

All four retained files pass their complete input domains and training sets.
