---
name: using-qmcpack
description: Use when using QMCPACK to prepare, run, monitor, debug, or interpret plane-wave solid Slater-Jastrow VMC and DMC workflows, including Slater determinant setup, Jastrow optimization, twist averaging, fixed-node DMC, timestep checks, scalar analysis, and MPI or twist-parallel launch tuning.
---

# Using QMCPACK

Software layer (QMCPACK side) of the QE -> QMCPACK Slater-Jastrow VMC/DMC workflow for periodic solids. Method understanding, routing, and knob judgment live in method-dmc; the orbital-generation side lives in using-quantum-espresso.

Software-stack skill for using **QMCPACK DMC** to
study periodic solids. It owns the package-level run mechanics:
build QMCPACK XML inputs, optimize the Jastrow, run fixed-node DMC, and
summarize twist-averaged energies with defensible uncertainty and convergence
caveats.

**Scope note.** This skill is for plane-wave solid workflows that use QE
orbitals and QMCPACK's ESHDF/einspline path. It is not a QMCPACK build guide,
not a molecular Gaussian-basis workflow, and not a substitute for a
project-specific production campaign generator. Use it to create or review the
scientific workflow and launch discipline; use host/project skills for exact
binary paths and scheduler quirks.

## Scope and source templates

Stack contract: `skills/using-qmcpack/stack.toml`.
The reusable source templates live in `skills/using-qmcpack/references/`:

```text
prepare-qmcpack-todo.md
input-sources.md
sj_vmc_dmc_tw00.xml
run_qmcpack_dmc.template.sh
```

Do not embed pseudopotential files or production scalar/HDF5 output in this
skill. `references/input-sources.md` points to documentation and starting locations
for matched QE/QMCPACK pseudopotential pairs.

-> orbital-generation input templates and their mechanics in using-quantum-espresso

## Version assumptions

- Skill/template revision: 2026-06-30.
- Target route: a QMCPACK 4.3.x complex-valued ESHDF/einspline solid
  workflow. -> upstream orbital-generation route and version assumptions in using-quantum-espresso
- The exact QE and QMCPACK builds are not bundled with this skill. Before each
  run, record executable paths, versions, compiler/MPI/HDF5 stack,
  pseudopotential hashes, scheduler launcher, and source-template revision.
- Re-run a one-twist VMC smoke before expanding if the project uses a different
  major QE/QMCPACK version, a different orbital route, or a new
  pseudopotential pair.

## Run-directory layout

Use one directory per system/grid/campaign:

```text
runs/<system>_k<NxNyNz>/
  pseudo/
  qmc_pseudo/
  sj_vmc_dmc_tw00.xml
  sj_vmc_dmc_twNN.xml
  run_qmcpack_dmc.sh
  case_timing.dat
  twist_timings.dat
  summary.dat
```

Keep generated scalar/HDF5/wavefunction payloads out of version control unless
the project explicitly treats a small result file as durable evidence.

## Phase 0 - Preflight

Resolve the calculation context before writing or submitting anything.

If starting a new calculation, first walk through
`references/prepare-qmcpack-todo.md` and keep the completed copy or answers beside
the run tree.

1. **Binaries.** Verify `qmcpack_complex`. For
   non-Gamma solid twists, default to a complex QMCPACK build. -> upstream orbital-generation binary checks in using-quantum-espresso Preflight
2. **Structure.** Use the relaxed structure intended for QMC. Check atom count,
   species labels, cell units, pressure/lattice provenance, and whether
   structures being compared are size-matched.
3. **Pseudopotential pair.** Confirm the QE UPF and QMCPACK XML are a matched
   norm-conserving pair. If the QE route uses an ultrasoft UPF, stop and choose
   or generate a QMC-safe pair.
4. **Supercell and twists.** Choose the many-body cell and twist grid first.
   Record `K_POINTS`, twist count, `twistnum` range, and whether all structures
   being compared are size-matched.
