---
name: using-quantum-espresso
description: Use when using Quantum ESPRESSO's native PHonon/DFPT package workflow to prepare, run, monitor, debug, or interpret electron-phonon coupling and superconductivity calculations involving pw.x, ph.x, q2r.x, matdyn.x, alpha2f.x, lambda_tetra, q/k convergence, or PHonon scratch failures. This skill owns the QE package run mechanics, literal input keywords, and templates. Use when using Quantum ESPRESSO to generate plane-wave orbitals for a Slater-Jastrow VMC and DMC workflow, including QE SCF/NSCF and pw2qmcpack.x ESHDF conversion, and MPI launch tuning.
---

# Using Quantum ESPRESSO

## DFPT / electron-phonon coupling route

Software-stack skill for using **Quantum ESPRESSO native DFPT-EPC** to study
electron-phonon superconductivity. It owns the package-level run mechanics:
build SCF and PHonon inputs, keep IFC and EPC branches separate, monitor long
`ph.x` jobs, diagnose fragile PHonon failures, and turn `alpha2F(omega)` into a
qualified superconducting `Tc` estimate.

Method understanding, method-vs-method routing, and knob JUDGMENT live in method-dfpt; result interpretation lives in physics-electron-phonon-coupling.

Stack contract: `skills/using-quantum-espresso/stack.toml`.
The reusable source templates live in `skills/using-quantum-espresso/references/dfpt/`:

```text
prepare-qe-todo.md
input-sources.md
scf.in
ph_ifc.in
q2r.in
matdyn_disp.in
ph_dvscf_epc.in
elph_densek_alpha2f.in
run_epc_sbatch.template.sh
```

Do not embed pseudopotential files in this skill. `references/dfpt/input-sources.md`
points to QE/SSSP download locations and records what the PdH-style templates
assume.

### Version assumptions

- Skill/template revision: 2026-06-30.
- Target route: Quantum ESPRESSO native PHonon EPC with `lambda_tetra`, as used
  by common QE 7.x PHonon builds and `PHonon/examples/tetra_example/`.
- The exact QE build is not bundled with this skill. Before each run, record the
  installed QE version, executable paths, module or build prefix, and whether
  `alpha2f.x` is serial-only for that build.
- Re-check input keywords against the installed QE documentation when using
  older QE 6.x builds, patched site builds, or future QE releases.

---

### The workflow spine

The ordered workflow-spine overview block is method-layer UNDERSTANDING and lives in method-dfpt. -> method-dfpt "The workflow spine".

Use one directory per parameter point:

```text
runs/<material-or-lattice>_q<N>_k<M>/
  pseudo/
  scf.in
  ph_ifc.in
  q2r.in
  matdyn_disp.in
  ph_dvscf_epc.in
  elph_densek_alpha2f.in
  run_epc.sbatch
  run_steps.tsv
```

Case names should be readable in a result table: include the structure or
lattice tag, EPC q grid, and dense electron k grid.

---

### Phase 1 - Prepare inputs (input keywords and templates)

Start from `skills/using-quantum-espresso/references/dfpt/` and adapt values to the project.

#### SCF

Use `scf.in` as the pattern:

- exact relaxed cell and atomic positions;
- `prefix`, `outdir`, and `pseudo_dir` that match every PHonon input;
- `occupations = 'tetrahedra_opt'` for the `lambda_tetra` route;
- a dense explicit `K_POINTS automatic` grid;
- project-validated `ecutwfc`, `ecutrho`, `conv_thr`, and mixing settings.

#### IFC branch

Use `ph_ifc.in -> q2r.in -> matdyn_disp.in` for ordinary force constants and
phonon dispersion:

- unshifted `ldisp = .true.` q grid;
- `q2r.x` and `matdyn.x` only on this IFC branch;
- `asr` / `zasr` selected according to the material and project convention.

#### EPC branch

Use `ph_dvscf_epc.in` for shifted-q dVscf generation:

- `ldisp = .true.`;
- `lshift_q = .true.`;
- `fildyn`, `fildvscf`, and `fildrho` set explicitly;
- `recover = .true.` allowed for restartable dVscf generation.

