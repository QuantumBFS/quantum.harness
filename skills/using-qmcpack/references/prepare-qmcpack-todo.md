# QMCPACK DMC Run Preparation Todo

Use this checklist before creating or submitting a QE -> QMCPACK
Slater-Jastrow/DMC case. Fill the case-specific values in the run directory or
the project campaign note; do not treat this file itself as the run record.

## 1. Version And Build Record

-> the QE orbital-generation binary rows in using-quantum-espresso/references/qmcpack-orbitals/prepare-qe-todo.md
- [ ] Record the `qmcpack_complex` path, QMCPACK version, real/complex mode,
  HDF5 support, compiler/MPI stack, and OpenMP setting.
- [ ] Save the scheduler launcher pattern: `mpirun`, `srun`, `ibrun`, or
  cluster wrapper.
- [ ] Record the source template revision or git commit used to generate the
  inputs.

Suggested evidence to save after the first smoke:

```bash
head -n 120 sj_vmc_dmc_tw00.out
ldd "$QMCPACK_COMPLEX_BIN" | grep -E "hdf5|mpi|not found" || true
sha256sum pseudo/*.upf qmc_pseudo/*.xml
```
-> the QE evidence greps in using-quantum-espresso/references/qmcpack-orbitals/prepare-qe-todo.md

Template version assumption:

```text
QMCPACK: 4.3.x complex-valued ESHDF/einspline solid workflow
```
-> the QE template-version line in using-quantum-espresso/references/qmcpack-orbitals/prepare-qe-todo.md

If a project uses a different major version or a different XML/orbital route,
run a one-twist VMC smoke before expanding to all twists or DMC.

## 2. Structure Materials

- [ ] Relaxed structure file selected and named.
- [ ] Cell vectors and atomic positions checked against the intended pressure,
  lattice constant, or phase.
- [ ] Atom count and species list recorded.
-> the QE input cell-units row in using-quantum-espresso/references/qmcpack-orbitals/prepare-qe-todo.md
- [ ] QMCPACK XML lattice vectors converted to bohr.
- [ ] Size matching checked before comparing energies between structures.

## 3. Pseudopotential Pair

-> the QE-UPF row in using-quantum-espresso/references/qmcpack-orbitals/prepare-qe-todo.md
- [ ] QMCPACK pseudopotential is the matching XML from the same source.
- [ ] Exchange-correlation/source family recorded.
- [ ] SHA256 hashes recorded for every UPF and XML pseudopotential.
- [ ] UPF files copied or linked into `pseudo/`.
- [ ] QMCPACK XML pseudopotentials copied or linked into `qmc_pseudo/`.
- [ ] The QE `ATOMIC_SPECIES` filenames and QMCPACK `<pseudo href=...>` paths
  both resolve from the run directory.

Good starting locations:

```text
QMCPACK pseudopotential library:
https://github.com/QMCPACK/pseudopotentiallibrary

Hydrogen ccECP recipe used by the post-HCP reference workflow:
https://github.com/QMCPACK/pseudopotentiallibrary/tree/main/recipes/H/ccECP

H ccECP QMCPACK XML:
https://github.com/QMCPACK/pseudopotentiallibrary/blob/main/recipes/H/ccECP/H.ccECP.xml
```

For command-line download, use the raw GitHub URLs, for example:

```bash
curl -L -o H.ccECP.xml \
  https://raw.githubusercontent.com/QMCPACK/pseudopotentiallibrary/main/recipes/H/ccECP/H.ccECP.xml
```

For a new element or custom potential, start from one generator input or one
trusted library source and produce the QE UPF plus QMCPACK XML as a matched
pair. Do not use a convenient ultrasoft or PAW UPF as a production QMCPACK
orbital source.

## 4. QE Orbital Inputs

-> the whole "## 4. QE Orbital Inputs" section (moved verbatim) in using-quantum-espresso/references/qmcpack-orbitals/prepare-qe-todo.md

## 5. QMCPACK XML Inputs

- [ ] One XML input exists for every twist.
- [ ] Each XML has the correct `twistnum`.
- [ ] `determinantset href` points to the real ESHDF file under QE `outdir`.
- [ ] `simulationcell` lattice vectors are in bohr.
- [ ] Ion species, positions, and electron counts match the QE structure and
  pseudopotential valence.
- [ ] Slater determinant, Jastrow blocks, Hamiltonian, and pseudopotential XML
  paths are checked.
- [ ] Seeds are recorded and vary across independent replicas when needed.

## 6. Run Controls

-> the QE parallel-settings and converter rows in using-quantum-espresso/references/qmcpack-orbitals/prepare-qe-todo.md
- [ ] QMCPACK settings chosen: `PARALLEL_TWISTS`, `QMC_NP`,
  `OMP_NUM_THREADS`, `QMC_MPI_FLAGS`, and optional CPU sets.
- [ ] Short one-twist VMC smoke planned before all-twist SJ optimization or DMC.
- [ ] DMC parameters recorded: `timestep`, `blocks`, `steps`,
  `targetwalkers`, warmup/discard rule, nonlocal move setting, and replica
  count.
- [ ] Walltime, memory, scratch, and cleanup policy set.

## 7. Analysis Plan

- [ ] Scalar files and HDF5 output locations recorded.
- [ ] Warmup/discard rule selected before reading energies.
- [ ] Twist averaging rule selected and weights justified.
- [ ] Timestep-bias check planned for production DMC.
- [ ] Unit normalization chosen: Hartree, eV, meV/atom, meV/H, or another
  project convention.
- [ ] Final report will separate VMC/SJ and DMC results.
- [ ] Known caveats recorded, especially finite-size mismatch, unconverged
  twist grid, incomplete replicas, or untested code-version changes.
