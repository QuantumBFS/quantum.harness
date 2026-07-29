# oddcycle-path-metric-v1

This is the frozen empirical stress protocol for the final four-letter
candidate.  It is discovery/regression evidence, not an assumption of the
exact arbitrary-depth theorem.

From `tracks/qmc/solutions/no-negative-vibes`:

```bash
python -m oracle.oddcycle_joint_words \
  --point 0.001 1 1 \
  --point 0.8 1 1 \
  --exhaustive-depth 10 \
  --max-level-matrices 2000000 \
  --random-samples 100000 \
  --random-depth 40 \
  --rng-seed 923771 \
  --summary
```

The exhaustive part tests all 1,398,100 nonempty words through depth 10.
The random part advances 100,000 independent histories through all 40
depths, for 4,000,000 evaluated word prefixes.  Any floating nonpositive
witness is replayed exactly before classification.

The publication gates are replayed separately by:

```bash
python -m oracle.oddcycle_final_certificate
```

Historical production evidence additionally exhausted all 22,369,620
nonempty words through depth 12 and the Hodge diagnostic through depth 14.
Those larger runs and their machine settings are recorded in
`docs/EXPERIMENT_LOG.md`.
