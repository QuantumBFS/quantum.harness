# AZ survivor-cone scan v1

This protocol tests the most direct number-conserving semigroup-cone
extensions of the four Hermitian Altland-Zirnbauer survivors found in the
earlier scan: BDI, AII, DIII, and CII.  It is a falsification screen, not a
proof that a surviving family is new or sign-free.

## Grid

- seven candidate or control families in the standard `4 x 4` representation;
- depths `2,3,4,8,16`;
- normalized generator scales `0.5,1,2,3`;
- four seeds;
- 250 products per cell;
- 560 cells and 140,000 determinant weights.

## Families

- `azcone_bdi_split`: one fixed real split-contraction cone, a known-positive
  control;
- `azcone_bdi_two_sided`: each time slice may independently use the
  contraction or expansion direction;
- `azcone_aii_kramers`: the full non-Hermitian Kramers-invariant algebra, a
  known-positive control;
- `azcone_diii_phs`: a DIII base plus a positive chiral-metric direction
  constrained to retain particle-hole symmetry;
- `azcone_diii_generic`: the same metric cone with a generic positive
  direction;
- `azcone_cii_kramers`: a CII metric cone constrained to retain Kramers
  symmetry, a known-positive control;
- `azcone_cii_generic`: the corresponding generic positive direction.

## Interpretation

A negative or genuinely complex determinant falsifies the proposed
number-conserving cone.  A zero-failure result only leaves a survivor for
proof and novelty analysis.  This protocol does not cover the full
Bogoliubov-de Gennes or complex-Majorana/Pfaffian problem.

## Run

From the harness repository root:

```bash
RUN_DIR="$PWD/tracks/qmc/results/no-negative-vibes/az-survivor-cones-v1"
python3 scripts/parameter_scan.py plan \
  --axes tracks/qmc/solutions/no-negative-vibes/protocols/az-survivor-cones-v1/axes.json \
  --settings tracks/qmc/solutions/no-negative-vibes/protocols/az-survivor-cones-v1/settings.json \
  --provenance tracks/qmc/solutions/no-negative-vibes/protocols/az-survivor-cones-v1/provenance.json \
  --run-id az-survivor-cones-v1 \
  --run-dir "$RUN_DIR"

cd tracks/qmc/solutions/no-negative-vibes
PYTHONPATH=. python3 -m oracle.scan "$RUN_DIR/run_spec.json"
```

Collect with:

```bash
python3 scripts/parameter_scan.py collect \
  --run-spec tracks/qmc/results/no-negative-vibes/az-survivor-cones-v1/run_spec.json \
  --success-field completed \
  --success-value true \
  --value-field counts.positive \
  --value-field counts.negative \
  --value-field counts.complex \
  --value-field counts.uncertain \
  --value-field max_structure_residual
```
