# Detailed Research Narrative Design

**Date:** 2026-07-30
**Status:** approved for implementation
**Language:** English throughout

## Purpose

Issue #265 asks a sharper question than whether a Burgers curve fits one
domain-wall trajectory.  It asks whether the machine-discovered,
constant-coefficient equation is a controlled asymptotic hydrodynamic law of
the isotropic Heisenberg chain or a finite-time, finite-resolution closure.
The public pull request therefore needs to expose the full scientific
argument, the evidentiary limits of the pilot, and the preregistered route to
a decisive answer.

## Chosen structure

The approved design is a layered research package:

1. `README.md` is the entry point.  It states the question, present answer,
   evidence levels, workflow, and reproducibility commands.
2. `SCIENTIFIC_CASE.md` is the long-form research argument.  It connects the
   issue, primary literature, symmetry and averaging constraints, the moment
   bridge, pilot measurements, competing closures, frozen tests, and HPC
   execution.
3. `CURRENT_STATUS.md` is the dated execution ledger.  It separates completed
   evidence from archived cluster observations and future evidence gates.
4. The pull-request body is a self-contained review narrative with links into
   the three repository documents.

## Scientific organization

The narrative is organized by claim strength rather than chronology:

- **Exact:** microscopic continuity, spin-flip constraints on a one-field
  current, and algebraic diagonalization of the equal-coupling two-mode flux.
- **Controlled interpretation:** linear-response relation between a weak wall
  and the equilibrium spin propagator; deterministic rarefaction of the
  fitted scalar equation; nonlinear averaging terms retained by an open
  fluctuating description.
- **Measured pilot evidence:** public-trajectory coefficients, profile error,
  width and moment exponents, and the moment-tangent ratio.
- **Registered confirmatory evidence:** convergence, cross-condition
  transfer, current/correlation/FCS observations, model hierarchy, and blind
  future-time confirmation.

This ordering prevents a high-quality fit from being presented as a
microscopic derivation, while also giving the successful finite-window result
its full positive scientific value.

## Tone and claim boundary

The writing uses constructive comparisons: models are described by the
observables and regimes they organize, and distinctions are stated as
non-equivalence or as registered selection criteria.  The current result is
presented as an established finite-window benchmark.  Confirmatory outcomes
are described as the next evidence-producing stages, without converting
pending simulations into a physics verdict.

## Evidence policy

Every numerical statement must be traceable to a committed report, JSON
record, frozen configuration, or test.  Primary-literature statements link to
the relevant arXiv record.  Cluster status is dated and attributed to the
latest archived evidence; it is not described as live unless refreshed.