Then use `elph_densek_alpha2f.in` for dense-k `lambda_tetra`:

- `trans = .false.`;
- `electron_phonon = 'lambda_tetra'`;
- `nk1`, `nk2`, `nk3` set to the dense electron k grid;
- no `recover = .true.` in this dense-k lambda input;
- `&INPUTa2F nfreq = ... /` present so the same file can feed `alpha2f.x`.

Run `alpha2f.x` serially unless the exact QE build has been verified to support
parallel execution for that executable.

---

### Phase 2 - Submit safely

Use `references/dfpt/run_epc_sbatch.template.sh` as a starting point for cluster jobs.
Adapt the SBATCH header, modules, `QE_ROOT`, MPI launcher, `NPOOL`, and resource
request to the target system.

#### Parallel settings

Treat the Slurm allocation, MPI rank count, QE pool count, and thread variables
as one contract. Do not tune them independently.

- Use a CPU-only pure-MPI default unless a project has validated hybrid MPI/OpenMP.
- Set math-library threads to one for this default:
  `OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`.
- Match the launch command to the allocation. A portable pure-MPI layout is:

  ```bash
  #SBATCH --nodes=1
  #SBATCH --ntasks-per-node=64
  #SBATCH --cpus-per-task=1
  NP="${SLURM_NTASKS}"
  ```

  then run `mpirun -np "$NP" ...`.
- Some clusters prefer one Slurm task with many CPUs and a launcher that
  expands inside the allocated cpuset:

  ```bash
  #SBATCH --nodes=1
  #SBATCH --ntasks-per-node=1
  #SBATCH --cpus-per-task=64
  NP="${SLURM_CPUS_PER_TASK}"
  ```

  Use this only after verifying that the site MPI launcher really starts `NP`
  MPI ranks inside the allocation.
- Pass `-npool "$NPOOL"` to `pw.x` and the MPI `ph.x` steps. Choose `NPOOL` so
  it divides the MPI rank count and is sensible for the k-point count. Start
  conservative (`1`, `2`, `4`, or `8`) and verify QE reports the expected pools.
- Keep `q2r.x`, `matdyn.x`, and `alpha2f.x` serial unless the exact executable
  has been tested in parallel.
- Print `NP`, `NPOOL`, thread variables, `QE_ROOT`, and the node list at job
  start. After the first run, check `scf.out` or `ph*.out` for the reported
  processor count and pool count before trusting timing or failures.

Before submission, check:

```bash
bash -n run_epc.sbatch
rg -n "occupations|K_POINTS|electron_phonon|trans|recover|nk1|nfreq" *.in
rg -n "recover *= *.true." elph_densek_alpha2f.in && echo "remove recover"
```

Then verify by inspection:

- UPF names in `ATOMIC_SPECIES` exist under `pseudo/`.
- All QE inputs use the same `prefix` and `outdir`.
- Dense-k `lambda_tetra` input has `trans = .false.` and no `recover`.
- A full-rerun wrapper archives old outputs before starting.
- If IFC and EPC branches share one `outdir`, the wrapper archives `tmp/_ph0`
  after `matdyn.x` and before `ph_dvscf_epc`.
- The Slurm request, `NP`, `NPOOL`, and thread variables match the intended
  parallel layout.
- The dense k grid stays below the QE build's k-point array limit. A
  `set_kplusq: too many k points` failure means reduce `nk` or rebuild QE with
  a larger `npk`.

---

### Phase 3 - Monitor and diagnose

For live jobs, combine scheduler state with case-local evidence:

```bash
tail -n 20 run_steps.tsv 2>/dev/null
stat -c "%y %s %n" *.out 2>/dev/null
grep -E "Calculation of q|Representation #|JOB DONE|Error in routine|lambda|omega" -n *.out 2>/dev/null | tail -n 80
find . -maxdepth 1 \( -name "CRASH" -o -name "*.err" \) -type f -size +0 -print
```

Treat `ph_ifc` and `ph_dvscf_epc` as long-running stages. A job is slow/active,
not stuck, when q-point or representation lines continue advancing and there is
no non-empty `.err`, `CRASH`, or `Error in routine`.

#### Failure map

