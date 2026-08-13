# Frontier semigroup falsification scan v1

This is a rapid local falsification scan over 15 structured generator sets. A
zero-negative result is a survivor for proof analysis, not evidence of a new
sign-free class.

## Grid

- 15 candidate or control families;
- dimensions 4 and 6;
- depths `2,3,4,8,16,32`;
- normalized generator scales `0.5,1,2,3`;
- four seeds;
- 500 products per cell;
- 1,440 cells and 720,000 determinant weights.

## Candidate comparisons

1. totally-nonnegative path generators versus cycle, star, and dense Metzler
   graph extensions;
2. a common path gauge versus independently changing the gauge on each slice;
3. one fixed split-contraction cone versus two slightly rotated cones;
4. block-upper-triangular coupling versus unrestricted bidirectional coupling.

Known split-cone and factorization cases are included as positive controls.

## Outcome

All 1,440 cells completed.  Path candidates had zero stable negative samples
and were subsequently proved nonnegative using the totally-nonnegative matrix
semigroup.  Cycle, star, dense-graph, changing-gauge, mixed-angle `0.5`, and
bidirectionally coupled candidates all produced negative weights.  See
`docs/FRONTIER_SEMIGROUP_RESULTS.md`.

## Run

From the harness repository root:

```bash
RUN_DIR="$PWD/tracks/qmc/results/no-negative-vibes/frontier-semigroups-v1"
python3 scripts/parameter_scan.py plan \
  --axes tracks/qmc/solutions/no-negative-vibes/protocols/frontier-semigroups-v1/axes.json \
  --settings tracks/qmc/solutions/no-negative-vibes/protocols/frontier-semigroups-v1/settings.json \
  --provenance tracks/qmc/solutions/no-negative-vibes/protocols/frontier-semigroups-v1/provenance.json \
  --run-id frontier-semigroups-v1 \
  --run-dir "$RUN_DIR"

cd tracks/qmc/solutions/no-negative-vibes
PYTHONPATH=. python3 -m oracle.scan "$RUN_DIR/run_spec.json"
```

Collect with:

```bash
python3 scripts/parameter_scan.py collect \
  --run-spec tracks/qmc/results/no-negative-vibes/frontier-semigroups-v1/run_spec.json \
  --success-field completed \
  --success-value true \
  --value-field counts.negative \
  --value-field counts.complex \
  --value-field counts.uncertain \
  --value-field max_structure_residual
```
