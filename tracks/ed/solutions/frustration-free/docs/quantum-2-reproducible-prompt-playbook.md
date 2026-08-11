# Reproducible Prompt Playbook: Quantum Harness Tasks

This guide condenses the project’s prior conversations into reusable English prompts and short execution routes. Replace text in `<angle brackets>` with your own problem details. Do not paste credentials, private keys, or tokens into prompts.

## 1. Understand a Repository Before Working

**Prompt**

```text
Explore this repository and give me a concise architecture map. Cover the entry points, skills/workflow conventions, experiment-track layout, run artifacts, scripts, CI, and documentation. Read files first; do not modify anything. Cite the central claims as file:line references.
```

**Route**

1. Inspect the root README, configuration, skills, tracks, scripts, and docs.
2. Ask for the architecture summary.
3. Confirm the relevant track and existing scripts before requesting new work.

---

## 2. Design a New Harness Capability Safely

**Prompt**

```text
I want to extend this Quantum Harness with <capability>. First inspect the current conventions and brainstorm a minimally invasive design. Compare viable directory locations, required skill/command behavior, documentation changes, and integration points. Do not implement yet. End with a recommended architecture and explicit user approval gates.
```

**Route**

1. Create an isolated branch or worktree.
2. Ask for a design review and choose an option.
3. Request a written spec.
4. Approve implementation only after reviewing the spec.
5. Test, visualize the changed structure if useful, then merge only after approval.

---

## 3. Add a Project-Specific Knowledge Base

**Prompt**

```text
Design a project-specific knowledge base for this repository. It should store curated, reusable facts for an individual research track—such as validated benchmarks, conventions, and domain-specific notes—without bloating global knowledge. Propose the directory layout, a README-based entry convention, agent instructions, and a dedicated command for reading it. Avoid hooks unless they are necessary.
```

**Route**

1. Decide the ownership boundary: repository-global vs. `tracks/<track>/knowledge/`.
2. Define the README as the mandatory human and agent entry point.
3. Add a read-only exploration skill/command.
4. Document when the knowledge base must be consulted.
5. Verify the command on a representative track.

---

## 4. Create a Staged Numerical-Experiment Workflow

**Prompt**

```text
Design a user-gated numerical-experiment workflow for this repository. It must support both an end-to-end command and separately invocable stages: MVP implementation, logical verification, small-size smoke test, refactoring into src/tests/scripts, and production parameter scans. The assistant must not advance across stages without user approval. First provide the design and command structure; do not implement yet.
```

**Route**

1. Specify the stages and their pass/fail criteria.
2. Put logical verification before the smoke test.
3. Define the user gate between every stage.
4. Create one command per stage and one orchestrating command.
5. Test that a stage can be invoked independently.

---

## 5. Set Up a Cluster Pipeline Without Exposing Secrets

**Prompt**

```text
Help me prepare a reproducible local-to-Slurm cluster workflow for this project. First inspect the existing cluster and Slurm conventions. Then propose the exact path layout for local source, staged remote inputs, scheduler logs, fetched outputs, and provenance metadata. Do not use or print credentials; I will authenticate separately. Verify the pipeline with a small harmless test job before any production calculation.
```

**Route**

1. Read the project’s cluster and Slurm guidance.
2. Confirm authentication out of band.
3. Create a minimal test script and Slurm job.
4. Upload, submit, poll, and retrieve outputs.
5. Record job ID, resources, commit/version, parameters, and output paths.
6. Only then submit scientific production jobs.

---

## 6. Build and Validate an ED MVP

**Prompt**

```text
In `tracks/ed/<project>`, inspect the existing code and implement a minimal exact-diagonalization MVP for <model>. Use <library>, with the following conventions: <Hamiltonian, size, boundary condition, particle sector, observables>. Do not start a large run. First add a small test or analytic-limit check, run the verification, then run the smallest nontrivial smoke test. Report the files changed, commands run, and result paths.
```

**Route**

1. Read the existing project scripts and conventions.
2. State assumptions about the Hamiltonian and boundary conditions.
3. Implement only the MVP and its direct test.
4. Verify analytic limits and sector dimensions.
5. Smoke-test locally at the smallest meaningful size.
6. Present results and wait for approval before scaling up.

