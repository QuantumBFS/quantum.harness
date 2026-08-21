# Issue #147 Deadline Technical Report Design

## Goal

Produce one self-contained Chinese HTML report that a challenge judge can read
offline and audit. The report must make the thermodynamic-targeted PEPO idea
look scientifically promising without claiming that the mandatory benchmark is
complete.

## Audience And Claim

The primary reader is a technically literate hackathon judge who may spend only
one to three minutes on the first pass. The headline claim is:

> The project delivers a reproducible finite-temperature PEPO prototype with a
> thermodynamic-aware compression objective and independent ED/QMC validation;
> the complete beta and bond-dimension benchmark remains unfinished.

The report must never claim an accuracy improvement over ordinary PEPO because
no matched ordinary production data exists and both retained PEPO checkpoints
accepted zero optimizer updates.

## Structure

1. Hero: project name, evidence status, strongest metrics, and one-sentence
   verdict.
2. Challenge map: mandatory deliverables marked complete, partial, or missing.
3. Physical setup: exact Hamiltonian, 10x10 open lattice, conventions, and
   thermodynamic observables.
4. Innovation: finite-capacity PEPO as information allocation; ordinary
   Frobenius compression versus the proposed z/u/Hermiticity-aware objective;
   falsifiable predictions and novelty caveat.
5. Method: Trotter evolution, teacher-student compression, boundary-MPS
   contraction, immutable checkpoints, and independent ED/QMC routes.
6. Evidence: the four deadline figures, each with what it proves and what it
   does not prove.
7. Verification and provenance: QMC acceptance gates, ED state count and file
   hash, PEPO checkpoint hashes, tests, and source artifact paths.
8. Limitations and roadmap: ordinary ablation, beta range, f/u/C curves,
   D/chi/delta-beta convergence, and accuracy-cost comparison.
9. Reproduction: one command to regenerate the deadline figures and direct
   links to source entry points and CSV tables.

## Evidence Rules

- Use only completed validated local outputs.
- Distinguish 4x4 ED from 10x10 PEPO/QMC in every relevant caption.
- Identify the PEPO result as a two-step feasibility probe at beta 0.025 and
  0.05, outside the challenge benchmark interval.
- State uncertainty types: QMC finite-M bars are block-bootstrap standard
  errors; the zero-step interval is a 95% bootstrap confidence interval.
- Treat zero accepted optimizer updates as a limitation, not a convergence
  result.
- Do not interpolate missing thermodynamic data or calculate specific heat
  from two PEPO points.

## Artifacts

The report directory is
`tracks/peps/results/issue147-four-figure-deadline/`. It contains `report.json`,
the rendered `report.html`, four PNG/PDF figure pairs, four CSV evidence tables,
and the existing README. The HTML embeds every displayed figure and all styles,
so it opens without a server or network connection.

## Acceptance

- The report renders successfully with the repository report renderer.
- All four embedded images are present and nonblank.
- Every numerical headline is traceable to a CSV, analysis JSON, or checkpoint
  metadata file named in the report.
- The innovation is presented as a testable research hypothesis rather than a
  demonstrated superiority claim.
- The challenge checklist is visible before the detailed method discussion.
- The HTML is readable at desktop and mobile widths and prints without relying
  on network assets.
