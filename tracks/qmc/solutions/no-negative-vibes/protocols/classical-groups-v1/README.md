# Classical groups baseline v1

This is a deterministic falsification scan, not a positivity proof.

## Grid

- 15 compact, split, special-linear, real-symplectic, pseudo-unitary, and
  compact-symplectic cases;
- depths `1,2,4,8,16`;
- generator scales `0.25,0.75,1.5`;
- four independent seeds;
- 1000 products per cell, for 900,000 products in total.

## Run

From the harness repository root:

```bash
RUN_DIR="$PWD/tracks/qmc/results/no-negative-vibes/classical-groups-v1"
MPLCONFIGDIR=/tmp/signfree-mpl python3 scripts/parameter_scan.py plan \
  --axes tracks/qmc/solutions/no-negative-vibes/protocols/classical-groups-v1/axes.json \
  --settings tracks/qmc/solutions/no-negative-vibes/protocols/classical-groups-v1/settings.json \
  --provenance tracks/qmc/solutions/no-negative-vibes/protocols/classical-groups-v1/provenance.json \
  --run-id classical-groups-v1 \
  --run-dir "$RUN_DIR"

cd tracks/qmc/solutions/no-negative-vibes
python3 -m oracle.scan "$RUN_DIR/run_spec.json"
```

Then collect from the harness repository root:

```bash
MPLCONFIGDIR=/tmp/signfree-mpl python3 scripts/parameter_scan.py collect \
  --run-spec tracks/qmc/results/no-negative-vibes/classical-groups-v1/run_spec.json \
  --success-field completed \
  --success-value true \
  --value-field counts.negative \
  --value-field counts.complex \
  --value-field counts.uncertain \
  --value-field max_structure_residual
```

Generated cells and tables live under `tracks/qmc/results/`, which the harness
intentionally excludes from Git.