| Symptom | Likely cause | Response |
|---|---|---|
| `opt_tetra_init (2): cannot remap grid on k-point list` | EPC branch is reading stale PH scratch, or the SCF k list is incompatible with the tetrahedron remap | First inspect `Reading xml data from directory` in `ph_ifc.out` and `ph_dvscf_epc.out`. If EPC reads `tmp/_ph0/<prefix>.save/`, archive `_ph0` and rerun from the EPC branch before changing grids. |
| `read_control_ph (1): wrong trans` | Dense-k `elph` step recovered a previous `ph.x` control file with a different `trans` mode | Remove `recover = .true.` from `elph_densek_alpha2f.in`; archive only old dense-k outputs and rerun the post-dVscf branch. |
| `read_lam: Imaginary frequency` in `alpha2f.x` | Shifted EPC q grid contains imaginary modes | Do not force a physical `Tc`. Inspect structural stability, q-grid dependence, and phonon branches first. |
| Shifted q grid cannot be used by `q2r.x` | EPC shifted q grid is being reused as an IFC interpolation grid | Keep unshifted IFC/dispersion and shifted EPC grids as separate branches. |
| `set_kplusq: too many k points` | Dense electron k grid exceeds the QE build's static k-point array | Reduce `nk` or rebuild QE with a larger `npk`; record the limit in the result note. |

---

### Phase 4 - Interpret results (data collection and Tc value)

After `alpha2f.x` succeeds, collect:

- `lambda` from QE's direct `omega_q/lambda_q` summary;
- `omega_log` / `omega_ln`, with units;
- the `alpha2F(omega)` data file;
- an independent `alpha2F` integration check when the data file is present;
- `Tc` for at least `mu* = 0.10, 0.13, 0.15`;
- IFC branch and shifted EPC q-grid imaginary-frequency status.

The McMillan/Allen-Dynes interpretation form and units rule live in physics-electron-phonon-coupling "Interpretation rules"; the convergence-comparison logic lives in method-dfpt "Convergence judgment".

Write a short result note beside the run tree with the case name, QE version,
input grids, resources, step statuses, failure/success evidence, `lambda`,
`omega_log`, `Tc(mu*)`, imaginary-frequency status, and remaining convergence
caveats.

---

### Common mistakes (package mechanics)

| Mistake | Instead |
|---|---|
| Reusing `tmp/_ph0` from the IFC branch for shifted-q EPC | Archive or separate PH scratch before `ph_dvscf_epc`. |
| Running `q2r.x` on the shifted EPC q grid | Use an unshifted IFC branch for `q2r.x` / `matdyn.x`. |
| Leaving `recover = .true.` in the dense-k `lambda_tetra` input | Keep `recover` only in compatible restartable PHonon branches. |
| Reporting `Tc` after `alpha2f.x` reports imaginary frequencies | Report the instability; do not treat that `Tc` as physical. |
| Calling a q4/k21 canary a converged result | Add q-grid and dense-k checks before presenting a final number. |
| Trusting `RUNNING` or quiet stdout as proof of health | Inspect `run_steps.tsv`, output timestamps, q progress, and error files. |
| Requesting one Slurm shape but launching a different number of MPI ranks | Make Slurm tasks, `NP`, `NPOOL`, and thread variables agree, then verify QE's reported processor and pool counts. |

---

### Integrations

- **Source templates:** `skills/using-quantum-espresso/references/dfpt/`.
- **Stack contract:** `skills/using-quantum-espresso/stack.toml`.
- **Run preparation checklist:** `skills/using-quantum-espresso/references/dfpt/prepare-qe-todo.md`.
- **Input provenance and download locations:** `skills/using-quantum-espresso/references/dfpt/input-sources.md`.
- **Cluster wrapper template:** `skills/using-quantum-espresso/references/dfpt/run_epc_sbatch.template.sh`.
- **QE upstream reference:** the installed QE documentation and
  `PHonon/examples/tetra_example/` in a QE source tree.

## QMCPACK orbital-generation route

Software layer (QE / pw2qmcpack side) of the QE -> QMCPACK Slater-Jastrow VMC/DMC workflow for periodic solids. Method understanding/routing lives in method-dmc; the QMCPACK side lives in using-qmcpack.

