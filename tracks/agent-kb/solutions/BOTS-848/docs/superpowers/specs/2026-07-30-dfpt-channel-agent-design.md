# DFPT Channel Research Agent Design

> Historical design record. The current four-channel and finite-q contract is
> defined by `2026-07-30-final-audit-fixes-design.md`, which supersedes the
> original three-channel decomposition below.

## Objective

Turn the BOTS:848 literature study into a reviewable AI-for-science artifact. The submission must do more than present a physics report: it must give an agent a traceable knowledge base, an explicit scientific decision procedure, a small executable prediction prototype, and an evaluation that exposes unsupported conclusions.

The working hypothesis is deliberately falsifiable: the leading error of static DFPT is controlled by the weight of a phonon perturbation in charge, on-site internal, and nonlocal operator channels, together with each channel's static amplification and frequency dependence. Strong correlation alone is not a failure criterion.

## Architecture

The solution has five independent parts:

1. `report/` preserves the source-backed derivation, material comparisons, caveats, and two-day research protocol.
2. `knowledge/` stores claims and material-mode cases as machine-readable records with source IDs, status labels, normalization notes, and limitations.
3. `agent/` defines a reusable research workflow: retrieve evidence, classify claims, decompose the perturbation, choose a correction level, and state a falsification test.
4. `src/` implements a dependency-free reference model. It decomposes a finite Hermitian operator into local common-charge, local traceless-internal, and off-site nonlocal parts; applies channel kernels; and returns a guarded recommendation.
5. `eval/`, `examples/`, and `tests/` make the scientific contract executable.

## Data Flow

Literature records enter the claim ledger with one of four statuses: `exact-constraint`, `numerical-evidence`, `working-hypothesis`, or `open-question`. The agent may use an exact constraint directly, but it must not promote numerical evidence to a theorem. A projected DFPT perturbation is then decomposed as

`D = D_charge + D_internal + D_nonlocal`.

Squared Frobenius norms, optionally after projection into a supplied low-energy basis, define normalized channel weights. A decision gate combines these weights with three pieces of evidence: source traceability, validity of the electronic reference state, and the ratio of phonon energy to the electronic relaxation scale. It returns exactly one of `dfpt-safe`, `static-correction`, `dynamic-correction`, or `abstain` with reasons.

The gate is a research triage rule, not a trained accuracy guarantee. Its thresholds are explicit calibration parameters and the report defines how the hypothesis can fail.

## Interfaces

- `decompose_operator(operator, site_blocks)` returns the three operators and requires the blocks to partition a square Hermitian matrix.
- `channel_weights(channels, basis_vectors=None)` returns nonnegative weights summing to one for a nonzero perturbation.
- `correct_operator(dfpt_operator, site_blocks, kernels)` applies one scalar kernel per channel; kernels equal to one reproduce the input exactly.
- `select_correction_level(weights, evidence, thresholds=None)` returns a serializable decision record and abstains when required evidence is absent.

All matrices are nested Python sequences and use only the standard library. This keeps the reviewer command runnable without installing a scientific Python stack.

## Error Handling and Scientific Guardrails

- Reject non-square, non-Hermitian, overlapping, incomplete, or out-of-range site blocks.
- Reject missing or unknown channel kernels and negative channel weights.
- Treat a zero perturbation as zero weight in every channel and do not call it DFPT-safe.
- Abstain if sources are not traceable, the reference state is invalid, or the energy-scale evidence is absent.
- Keep the Ward identity restricted to the conserved long-wavelength charge limit; it is not accepted as a universal proof of DFPT.
- Store reported numbers with the source's units and a normalization caveat instead of silently comparing unlike definitions.

## Verification

Unit tests cover exact reconstruction, on-site tracelessness, Hermiticity, invariance of channel weights under local unitary rotations, identity-kernel recovery, toy charge and orbital-splitting classifications, and evidence-driven abstention. The evaluation checks decision cases, knowledge-schema completeness, citation coverage, and unsupported-claim rate. The report is rebuilt from source, and a final git audit confirms that every change remains below `tracks/agent-kb/solutions/BOTS-848/`.

## Scope

This submission is a minimum viable prediction framework. It does not claim fitted channel kernels, production Wannier interfaces, or universal numerical accuracy. The first final validation target remains the finite-momentum uniform electron gas, followed by held-out material-mode comparisons.
