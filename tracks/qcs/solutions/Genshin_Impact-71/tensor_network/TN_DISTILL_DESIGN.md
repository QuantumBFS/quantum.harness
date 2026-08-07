# Issue 71: continuous MPS to ROBDD to gate-netlist distillation

This audit-only stage completes the conversion path suggested by the issue.

- Select exactly one frozen MPS per mystery instance using only validation
  exact accuracy, validation bit accuracy, lower validation RMSE, then smaller
  bond. Full-domain accuracy is not part of selection.
- Exhaustively threshold that already-frozen MPS.
- Reduce the resulting multi-output truth table into a shared ordered BDD using
  the selected MPS variable order.
- Convert every BDD node to simplified AND/OR MUX logic, with free inversions,
  and write a syntactically legal issue-71 netlist.
- Independently parse and bit-parallel simulate the serialized netlist over the
  complete domain. It must exactly equal the thresholded MPS predictions.
- Separately report mismatches to the arithmetic truth. Any nonzero mismatch
  makes the netlist an analysis artifact, not a challenge candidate.

The four cells use root seed 42 indirectly through the immutable selected MPS
artifacts from Slurm array 42698. Each requests one CPU and 8 GiB.
