# Majorana cones with a shared reality structure v1

## Precise question

For a complex skew-symmetric Majorana generator `A`, the known
reflection-positive cone is defined by two anticommuting real orthogonal
structures `J1` and `J2`:

```text
J1^T A J1 = conjugate(A)
i (J2 A - conjugate(A) J2) <= 0.
```

Every individual time slice in that cone has nonnegative fermionic trace under
arbitrary products from the same cone. This protocol asks a controlled
relaxation: may consecutive slices use either of two such cones when both cones
share the same `J1` reality condition, but their `J2` contraction directions
are separated by an angle?

The common `J1` keeps the full product trace real. Therefore a negative result
tests a genuine sign failure, rather than the trivial complex phase produced
when the reality structures are also mixed.

## Weight oracle

The physical small-system weight is evaluated directly in Fock space:

```text
p = Tr(exp(h_1) ... exp(h_L)),
h_l = gamma^T A_l gamma / 4.
```

The code also checks, for every sample,

```text
p^2 = det(I + exp(A_1) ... exp(A_L)).
```

This direct trace fixes the two-valued Spin square-root branch that a
determinant-only oracle cannot determine.

## Grid and cost

- Majorana dimensions `4` and `6`, with Fock dimensions `4` and `8`;
- depths `2,3,4,6,8,12,16`;
- scales `0.5,1,2,3`;
- relative angles from `0` through `pi`;
- four seeds and 250 products per cell;
- 1,792 cells and 448,000 Fock-space weights.

The angle-zero cells are theorem-grade positive controls because the two cones
then coincide. A negative weight at any nonzero angle falsifies universal
nonnegativity for that two-cone union. Survival at a finite grid point only
promotes it to targeted testing or proof analysis.

## Run

From the harness repository root:

```bash
RUN_DIR="$PWD/tracks/qmc/results/no-negative-vibes/majorana-shared-reality-cones-v1"
MPLCONFIGDIR=/tmp/signfree-mpl python3 scripts/parameter_scan.py plan \
  --axes tracks/qmc/solutions/no-negative-vibes/protocols/majorana-shared-reality-cones-v1/axes.json \
  --settings tracks/qmc/solutions/no-negative-vibes/protocols/majorana-shared-reality-cones-v1/settings.json \
  --provenance tracks/qmc/solutions/no-negative-vibes/protocols/majorana-shared-reality-cones-v1/provenance.json \
  --run-id majorana-shared-reality-cones-v1 \
  --run-dir "$RUN_DIR"

cd tracks/qmc/solutions/no-negative-vibes
python3 -m oracle.majorana_scan "$RUN_DIR/run_spec.json"
```
