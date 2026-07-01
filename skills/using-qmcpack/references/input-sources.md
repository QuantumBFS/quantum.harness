# Input Sources For QMCPACK DMC Templates

The files in this directory are source templates, not a complete production
workflow. Before running them, provide project-specific structures,
pseudopotentials, executable paths, twist grids, and scheduler settings.

## Documentation

- QMCPACK documentation: <https://qmcpack.readthedocs.io/>
- QMCPACK input examples and source: <https://github.com/QMCPACK/qmcpack>
-> orbital-generation documentation link in using-quantum-espresso/references/qmcpack-orbitals/input-sources.md

## Version Assumptions

These templates follow the route validated in the local/post-HCP reference
workflow:

```text
QMCPACK: 4.3.x complex-valued ESHDF/einspline workflow
```
-> the QE-side version line in using-quantum-espresso/references/qmcpack-orbitals/input-sources.md

Record the exact executable paths, versions, compiler/MPI/HDF5 stack, and input
template revision in each run directory. Treat these files as examples unless
that version record has been filled for the active machine.

## Pseudopotentials

For production QMCPACK, use a matched pseudopotential pair:

```text
QMCPACK: XML pseudopotential for the same element/source
```
-> the QE-UPF source lines of "## Pseudopotentials" in using-quantum-espresso/references/qmcpack-orbitals/input-sources.md

Do not use an ultrasoft or PAW QE pseudopotential as a production QMC orbital
source unless the project has an explicit, validated route for doing so. In the
post-HCP hydrogen reference workflow, the useful pair was a ccECP-style
`H.ccECP.upf` for QE and matching `H.ccECP.xml` for QMCPACK.

Starting points:

```text
QMCPACK pseudopotential library:
https://github.com/QMCPACK/pseudopotentiallibrary

Hydrogen ccECP recipe:
https://github.com/QMCPACK/pseudopotentiallibrary/tree/main/recipes/H/ccECP

H ccECP QMCPACK XML:
https://github.com/QMCPACK/pseudopotentiallibrary/blob/main/recipes/H/ccECP/H.ccECP.xml
```

Raw download form:

```bash
curl -L -o H.ccECP.xml \
  https://raw.githubusercontent.com/QMCPACK/pseudopotentiallibrary/main/recipes/H/ccECP/H.ccECP.xml
```

For a custom potential, keep the generator input or trusted library recipe as
the source of truth and export both the QE UPF and QMCPACK XML from that same
source. Record SHA256 hashes beside the run.

## Units

-> "## Units" (QE cell units and bohr conversion) in using-quantum-espresso/references/qmcpack-orbitals/input-sources.md

## ESHDF Location

-> "## ESHDF Location" (where the orbital file is written, and keeping the QMCPACK `href` pointed at it) in using-quantum-espresso/references/qmcpack-orbitals/input-sources.md
