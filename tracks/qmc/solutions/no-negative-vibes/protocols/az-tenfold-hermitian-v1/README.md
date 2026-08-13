# AZ tenfold Hermitian-slice reconnaissance v1

This protocol asks one precise matrix question for each Altland--Zirnbauer
class: if every Hermitian time-slice generator obeys that class's canonical
TRS, PHS, and/or chiral constraints, what signs or phases occur in

```text
det(I + exp(A_1) ... exp(A_L))?
```

It is a common-convention reconnaissance table, not yet a full physical BdG
classification. In PHS classes the physical fermion trace can involve a
Pfaffian or a square-root branch, so a complex determinant here falsifies this
specific determinant statement but does not by itself prove that every QMC
formulation of the symmetry class has a phase problem.

## Canonical table

| Class | T^2 | C^2 | Chiral |
|---|---:|---:|---:|
| A | 0 | 0 | no |
| AI | +1 | 0 | no |
| BDI | +1 | +1 | yes |
| D | 0 | +1 | no |
| DIII | -1 | +1 | yes |
| AII | -1 | 0 | no |
| CII | -1 | -1 | yes |
| C | 0 | -1 | no |
| CI | +1 | -1 | yes |
| AIII | 0 | 0 | yes |

All representatives are `4 x 4`. Every random direction is normalized to
`||A||_F = 2 * scale` before exponentiation, so scale comparisons are not
confounded by the different number of free parameters in each class.

## Grid

- depths `1,2,3,4,8,16`, including the first depth at which three
  positive-definite slice factors can develop a nontrivial sign or phase;
- scales `0.25,0.75,1.5`;
- seeds `2101,2102,2103,2104`;
- 1000 products per cell;
- 720 cells and 720,000 products in total.

## Run

From the harness repository root:

```bash
RUN_DIR="$PWD/tracks/qmc/results/no-negative-vibes/az-tenfold-hermitian-v1"
MPLCONFIGDIR=/tmp/signfree-mpl python3 scripts/parameter_scan.py plan \
  --axes tracks/qmc/solutions/no-negative-vibes/protocols/az-tenfold-hermitian-v1/axes.json \
  --settings tracks/qmc/solutions/no-negative-vibes/protocols/az-tenfold-hermitian-v1/settings.json \
  --provenance tracks/qmc/solutions/no-negative-vibes/protocols/az-tenfold-hermitian-v1/provenance.json \
  --run-id az-tenfold-hermitian-v1 \
  --run-dir "$RUN_DIR"

cd tracks/qmc/solutions/no-negative-vibes
python3 -m oracle.scan "$RUN_DIR/run_spec.json"
```

The run is falsification-only: a negative or complex sample closes the
universal determinant claim for the stated convention, while zero hits only
promote a class to proof and known-mechanism analysis.
