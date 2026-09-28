# Detailed Research Narrative Design

**Date:** 2026-07-30
**Status:** approved for implementation
**Language:** English throughout

## Purpose

Issue #265 asks which hydrodynamic scope belongs to the machine-discovered
constant-coefficient Burgers equation: a transferable asymptotic law, a
chiral-mode law, or a finite-window effective closure.  The public pull
request presents the full scientific argument, the demonstrated scope of the
pilot, and the preregistered route to a decisive classification.

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

The narrative is organized by claim strength:

- **Exact:** microscopic continuity, spin-flip constraints on a one-field
  current, and algebraic diagonalization of the equal-coupling two-mode flux.
- **Controlled interpretation:** linear-response relation between a weak wall
  and the equilibrium spin propagator; deterministic rarefaction of the
  fitted scalar equation; nonlinear averaging terms retained by an open
  fluctuating description.
- **Measured pilot evidence:** public-trajectory coefficients, profile relative difference,
  width and moment exponents, and the moment-tangent ratio.
- **Registered confirmatory evidence:** convergence, cross-condition
   transfer, current/correlation/FCS observations, model hierarchy, and sealed
  future-time confirmation.

This ordering gives the successful finite-window result its full scientific
value and assigns every broader statement to its own evidence gate.

## Tone and claim boundary

The writing uses constructive comparisons.  Models are described by the
observables and regimes they organize, while distinctions appear as
registered selection criteria.  The current result is an established
finite-window benchmark.  Confirmatory outcomes appear as the next
evidence-producing stages.

## Evidence policy

Every numerical statement is traceable to a committed report, JSON record,
frozen configuration, or test.  Primary-literature statements link to the
relevant arXiv record.  Cluster status is dated and attributed to the latest
archived evidence.  A refreshed scheduler readout becomes a new dated record.

## Positive-language policy

Public prose uses three sentence types: established evidence, current research
stage, and the next action that creates evidence.  Scientific distinctions are
expressed through field identity, domain of validity, registered eligibility,
and quantitative thresholds.  Machine-compatible internal status labels stay
inside JSON records and source interfaces; reader-facing Markdown translates
them into stage descriptions.