5. **Run stage.** Decide whether this is a smoke, Jastrow optimization, fixed
   optimized DMC, timestep-bias suite, or production replica.
6. **Run directory state.** Inspect old
   `*.scalar.dat`, `*.stat.h5`, `.out`, and `.err` files. Decide whether this
   is a fresh run, continuation, or post-processing pass. -> upstream orbital-generation scratch inspection in using-quantum-espresso Preflight

-> supercell/twist-grid and run-stage judgment also in method-dmc; QE structure + pseudopotential-pair preflight also in using-quantum-espresso

## Prepare QMCPACK XML

Start from `references/sj_vmc_dmc_tw00.xml` and generate one XML per twist.

Required consistency checks:

- `determinantset` uses `type="einspline"` and `href` points to the ESHDF
  written by `pw2qmcpack.x`.
- `simulationcell` lattice vectors are in bohr.
- The Hamiltonian uses the matching QMCPACK XML pseudopotential.

-> twistnum / electron-group / position / optimize-stage judgment in method-dmc
-> QMCPACK XML template: `references/sj_vmc_dmc_tw00.xml` (byte-exact copy)

## Submit safely (QMCPACK twist parallelism)

Treat QE parallelism and QMCPACK twist parallelism as different problems.

-> QE parallelism and converter launch in using-quantum-espresso

### QMCPACK

- Prefer parallel independent twists over large thread counts inside one small
  twist.
- Use this accounting:

  ```text
  total QMC CPU slots = PARALLEL_TWISTS * QMC_NP * OMP_NUM_THREADS
  ```

- Default `OMP_NUM_THREADS=1` until a case is benchmarked otherwise.
- With OpenMPI plus outer CPU sets, use MPI flags such as `--bind-to none`.
- With Intel MPI, prefer explicit per-twist processor lists when the site
  launcher otherwise rebinds ranks onto one CPU.
- Print CPU sets, `PARALLEL_TWISTS`, `QMC_NP`, `OMP_NUM_THREADS`, and MPI flags
  before launching.

Before submission, check:

```bash
bash -n run_qmcpack_dmc.sh
rg -n "href=|twistnum|particleset|pseudo|timestep|targetwalkers" *.xml
test -d pseudo && test -d qmc_pseudo
```

Then verify by inspection:

- QMCPACK pseudopotential XML paths resolve under `qmc_pseudo/`.
- Slurm resources, `QE_NP`, `QE_NPOOL`, `PARALLEL_TWISTS`, `QMC_NP`, and
  `OMP_NUM_THREADS` match the launch plan.
-> upstream orbital-input consistency checks (species/prefix/grid/scratch path/href target) in using-quantum-espresso Submit safely

Do not trust CPU use by assumption. Check live placement when performance looks
wrong:

```bash
ps -C qmcpack_complex -o pid,ppid,psr,stat,pcpu,comm,args
grep Cpus_allowed_list /proc/<pid>/status
```

## Monitor and diagnose (QMCPACK side)

Use output evidence from every stage:

```bash
grep -n "QMCPACK execution completed successfully" qmcpack_*.out
ls -1 *.scalar.dat
```
-> upstream orbital-stage "JOB DONE" / ESHDF-written monitoring greps in using-quantum-espresso Monitor

For live jobs, combine scheduler state with case-local evidence:

```bash
stat -c "%y %s %n" *.out *.err *.scalar.dat 2>/dev/null
tail -n 40 qmcpack_*.out 2>/dev/null
grep -E "JOB DONE|Error in routine|Total Energy|DMC|VMC|execution completed" -n *.out 2>/dev/null | tail -n 80
```

Treat a job as active, not stuck, when scalar files or output timestamps keep
advancing and there is no non-empty `.err`, `CRASH`, parser failure, missing
HDF5 error, or MPI abort.

If the user asks for live status or ETA, use queue state plus workflow-local
timing files (`case_timing.dat`, `twist_timings.dat`, per-twist logs), not
queue state alone.

