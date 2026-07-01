# QE Orbital-Generation Run Preparation Todo

QE-side checklist items moved verbatim from using-qmcpack/references/prepare-qmcpack-todo.md. The QMCPACK-side items stay there.

## 1. Version And Build Record (QE rows)

- [ ] Record the `pw.x` path, QE version, compiler/MPI stack, and whether the
  build is HDF5-enabled.
- [ ] Record the `pw2qmcpack.x` path and confirm it comes from the same QE build
  used for SCF/NSCF orbital generation.

QE evidence to save after the first smoke (QMCPACK lines stay in using-qmcpack):

```bash
head -n 60 qe_scf.out
head -n 60 qe_nscf.out
head -n 80 pw2qmcpack.out
ldd "$PW2QMCPACK" | grep -E "hdf5|mpi|not found" || true
```

QE template version assumption:

```text
QE:       7.5-style HDF5 + pw2qmcpack.x workflow
```

## 2. Structure Materials (QE row)

- [ ] QE input cell units chosen.

## 3. Pseudopotential Pair (QE-UPF rows)

- [ ] QE orbital pseudopotential is a norm-conserving UPF.

QE-UPF source lines (the matched-pair prose and the QMCPACK XML lines stay in using-qmcpack):

```text
H ccECP QE UPF:
https://github.com/QMCPACK/pseudopotentiallibrary/blob/main/recipes/H/ccECP/H.ccECP.upf
```

```bash
curl -L -o H.ccECP.upf \
  https://raw.githubusercontent.com/QMCPACK/pseudopotentiallibrary/main/recipes/H/ccECP/H.ccECP.upf
```

## 4. QE Orbital Inputs

- [ ] `qe_scf.in` has the target structure, pseudopotential names, cutoffs,
  `prefix`, `pseudo_dir`, and `outdir`.
- [ ] `qe_nscf.in` uses the same structure, pseudopotentials, `prefix`, and
  `outdir`.
- [ ] NSCF has `nosym = .true.` and `noinv = .true.`.
- [ ] NSCF `K_POINTS` equals the QMC twist grid.
- [ ] `pw2qmcpack.in` uses the same `prefix` and `outdir`.
- [ ] Expected ESHDF path recorded, usually
  `qe_tmp/<prefix>.pwscf.h5`.

## 6. Run Controls (QE rows)

- [ ] QE parallel settings chosen: `QE_NP`, `QE_NPOOL`, and scheduler resources.
- [ ] Converter setting chosen; default to `PW2QMCPACK_NP=1` unless proven safe
  otherwise.