---

## 7. Reproduce a Published Figure Incrementally

**Prompt**

```text
Read the existing `hubbard-pump-2` code and reproduce only the minimal version of <paper figure>. Use the paper’s stated model, parameter path, observables, boundary conditions, and evolution convention. Where the paper is ambiguous, list the ambiguity and make the timestep/configuration explicit. First validate at the smallest size; do not launch a cluster scan until I approve the local result.
```

**Route**

1. Extract definitions and numerical conventions from the paper.
2. Map each requirement to existing source files.
3. Implement the minimal observable/plot.
4. Test a small system and compare qualitative behavior with the figure.
5. Save figures and raw data under a named run directory.
6. Obtain approval before a size or parameter scan.

---

## 8. Scan Spectra to Separate Spin and Charge Manifolds

**Prompt**

```text
Using the existing Rice–Mele–Hubbard ED project, perform a static spectral scan at half filling. Fix `<U>` and `<Delta>`, scan dimerization `<delta range>`, and compute a many-body energy landscape suitable for distinguishing low-energy spin states from higher-energy doublon–holon charge states. This phase is static spectroscopy only: do not add time evolution. Start by implementing and validating the script locally, then show me the local output before proposing a cluster scan.
```

**Route**

1. Inspect the ED basis, symmetry sector, and energy conventions.
2. Define the scan grid and number of eigenvalues.
3. Validate limiting points and expected degeneracies.
4. Run a small local scan and plot the landscape.
5. Review the figure.
6. Submit the approved grid to the cluster and fetch results.

---

## 9. Map Many-Body, Spin, and Charge Gaps

**Prompt**

```text
For the large-U Rice–Mele–Hubbard model, scan the full `(delta, Delta)` plane and compute: (1) the lowest many-body gap in the half-filled zero-magnetization sector, (2) the spin gap, and (3) the charge gap. Use the existing ED conventions. First run a complete `L=6` benchmark locally, verify the boundary-condition parity and expected gapless locus, and only then prepare the `L=10` Slurm run.
```

**Route**

1. Write exact sector definitions for all three gaps.
2. Verify OBC/PBC and bond-parity conventions explicitly.
3. Benchmark all diagnostics locally at small size.
4. Check that known symmetry/gap-closing loci appear where expected.
5. Correct any convention error before cluster submission.
6. Submit and monitor the approved larger-size job.

---

## 10. Diagnose Nonadiabatic Pump Failure Through Current Channels

**Prompt**

```text
Extend the verified time-dependent Rice–Mele–Hubbard pump calculation with instantaneous particle-current diagnostics. Keep all previously validated parameters, initial state, boundary conditions, and time-evolution settings unchanged. Determine when and on which bonds the transported charge deviates from the expected value, distinguishing missing forward current from reverse current. First generate and explain the smallest-size result before scaling up.
```

**Route**

1. Reuse the verified evolution implementation without changing conventions.
2. Define bond-current operators and integrated transported charge.
3. Test the continuity relation numerically.
4. Run the smallest system and inspect time-resolved current plots.
5. Explain deviations using the computed quantities only.
6. Scale to larger sizes after review.

---

## 11. Diagnose Coherence After a Gapless Crossing

**Prompt**

```text
Using the validated time-dependent ED code, diagnose whether pump failure after a gapless crossing arises from coherent phase evolution among nonadiabatically excited instantaneous eigenstates. Compute an instantaneous-eigenbasis current decomposition and a post-crossing waiting-time interference scan for `L = <sizes>`. Do not invoke environmental decoherence, thermalization, or Lindblad dynamics. Show the `L=6` data first and explain the physical interpretation precisely.
```

**Route**

1. Preserve the validated pump path and evolution convention.
2. Project the state and current onto the instantaneous eigenbasis.
3. Confirm numerically that channel contributions reconstruct the total current.
4. Run the smallest size.
5. Separate coherent multi-state interference from environmental decoherence.
6. Approve larger sizes only after the interpretation is checked.

---

## 12. Compute an Interaction Scan of a Many-Body Chern Number

