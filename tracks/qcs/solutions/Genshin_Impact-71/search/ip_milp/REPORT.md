# Issue #71 IP/MILP experiment report

## Outcome

The independent 0–1 MILP arm is complete.  It produced exact warmup minima
for four low-output cones and 13 completed local no-improvement proofs across
A–D.  It found no new candidate circuit; five harder 4→3 windows reached their
solver limit and remain explicitly unresolved.

## Exact formulation

For every unknown gate, binary one-hot variables choose:

- each input literal, including free phase;
- one operation from AND, OR, XOR, NAND, NOR, XNOR;
- the gate value on every supplied truth-table row.

For an earlier unknown signal, the selected value is linearized as
`z = selector ∧ value` using `z ≤ selector`, `z ≤ value`, and
`z ≥ selector + value − 1` (with the corresponding complemented form).
Conditional linear inequalities impose all four rows of the chosen gate truth
table.  The two commutative ports are ordered to remove a symmetry.  This is a
MILP implemented through SciPy 1.16.1's bundled HiGHS backend, not the SAT
encoding used by the other experiment arm.

## Warmup output cones

All 16 assignments of `(x₀,x₁,y₀,y₁)` were constrained.

| Function | Infeasible size | Feasible size | Independent audit |
|---|---:|---:|---|
| add bit 0 | 0 | 1 | full 16-row truth table |
| add bit 1 | 2 | 3 | full truth table + exhaustive 2-gate enumeration |
| multiply bit 0 | 0 | 1 | full 16-row truth table |
| multiply bit 1 | 2 | 3 | full truth table + exhaustive 2-gate enumeration |

The independent enumeration imports neither SciPy nor the MILP source.  It
checked 71,280 commutativity-reduced two-gate configurations for each of add
bit 1 and multiply bit 1; neither target was reachable.

## A–D local exact synthesis

Every test asks whether an MFFC can be replaced by one fewer gate while using
the same safe, earlier-signal divisor boundary.  The 128-row primary batch uses
deterministic seed-42 witnesses.  The separate C/D batch uses 64 rows and
selects the smallest distinct MFFCs.  Infeasibility on a row subset is already
a valid obstruction to an exact full-domain replacement: an exact replacement
would necessarily satisfy every selected row.  A feasible subset result would
only be accepted after full-domain root and complete-circuit output audits.

| Circuit | Window | Attempt | Status |
|---|---|---:|---|
| A | w7 | 3→2 | proven infeasible |
| A | w12 | 3→2 | proven infeasible |
| A | w17 | 3→2 | proven infeasible |
| B | w49 | 4→3 | limit |
| B | w6 | 3→2 | proven infeasible |
| B | w10 | 3→2 | proven infeasible |
| C | w84 | 4→3 | limit |
| C | w102 | 4→3 | limit |
| C | w122 | 4→3 | limit |
| C | w39 | 2→1 | proven infeasible |
| C | w41 | 2→1 | proven infeasible |
| C | w46 | 2→1 | proven infeasible |
| D | w46 | 4→3 | limit |
| D | w34 | 3→2 | proven infeasible |
| D | w38 | 3→2 | proven infeasible |
| D | w11 | 2→1 | proven infeasible |
| D | w28 | 2→1 | proven infeasible |
| D | w30 | 2→1 | proven infeasible |

Summary: 13 `PROVEN_INFEASIBLE`, 5 `LIMIT`, 0 feasible local replacements,
and therefore 0 candidate netlists from this arm.

## Reproducibility

- Root seed: 42.
- Environment setup job: 43025, completed with exit code 0.
- Primary job: 43026 on n002, 4 CPU / 24 GiB, completed with exit code 0 in
  48:39; result wall time 2917.893 s.
- Distinct C/D small-window job: 43205 on n002, 4 CPU / 16 GiB, completed with
  exit code 0 in 10.736 s.
- An earlier submission, 43203, failed before execution because its Slurm log
  parent directory did not yet exist.  The directory was created and 43205 is
  the successful, complete rerun.
- NumPy 2.3.2 wheel SHA256:
  `938065908d1d869c7d75d8ec45f735a034771c6ea07088867f713d1cd3bbbe4f`.
- SciPy 1.16.1 wheel SHA256:
  `fedc2cbd1baed37474b1924c331b97bdff611d762c196fac1a9b71e67b813b1b`.

Primary artifact hashes:

- `results.json`:
  `e140e06abe40d08e3ffd932af32462999c2b1e635f446c415d030789e1f4ff78`
- `manifest.json`:
  `cfefe83bbcfdddb6a831f4e5e7cf1607250a9c968b7a49e1d868236ab761e23a`
- independent enumeration:
  `fd27f19a66f2b9604d71f9dc4b704074d3e37555e385d9a9a22e770b4950068c`
- C/D small-window results:
  `d732ed19ad34f3535bbd29cfbe7157ae0ae1656cf4f11985346d0426a1156d88`

## Security

Competing pull-request code and prose were never executed.  Reference
netlists were accepted only as strict inert ASCII data by a standalone parser.
