# Input Sources For QE Orbital-Generation Templates

QE-side lines moved verbatim from using-qmcpack/references/input-sources.md. The QMCPACK-side lines and the shared matched-pair prose stay there.

## Documentation

- Quantum ESPRESSO documentation: <https://www.quantum-espresso.org/documentation/>

## Version Assumptions

```text
QE:       7.5-style HDF5 build with pw2qmcpack.x
```

## Pseudopotentials

QE-UPF source lines (the matched-pair prose and the QMCPACK XML lines stay in using-qmcpack):

```text
QE:       norm-conserving UPF
```

```text
H ccECP QE UPF:
https://github.com/QMCPACK/pseudopotentiallibrary/blob/main/recipes/H/ccECP/H.ccECP.upf
```

```bash
curl -L -o H.ccECP.upf \
  https://raw.githubusercontent.com/QMCPACK/pseudopotentiallibrary/main/recipes/H/ccECP/H.ccECP.upf
```

## Units

The QE templates use `CELL_PARAMETERS angstrom`. The QMCPACK XML template uses
`<parameter name="lattice" units="bohr">`. Convert the QE cell before writing
QMCPACK XML.

## ESHDF Location

`pw2qmcpack.x` typically writes the ESHDF under QE `outdir`, for example:

```text
qe_tmp/qmc_solid.pwscf.h5
```

Keep the QMCPACK `href` pointed at the real generated file.
