# Speculative sign-free structures v1

This is the first aggressive local falsification batch reserved in
`docs/SPECULATIVE_CANDIDATE_BATCH.md`.

## Grid

- 12 candidate or boundary-control families;
- dimensions 3 through 8;
- depths `2,3,4,8,16`;
- scales `0.5,1,2,3`;
- four deterministic seeds;
- 200 products per cell;
- 960 cells and 192,000 determinant weights.

The odd-monomial and block-monomial cases sample their one-body evolution
factors directly.  Every sampled factor is constrained to admit a real
logarithm, so it remains an admissible `B_l=exp(A_l)` time slice without paying
for a numerical matrix logarithm in every sample.

Zero negative samples only make a family a numerical survivor.  Rigorous
survivors are upgraded separately using cycle factorization, a common norm,
parabolic block factorization, or commutativity.  The `D4` zero-failure cases
are classified separately as a reduction to the known split-orthogonal
mechanism.

## Outcome

All 960 cells completed.  Odd `C3/C5` monomial, odd block-TN, fixed
`l_infinity`, reciprocal-parabolic, split `D4`, and commuting controls had no
stable negative weights.  Even `V4` monomial, moving metric, bidirectional
reciprocal coupling, and near-commuting unions all failed.  Four representative
failures were replayed at 80 digits.  See
`docs/SPECULATIVE_STRUCTURE_RESULTS.md` for counts, proofs, reductions, and
interpretation.

## Run

From the harness repository root:

```bash
RUN_DIR="$PWD/tracks/qmc/results/no-negative-vibes/speculative-structures-v1"
python3 scripts/parameter_scan.py plan \
  --axes tracks/qmc/solutions/no-negative-vibes/protocols/speculative-structures-v1/axes.json \
  --settings tracks/qmc/solutions/no-negative-vibes/protocols/speculative-structures-v1/settings.json \
  --provenance tracks/qmc/solutions/no-negative-vibes/protocols/speculative-structures-v1/provenance.json \
  --run-id speculative-structures-v1 \
  --run-dir "$RUN_DIR"

cd tracks/qmc/solutions/no-negative-vibes
PYTHONPATH=. python3 -m oracle.scan "$RUN_DIR/run_spec.json"
```

Collect from the repository root:

```bash
python3 scripts/parameter_scan.py collect \
  --run-spec tracks/qmc/results/no-negative-vibes/speculative-structures-v1/run_spec.json \
  --success-field completed \
  --success-value true \
  --value-field counts.negative \
  --value-field counts.complex \
  --value-field counts.uncertain \
  --value-field max_structure_residual
```

The completed outcome and high-precision counterexamples are documented in
`docs/SPECULATIVE_STRUCTURE_RESULTS.md`.