### Failure map

| Symptom | Likely cause | Response |
|---|---|---|
| QMCPACK rejects lattice/cell parsing | XML lattice vectors written in Angstrom | Convert lattice vectors to bohr before writing `simulationcell`. |
| QMCPACK electron count or SPO setup fails | Valence count, species labels, or pseudopotential XML paths do not match the QE structure | Recompute electron groups from the QMC pseudopotential valence and inspect every `<pseudo href=...>`. |
| CPU use is concentrated on a few cores | MPI rebinding inside outer twist CPU sets | Inspect rank affinity and switch to no-bind or explicit per-twist CPU lists. |

-> upstream orbital-stage failure rows (ESHDF/orbital-file not found, twist-symmetry reduction, converter produced no HDF5) in using-quantum-espresso Monitor

## Scalar analysis and interpretation (QMCPACK side)

For summaries:

- Discard the agreed warmup blocks before computing means.
- Report mean and uncertainty in Hartree and in the project-normalized unit
  such as meV/atom or meV/H.
- Twist-average equal-weight only when the twist grid and weights justify it.
- Compare relative energies only across size-matched many-body cells or label
  the comparison as a finite-size diagnostic.
- Keep VMC/SJ and DMC sections separate in human-facing reports.

For DMC comparisons, first check:

- size matching and atom-count normalization;
- twist grid and twist weights;
- ESHDF provenance and pseudopotential hashes;
- warmup/discard policy;
- timestep-bias evidence;
- independent replica count and seed plan.

DMC rankings that fail any of these checks are finite-size or workflow
diagnostics, not phase-ordering results.

Write a short result note beside the run tree with the case name, structure,
QE/QMCPACK versions, pseudopotential hashes, twist grid, resources, stage
statuses, scalar discard rule, VMC/SJ result, DMC result, and remaining
convergence caveats.

## Cluster wrapper template (QMCPACK launcher)

The launcher `references/run_qmcpack_dmc.template.sh` (byte-exact copy) runs the twist-parallel QMCPACK stage. It consumes the orbital file produced upstream. -> the orbital-generation stage launcher `using-quantum-espresso/references/qmcpack-orbitals/run_qe_orbitals.template.sh` in using-quantum-espresso.

## Stack contract (QMCPACK)

The stack contract `stack.toml` (`id = "qmcpack"`, `language = "c++"`) covers the QMCPACK binary, smoke, and docs. -> the orbital-generation stack contract in using-quantum-espresso/stack.toml.

## Common mistakes (QMCPACK side)

| Mistake | Instead |
|---|---|
| Reusing optimized Jastrows across different twist grids or ESHDF files | Reoptimize or prove equivalence before reuse. |
| Running all production twists before a one-twist smoke passes | Gate every campaign with a tiny VMC smoke. |
| Comparing DMC energies from different atom counts as phase rankings | Use size-matched cells or label the result as a finite-size warning. |
| Reporting one timestep as production DMC | Run or cite a timestep-bias check. |
| Trusting `RUNNING` as proof of health | Inspect output tails, scalar timestamps, error files, and timing records. |

-> QE-pseudopotential / QE-k-point common mistakes in using-quantum-espresso

## Integrations

- **Run preparation checklist:** `skills/using-qmcpack/references/prepare-qmcpack-todo.md`.
- **Source templates:** `skills/using-qmcpack/references/`.
- **Stack contract:** `skills/using-qmcpack/stack.toml`.
- **Input provenance and download locations:** `skills/using-qmcpack/references/input-sources.md`.
- **Cluster wrapper template:** `skills/using-qmcpack/references/run_qmcpack_dmc.template.sh`.
- **QE EPC skill for DFPT superconductivity:** `skills/using-quantum-espresso/SKILL.md` (different workflow).
- **Local machine build note:** user-level `qmcpack-local-build` when available.
