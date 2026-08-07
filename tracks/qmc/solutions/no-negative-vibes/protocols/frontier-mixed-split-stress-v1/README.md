# Small-angle mixed split-cone stress scan

This scan follows up the zero-negative `0.05` and `0.2` mixed-cone cells from
`frontier-semigroups-v1`.  It is a falsification stress test, not a positivity
proof.

- fixed split cone as a positive control;
- mixed split cones at angles `0.05` and `0.2`;
- depths through 64;
- scales through 4;
- eight seeds and 1000 products per cell;
- 672 cells and 672,000 determinant weights.

Run with `scripts/parameter_scan.py plan`, followed by
`PYTHONPATH=. python3 -m oracle.scan RUN_DIR/run_spec.json`.

## Outcome

All 672 cells completed.  The angle-`0.2` family produced nine negative
weights; the best-conditioned saved example was confirmed with 80-digit
matrix exponentials.  Angle `0.05` had no random hits, but a subsequent
rank-one boundary construction proved

```text
det(I + exp(A_1) exp(A_2)) = 16 (1 - q^2 sin(theta)^2)
```

in the four-dimensional embedding.  Thus every distinct rotated cone
(`sin(theta) != 0`) is falsified, including `0.05`; the zero-hit result records
sampling difficulty rather than a surviving conjecture.
