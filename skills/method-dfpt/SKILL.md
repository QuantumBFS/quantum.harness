---
name: method-dfpt
description: Use when a DFPT electron-phonon coupling and superconductivity calculation needs method-level route and tool selection — native PHonon/DFPT workflow for alpha2F(omega), lambda, omega_log, McMillan/Allen-Dynes Tc, q/k convergence. This skill owns the method understanding, method-vs-method routing (DFPT vs EPW), and the knob JUDGMENT. This is for QE PHonon workflows, not EPW.
---

# Method: DFPT (density-functional perturbation theory) electron-phonon coupling

Method-level skill for studying electron-phonon superconductivity via the native DFPT-EPC route. It owns the method understanding, method-vs-method routing, and the knob JUDGMENT. Literal keywords, values, templates, and run mechanics live in using-quantum-espresso.

**Scope note.** This skill is for QE's PHonon route (`pw.x`, `ph.x`, `q2r.x`,
`matdyn.x`, `alpha2f.x`). It is **not** an EPW workflow. Use it when the user
wants native QE electron-phonon coupling, `lambda_tetra`, `alpha2F(omega)`,
`lambda`, `omega_log`, or McMillan/Allen-Dynes `Tc`. If the user asks for
Wannier interpolation, dense electron-phonon matrix interpolation, or EPW input
generation, switch to an EPW-specific workflow instead.

---

## Operating principle

**Branch-separated, evidence-first, convergence-qualified.**

- **Branch-separated** - keep the normal IFC/phonon-dispersion branch separate
  from the shifted-q EPC branch. Shared PHonon scratch is a common source of
  false k-grid failures.
- **Evidence-first** - judge jobs from `run_steps.tsv`, output tails, q-point
  progress, and concrete QE error text, not from scheduler state alone.
- **Convergence-qualified** - report `Tc` only with its q-grid, dense k-grid,
  structure, imaginary-frequency status, and remaining convergence caveats.

---

## The workflow spine

Use this sequence unless the active QE example or project convention gives a
validated reason to deviate:

```text
pw.x scf
ph.x ph_ifc                 # unshifted IFC branch
q2r.x
matdyn.x
archive tmp/_ph0 from IFC branch if one outdir is reused
ph.x ph_dvscf_epc           # shifted-q dVscf branch
ph.x elph_densek            # lambda_tetra on dense electron k grid
alpha2f.x                  # serial post-processing in common QE 7.x builds
```

The per-stage input files, directory layout, and exact invocation mechanics live in using-quantum-espresso. -> using-quantum-espresso "The workflow spine".

---

## Phase 0 - Preflight

Resolve the calculation context before writing or submitting anything:

If starting a new calculation, first walk through
`using-quantum-espresso/references/dfpt/prepare-qe-todo.md` and keep the completed copy or answers beside the
run tree.

1. **QE executables.** Verify the QE version and paths for `pw.x`, `ph.x`,
   `q2r.x`, `matdyn.x`, and `alpha2f.x`. Confirm the MPI launcher expected by
   the cluster or workstation.
2. **Structure.** Use the relaxed structure that the project actually wants to
   study. Check whether it is close to a phonon instability; EPC `Tc` is not
   meaningful if the relevant q grid has unresolved imaginary modes.
3. **Pseudopotentials and cutoffs.** Keep the exchange-correlation functional
   and pseudopotential family consistent across species. Copy or symlink UPF
   files into `pseudo/`; do not assume this skill ships them.
4. **Grid plan.** Record the SCF k grid, EPC shifted q grid, dense electron k
   grid, and at least one follow-up convergence comparison.
5. **Scratch policy.** Inspect whether old `tmp/`, `_ph0/`, `.save/`, `.dyn*`,
   `.elph*`, `.out`, or `.err` files exist. Decide whether this is a fresh run,
   a full rerun, or a post-processing continuation.

---

## Phase 1 - Prepare inputs (knob JUDGMENT)

The literal input keywords, per-file SCF / IFC / EPC value patterns, and templates live in using-quantum-espresso. -> using-quantum-espresso "Phase 1 - Prepare inputs". Two of those bullets carry the method JUDGMENT rather than a literal value: the ASR-choice rationale (the IFC-branch bullet "`asr` / `zasr` selected according to the material and project convention.") and the dense-k restart rationale (the EPC-branch bullet "no `recover = .true.` in this dense-k lambda input;").

---

## Convergence judgment

Do not call one parameter point final. At minimum compare:

- q-grid convergence at fixed dense k;
- dense-k convergence at fixed q grid;
- structural or lattice-constant sensitivity when the material is close to an
  instability;
- direct QE values against integrated `alpha2F(omega)` values.