### Source templates (QE side)

The reusable QE source templates are `references/qmcpack-orbitals/qe_scf.in`, `references/qmcpack-orbitals/qe_nscf.in`, and `references/qmcpack-orbitals/pw2qmcpack.in` (byte-exact copies). Stack contract and QMCPACK-side templates live in using-qmcpack.

### Run-directory layout (QE side)

QE entries of the shared run directory, moved verbatim from using-qmcpack Run-directory layout (the QMCPACK entries and the enclosing `runs/<system>_k<NxNyNz>/` block stay there):

```text
  qe_tmp/
  qe_scf.in
  qe_nscf.in
  pw2qmcpack.in
```

### Version assumptions (QE side)

Moved verbatim from using-qmcpack Version assumptions. -> the QMCPACK-side route (a QMCPACK 4.3.x complex-valued ESHDF/einspline solid workflow) and build-recording bullets in using-qmcpack.

Target route (QE portion): QE 7.5-style `pw.x` plus matching HDF5-enabled
  `pw2qmcpack.x`
- Orbital handoff: `pw2qmcpack.x` writes `<prefix>.pwscf.h5` under the QE
  `outdir`; QMCPACK XML `href` values point to that exact file.

### Preflight (QE side)

Most of Phase 0 stays in using-qmcpack. -> the QMCPACK-side items there: "2. Structure" (relaxed structure, atom count, species labels, cell units, pressure/lattice provenance, size-matching) and "3. Pseudopotential pair" (matched norm-conserving QE UPF + QMCPACK XML; stop on ultrasoft UPF) in using-qmcpack Phase 0 - Preflight

QE-side Phase 0 items, moved verbatim from using-qmcpack:
- Binaries: Verify `pw.x`, `pw2qmcpack.x`, and
- Run directory state: Inspect old `qe_tmp/`, `.save/`, `.pwscf.h5`,

### Generate QE orbitals

Start from `references/qmcpack-orbitals/qe_scf.in`, `references/qmcpack-orbitals/qe_nscf.in`, and
`references/qmcpack-orbitals/pw2qmcpack.in`.

#### SCF

- Use the target structure, the matched QE UPF, and project-validated cutoffs.
- Run with enough k-points to converge the charge density.
- Keep `prefix`, `outdir`, and pseudopotential names consistent with NSCF and
  `pw2qmcpack.in`.
- Use the QE build that belongs with `pw2qmcpack.x`.

#### NSCF

- Run at the exact full twist grid required by the QMC supercell.
- Set `nosym = .true.` and `noinv = .true.` so QE writes every twist, not a
  symmetry-reduced subset.
- Keep `K_POINTS automatic` synchronized with the intended twist count.
- Do not change the structure, pseudopotential, or prefix between SCF and NSCF.

#### Conversion

- Run `pw2qmcpack.x` after the NSCF completes.
- Expect the ESHDF file under the QE `outdir`, often
  `qe_tmp/<prefix>.pwscf.h5`.
- Keep the QMCPACK XML `href` pointed at that actual path, not a guessed file
  in the run-directory root.
- Use a serial converter launch (`PW2QMCPACK_NP=1`) unless this exact converter
  build has been proven safe with MPI.

-> QMCPACK XML `href` keyword/value and ESHDF consumption in using-qmcpack

### Submit safely (QE and converter parallelism)

"Treat QE parallelism and QMCPACK twist parallelism as different problems." (framing kept whole in using-qmcpack Submit safely)
-> QMCPACK twist parallelism and the submission/inspection checklists in using-qmcpack

#### QE

- Use `QE_NP` MPI ranks for `pw.x`.
- Pass a project-validated `-npool` for SCF/NSCF when useful.
- Verify QE reports the expected rank and pool counts in `qe_scf.out` and
  `qe_nscf.out`.

#### Converter

- Default `PW2QMCPACK_NP=1`.
- If the converter needs a special HDF5 library path, apply it only to the
  converter command rather than polluting the global QMCPACK runtime.

#### Consistency checks (QE side)

Moved verbatim from using-qmcpack Submit safely (the `bash -n` step, the QMCPACK `*.xml` grep, the `pseudo/`/`qmc_pseudo/` test, and the QMCPACK-side inspection bullets stay there):

