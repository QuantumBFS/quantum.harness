# Capsule Trust and Route Closure Design

## Decision

The current repeat chain is useful evidence that two differently addressed
records were supplied, but it is not trusted evidence that a scheduler ran two
independent attempts. `reproducibility` therefore becomes a
`reported_only` structural diagnostic and is excluded from
`all_required`. A future contract may promote it only when a preregistered
distinct attempt nonce and runner identity are bound to the experiment and
request digests by a trusted scheduler signature/MAC or an external registry
receipt.

The capsule keeps the repeat delta, exact reconstruction, distinct execution
handle, and distinct raw-result identity checks. These checks detect accidental
reuse and stale artifact chains; they do not establish process independence.
Cosmetic byte differences, warning text, or a second self-authored handle do
not increase scientific assurance.

## Route closure

Every experiment accepted by `validate_experiment` must be translatable
without `KeyError` into an exact main-repository TeNPy request and must provide
every observable used by the public gate. Both promoted routes therefore
require `energy` and `variance`; infinite variance remains
`backend_limited`.

Numerics are route-aware. Finite experiments do not contain `min_sweeps` or
`entropy_tolerance`; the translator records the backend-fixed values
`min_sweeps=0` and `entropy_tolerance=null`. Infinite experiments explicitly
preregister both fields and require
`finite_entanglement_fit.max_chi == max_bond_dim == chi_schedule[-1]`.

The infinite Hamiltonian is

`H = Σ_i [Jxy(Sx_i Sx_{i+1} + Sy_i Sy_{i+1}) + Jxy·Delta Sz_i Sz_{i+1} - h Sz_i]`.

`Delta` is dimensionless and the external TN-Agent worker implements
`Jz = Jxy·Delta`. That implementation is not part of this QuantumBFS PR's
standalone trust root, so the public capsule exposes only `Jxy=1`. Non-unit
`Jxy` remains fail-closed until an exact worker source identity or trusted
execution receipt is included in the public evidence boundary.

## Candidate trust boundary

`candidate` is a valid preregistration status, not a scientific verdict. The
current capsule has no trusted runner receipt and no independently checkable
state/certificate evaluator, so `evaluate()` rejects every candidate with
`SCIENTIFIC_EVIDENCE_UNATTESTED`. Only synthetic `test_fixture` documents may
reach fixture-level `ACCEPTANCE_PASSED`; that outcome proves contract closure,
not fresh tensor-network execution or any success tier of issue #133.

## Library grounding

Repository-skill sources resolve only as normalized POSIX paths relative to
the quantum.harness repository root derived from the team directory. Contract
audit evidence resolves only inside the team directory. Validation opens
those files through pinned directory descriptors, rejects traversal,
symlinks, hardlinks, missing files, and content changes, then recomputes the
declared SHA-256.

Contract-audit evidence carries both `uri` and `sha256`; a digest without an
addressable artifact is not grounded. Append-only sequence rules remain local
consistency rules. Publication still requires an external Git commit/tip or
equivalent immutable registry identity; the file alone cannot prove that
history was never rewritten.

## Artifact safety

Every registered artifact must be a stable regular file with exactly one hard
link. The descriptor-based read rejects `st_nlink != 1` before consuming
content and verifies the link count again after reading.

## Test boundary

Tests cover:

- reproduction excluded from required acceptance and retained as
  `reported_only`;
- physics-equal repeat records that differ only in whitespace or warning text
  remain structural diagnostics, never independent reproduction evidence;
- energy/variance dependency closure and stable rejection instead of
  `KeyError`;
- finite backend-fixed `min_sweeps=0`;
- infinite `max_chi == max_bond_dim`;
- non-unit `Jxy` rejected by the standalone capsule while the external worker
  retains its independently tested `Jz=Jxy·Delta` implementation;
- fully rebuilt synthetic candidate evidence remaining scientifically
  unattested;
- source/evidence traversal, tamper, missing-file, and hardlink rejection;
- standalone behavior plus optional main-repository parser/worker
  compatibility.