**Prompt**

```text
Add an independent `U_scan_C_solver` experiment to the spinful Rice–Mele–Hubbard ED project. Along the specified unbiased pump path, scan from strong attraction to strong repulsion and compute the adiabatic many-body Chern number together with the relevant gap structure. First validate the discretized Berry-curvature implementation and convergence with grid resolution locally. Do not round Chern numbers when diagnosing the transition point.
```

**Route**

1. Define the parameter torus and gauge-invariant discretization.
2. Test known or noninteracting limits.
3. Run coarse and refined local scans with recorded grid resolution.
4. Compare raw Chern estimates, gaps, and finite-grid uncertainty.
5. Diagnose discrepancies before launching a cluster scan.
6. Archive raw data and plotting code with each run.

---

## 13. Test Independent Spinon–Holon Pumping

**Prompt**

```text
In the existing Rice–Mele–Hubbard ED code, test whether removing one spin-up electron from the half-filled Mott state produces charge and spin defects with different pump-induced displacements. Use static-evolution controls, forward and reverse pump protocols, and a `U=0` control to rule out ordinary wave-packet drift and finite-size effects. Restrict the first stage to an ED proof of principle and report the required observables before implementation.
```

**Route**

1. Define the doped particle and spin sectors.
2. Specify charge and spin center/displacement observables.
3. Design forward, reverse, static, and `U=0` controls.
4. Verify each control at small size.
5. Compare only control-subtracted pump responses.
6. Scale only if the controls support the claimed effect.

---

## 14. Explore Spinon–Holon Binding or Pinning Mechanisms

**Prompt**

```text
Using the existing Rice–Mele–Hubbard model, test whether a pump periodically changes the relative spinon–holon separation and binding length rather than merely producing distinct wave-packet velocities. Use `<L, U, pump radius, period>` and define the separation/binding diagnostics explicitly. Begin with a small ED calculation and include static and reversed-pump controls. Report whether the proposed diagnostic genuinely distinguishes binding dynamics from simple propagation.
```

**Route**

1. Define a measurable separation or correlation-based binding length.
2. Add static and reverse-protocol controls.
3. Validate the diagnostic on simple limiting states.
4. Run the smallest system first.
5. Compare the full time dependence against controls.
6. Only then schedule a parameter grid on the cluster.

---

## 15. Study Doped Low-Energy Bands and Chern Numbers

**Prompt**

```text
Study the low-energy doped many-body band of the Rice–Mele–Hubbard model on the `(K, phi)` torus. Use periodic boundary conditions and two-site translation symmetry to resolve reduced momentum `K`, with particle sector `N = L - 1` and the specified total spin. Determine whether a holon-like or spinon–holon multiplet admits an isolated topological invariant. First demonstrate band isolation and gauge-stable Chern-number evaluation at `L=8`.
```

**Route**

1. Implement and test the symmetry-resolved basis.
2. Identify the candidate low-energy multiplet and its separation from other states.
3. Verify continuity/gauge stability across the parameter mesh.
4. Compute Chern numbers at small size.
5. Report finite-size and multiplet-isolation limitations before extending the study.

---

## 16. Turn Completed Work into a Short Research Report

**Prompt**

```text
Read the completed run artifacts, scripts, and project documentation for `<experiment>`. Produce a concise English research report containing: objective, model and numerical method, validated setup, key results, caveats, and reproducibility paths to scripts/data/figures. Do not claim conclusions that are not supported by the saved outputs.
```

**Route**

1. Locate the exact script version, parameters, logs, raw data, and figures.
2. Cross-check stated results against the saved artifacts.
3. Separate observed results from interpretation.
4. Include only the minimal reproducibility commands and paths.
5. Review the report before sharing externally.

---

## General Handoff Prompt

Use this when moving any task to another person or another Claude session.

```text
Continue this task from the repository state. First read the relevant track README, project knowledge README, source code, tests, run metadata, and the most recent output directory. Do not change model conventions, boundary conditions, or numerical parameters silently. State the current status, the next smallest verifiable action, and the criterion for success. Wait for approval before launching a production cluster job or making irreversible Git changes.
```