```bash
rg -n "prefix|outdir|K_POINTS|nosym|noinv" qe_*.in pw2qmcpack.in
```

- UPF names in QE `ATOMIC_SPECIES` exist under `pseudo/`.
- SCF, NSCF, and `pw2qmcpack.in` use the same `prefix` and `outdir`.
- The NSCF grid matches the intended twist count and has `nosym` plus `noinv`.
- XML `href` points to the expected ESHDF under QE `outdir`.

### Cluster wrapper template (QE stage)

The QE SCF/NSCF/pw2qmcpack execution stage is the launcher `references/qmcpack-orbitals/run_qe_orbitals.template.sh` (byte-exact copy): QE SCF, QE NSCF, pw2qmcpack invocation, ESHDF check, and the `QE_BIN` / `PW2QMCPACK` / `QE_NP` / `QE_NPOOL` / `PW2QMCPACK_NP` env handling. -> the QMCPACK-stage launcher `using-qmcpack/references/run_qmcpack_dmc.template.sh` in using-qmcpack.

### Monitor and diagnose (QE side)

QE-stage output evidence, moved verbatim from using-qmcpack Monitor (the QMCPACK `qmcpack_*.out` / `*.scalar.dat` lines and the generic `stat`/`grep -E *.out` lines stay there):

```bash
grep -n "JOB DONE." qe_scf.out qe_nscf.out pw2qmcpack.out
test -s qe_tmp/*.pwscf.h5
```

The QE filenames of the live-job tail (moved from the `tail -n 40 ... qmcpack_*.out` line in using-qmcpack):

```text
qe_scf.out qe_nscf.out pw2qmcpack.out
```

#### Failure map (QE side)

Orbital-stage rows, moved verbatim from the using-qmcpack failure map (the QMCPACK-side rows stay there):

| Symptom | Likely cause | Response |
|---|---|---|
| QMCPACK cannot find `.pwscf.h5` | XML assumes the ESHDF is in the run root | Point `href` at the file under the QE `outdir`, e.g. `qe_tmp/<prefix>.pwscf.h5`. |
| NSCF or converted twist count is too small | QE symmetry reduced the k grid | Set `nosym=.true.` and `noinv=.true.` in NSCF and regenerate orbitals. |
| `pw2qmcpack.x` runs but no useful HDF5 appears | Wrong QE build, wrong prefix/outdir, or converter launched with a bad library/MPI setup | Use the QE build paired with `pw2qmcpack.x`; verify `prefix`, `outdir`, and converter library path. |

### Stack contract (QE stanzas)

The stack contract `stack.toml` (`id = "quantum-espresso"`, `language = "fortran"`) covers the QE/converter binaries: `[install.site]` command `command -v pw.x && command -v pw2qmcpack.x`, `[smoke.cpu_mpi]` command `pw.x -h >/dev/null && pw2qmcpack.x -h >/dev/null`, and `[docs] qe = "https://www.quantum-espresso.org/Doc/"`. -> the QMCPACK stack contract in using-qmcpack/stack.toml.

### Common mistakes (QE side)

| Mistake | Instead |
|---|---|
| Using a QE ultrasoft pseudopotential for production QMC orbitals | Use a norm-conserving QE UPF and matching QMCPACK XML pair. |
| Choosing QE k-points before the QMC twist plan | Choose the QMC cell and twist grid first, then generate NSCF twists. |

-> remaining (QMCPACK-side) common mistakes in using-qmcpack

### Input provenance (QE side)

The QE-side input-provenance lines and run-preparation rows now live here: `references/qmcpack-orbitals/input-sources.md` (QE documentation, version, QE-UPF source lines, Units, ESHDF Location) and `references/qmcpack-orbitals/prepare-qe-todo.md` (section "## 4. QE Orbital Inputs", the QE rows of "## 1. Version And Build Record", "## 3. Pseudopotential Pair", "## 2. Structure Materials", and "## 6. Run Controls").
-> the matched-pair prose and the QMCPACK-side rows in using-qmcpack/references/input-sources.md and using-qmcpack/references/prepare-qmcpack-todo.md
