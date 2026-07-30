# Issue #71: independent IP/MILP experiment arm

This directory implements a genuine 0–1 integer-programming route.  It does
not call the SAT encodings used by the other search arms.

## Formulation

For every synthesized gate, the model has one-hot binary variables for:

- the left and right input literals (both phases of every available signal);
- one of AND, OR, XOR, NAND, NOR, and XNOR;
- the gate's Boolean value on every truth-table row.

The product between a topology selector and an earlier unknown gate value is
linearized with the usual three binary McCormick inequalities.  Conditional
truth-table inequalities impose the selected gate operation.  The last gate is
constrained to the target on every supplied row.  All operations are
commutative, so the model removes the port-swap symmetry.

HiGHS status `Infeasible` is a proof that no circuit of the requested size can
match the supplied rows within this topology and divisor boundary.  In the
local-window experiments, an infeasible deterministic subset is already a
valid obstruction to an exact full-domain replacement: every exact
replacement would also have to match that subset.  A feasible subset solution
is never accepted directly; it is independently evaluated on the entire input
domain, spliced into the full circuit, and all circuit outputs are compared.

## Reproduction

The environment is locked to CPython 3.13 Linux wheels:

- NumPy 2.3.2
- SciPy 1.16.1 (bundled HiGHS MILP backend)

Both wheel SHA256 hashes are in `requirements.lock`.  On `t02-server`, submit:

```bash
sbatch setup_scipy_home.sbatch
sbatch --dependency=afterok:<setup-job-id> run_ip_milp_home.sbatch
```

The canonical root seed is 42.  The run writes an incremental JSON record after
every solved instance, a final `results.json`, source hashes, Slurm metadata,
and a `COMPLETE` sentinel.

## Security boundary

Reference netlists are parsed as strict inert ASCII data.  No code, scripts, or
instructions from competing pull requests are imported or executed.
