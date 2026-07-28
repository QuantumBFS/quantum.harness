# WangTheoPhys: a fail-closed tensor-network research gate

## Team

| | |
|---|---|
| **Team name** | WangTheoPhys |
| **Members** | Junkai Wang, WangTheoPhys@outlook.com |

## Challenge

| Row | |
|---|---|
| **Challenge** | Build an agent for tensor-network research: a research assistant that can mine tensor-network literature, maintain a grounded knowledge base, propose executable research tasks, and support solution workflows. |
| **Catalog issue** | Addresses [#133 — The problem factory](https://github.com/QuantumBFS/quantum.harness/issues/133), released by Jin-Guo Liu. |
| **Track** | `agent-kb`, chosen because the issue's `Method` field is `Other` and this is an AI research-agent / knowledge-base contribution. |

This directory is a deliberately small public review surface for the larger
TN-Agent design. It preregisters scientific intent, binds an exact executable
route, evaluates normalized evidence, and accumulates heuristics without
copying a numerical library or the repository's MPS methodology cards.

## What is implemented

```text
experiment definition
    │  strict JSON, no implicit fields
    ▼
experiment-v1 + exact capability/backend binding
    │  human ratifies physics and gate before compute
    ▼
external TN worker (not bundled here)
    │  primary + repeat request-bound artifact chains
    ▼
evidence-v1 ──> stdlib-only gate.py
                  │  strict parse and identity binding
                  │  deterministic reconstruction of both backend bundles
                  │  locked reference + structural repeat metric derivation
                  │  raw-only diagnostics remain reported-only
                  ▼
             fixture contract closure or stable rejection code
                                      │
                                      ▼
                              append-only heuristics Library
```

The public capsule contains:

- [`contracts/experiment-v1.schema.json`](contracts/experiment-v1.schema.json):
  problem, physics, capability, backend binding, explicit numerics,
  observables, validator assurance policies, acceptance policy, a
  preregistered energy reference, and provenance.
- [`contracts/evidence-v1.schema.json`](contracts/evidence-v1.schema.json):
  immutable experiment identity, matching binding, execution state,
  artifact manifest, observable evidence, validator results, and result
  identity.
- [`contracts/backend-result-v1.schema.json`](contracts/backend-result-v1.schema.json):
  the public JSON form of the main repository's
  `tn_agent.backends.models.BackendResultBundleV1`, including its semantic
  canonical digest.
- [`contracts/validator-evidence-v1.schema.json`](contracts/validator-evidence-v1.schema.json):
  the separately addressed gate-derived validator report. It binds the
  canonical request, both semantic backend-result digests, and the
  preregistered reference artifact.
- [`contracts/energy-reference-v1.schema.json`](contracts/energy-reference-v1.schema.json):
  the registered reference record bound to exact physics, value,
  normalization, method label, citation, and semantic identity. The gate
  verifies this record but does not rerun the cited reference method.
- [`gate.py`](gate.py): a dependency-free Python CLI that rejects duplicate
  keys, non-finite values, missing/unknown fields, unsupported routes,
  mismatched bindings/digests, unsafe artifacts, stale normalized results,
  reused primary/repeat identities, self-contradicting raw metrics, forged
  validator reports, hardlinked files, and failed thresholds.
- [`library/heuristics.jsonl`](library/heuristics.jsonl): append-only,
  revisioned heuristics with source, evidence, confidence, contradiction, and
  supersession fields.
- [`skill/tn-agent-workflow/SKILL.md`](skill/tn-agent-workflow/SKILL.md): a
  thin workflow skill that composes the repository's MPS/TeNPy skills.
- [`fixtures/`](fixtures/) and [`tests/test_gate.py`](tests/test_gate.py):
  compact synthetic finite/infinite examples and negative contract tests.
- [`fixtures/regenerate.py`](fixtures/regenerate.py): deterministic
  regeneration of every synthetic artifact and digest.

The schemas are useful for editors and other agents. `gate.py` is the
executable semantic authority: JSON Schema alone does not compare two
documents, recompute file digests, or evaluate preregistered thresholds.

## Current scientific scope

Only two exact, reviewable routes are promoted:

| Capability | Physics and algorithm | Binding | Maturity |
|---|---|---|---|
| `tenpy.finite_1d.dmrg` | finite spin-1/2 TFIM, open chain, two-site MPS DMRG | `tn-agent.tenpy.finite-tfim-dmrg.v1` → `tenpy.v1` → `tenpy` | stable |
| `tenpy.infinite_1d.vumps` | infinite spin-1/2 XXZ, two-site uniform MPS VUMPS, total Sz=0 | `tn-agent.tenpy.infinite-xxz-vumps.v1` → `tenpy.v1` → `tenpy` | experimental; variance is explicitly backend-limited |

Both routes must request `energy` and `variance`, because those observables
are dependencies of the public gate. Finite experiments do not expose
`min_sweeps` or `entropy_tolerance`; the exact translator supplies the
backend-fixed values `0` and `null`. Infinite experiments preregister both and
must satisfy
`finite_entanglement_fit.max_chi == max_bond_dim == chi_schedule[-1]`.

The infinite route uses
`H = Σ_i[Jxy(Sx_i Sx_{i+1}+Sy_i Sy_{i+1}) + Jxy·Delta Sz_i Sz_{i+1} - h Sz_i]`.
Thus `Delta` is dimensionless and the TeNPy coupling is
`Jz = Jxy·Delta`. This standalone capsule currently promotes only `Jxy=1`:
the corrected general mapping lives in the external TN-Agent worker, which is
not part of this PR's independently reviewable trust root. Non-unit `Jxy`
therefore returns `UNSUPPORTED_ROUTE` until a versioned worker implementation
or trusted execution receipt is included in the public evidence boundary.

Installed packages, catalog entries, and fallback names do not create
capabilities. A request for quimb, YASTN, ITensor, MPSKit, PEPSKit, a different
model, boundary, sector, or algorithm returns `UNSUPPORTED_ROUTE`.

Method knowledge stays in the upstream harness:

- [Method MPS](../../../../skills/method-mps/SKILL.md) owns algorithm choice,
  accuracy knobs, and scientific validation guidance.
- [Using TeNPy](../../../../skills/using-tenpy/SKILL.md) owns TeNPy setup and
  API-specific workflow.

This solution links those sources and records their SHA-256 identities in
fixtures and Library records; it does not duplicate their method content.

## Run the public gate

From the repository root:

```bash
TN_PUBLIC_ROOT=tracks/agent-kb/solutions/WangTheoPhys

python3 "$TN_PUBLIC_ROOT/gate.py" validate \
  "$TN_PUBLIC_ROOT/fixtures/valid-finite/experiment.json"

python3 "$TN_PUBLIC_ROOT/gate.py" evaluate \
  "$TN_PUBLIC_ROOT/fixtures/valid-infinite/experiment.json" \
  "$TN_PUBLIC_ROOT/fixtures/valid-infinite/evidence.json" \
  --artifact-root "$TN_PUBLIC_ROOT/fixtures/valid-infinite/artifacts"

python3 "$TN_PUBLIC_ROOT/gate.py" validate-library \
  "$TN_PUBLIC_ROOT/library/heuristics.jsonl"
```

Every operational command writes exactly one compact JSON object to stdout.
Standard argparse `--help` is the sole human-readable exception. Exit status
`0` means the requested validation/evaluation passed, `2` means an input or
contract was invalid, and `3` means well-shaped evidence did not satisfy the
preregistered experiment. Every exit-3 JSON result includes
`"accepted": false`.

Run the direct test suite:

```bash
python3 -m unittest discover \
  -s tracks/agent-kb/solutions/WangTheoPhys/tests -v
```

The `test_fixture` documents are synthetic contract tests. Their
`ACCEPTANCE_PASSED` verdict demonstrates contract-level closure through
eleven required artifacts: one
request; primary and repeat raw/normalized result pairs; a preregistered
energy-reference record; validator evidence; and primary/repeat stdout and
stderr. Both request fixtures are parsed by the main repository's
`parse_tenpy_request_json`; all four normalized fixtures are parsed by
`BackendResultBundleV1.model_validate_json` and its Python-mode
`model_validate` path, and both requests pass the main worker's route-specific
request validation. The synthetic primary and repeat records are generated by
the same fixture script, so they test structural separation only. They are not
independent numerical runs, a new physics result, or challenge-tier evidence.

A `candidate` remains a valid frozen experiment definition, but this capsule
returns `SCIENTIFIC_EVIDENCE_UNATTESTED` for candidate evaluation because it
does not bundle a trusted runner receipt or independently checkable state
certificate. Rebuilding all candidate artifacts and digests cannot turn
worker assertions into scientific acceptance.

## Identity and acceptance

All identities use lowercase `sha256:<64 hex>`.

- `problem.status=test_fixture` is required for fixture-level
  `ACCEPTANCE_PASSED`. A validated `candidate` is always scientifically
  rejected as unattested by this contract version.
- `experiment_digest` is SHA-256 over canonical UTF-8 JSON for the complete
  experiment (`sort_keys=true`, compact separators, no NaN/Infinity).
- The outer evidence `result_digest`, both main-model backend
  `result_digest` values, the energy-reference `result_digest`, and
  validator-evidence `result_digest` each use the same canonical algorithm
  over their respective object with only that object's `result_digest`
  omitted. They are semantic identities, not raw-file identities.
- Artifact digests cover the raw file bytes. Evaluation pins one non-symlink
  artifact-root directory descriptor, opens every relative component without
  following symlinks, rejects files whose hard-link count is not exactly one,
  and recomputes bounded regular files' size and digest.
- Every observable points to the primary normalized backend-result artifact.
  Every validator result points to the separate validator-evidence artifact.
- The gate reconstructs the exact main-repository `BackendResultBundleV1`
  twice, from one canonical request and two distinct raw/execution/stream
  chains. Both submitted normalized bundles must be canonical-identical to
  those reconstructions. Execution handles and raw-result identities must
  differ. This proves artifact-level separation; it cannot prove that two
  external processes were scheduled independently.
- The experiment locks the energy value, units, normalization, and byte
  digest of a separate reference record. The record also binds the exact
  physics digest. `benchmark_delta` is derived only from primary energy versus
  that locked reference; a worker-supplied benchmark value has no authority.
- `reproduction_delta` is derived only from primary versus repeat raw energy.
  It cannot be supplied in the primary raw result. It is a structural,
  `reported_only` diagnostic with no operator or threshold and does not
  contribute to `ACCEPTANCE_PASSED`.
- Energy drift is derived from the last two primary convergence energies. A
  reported drift, when present, must agree, but it does not create an
  independent physics certificate.
- Variance, canonical residual, and symmetry residual cannot be recomputed
  without a state or certificate. They therefore have `reported_only` status
  (or `backend_limited` for infinite-route variance), carry no acceptance
  threshold, and are excluded from `all_required`.
- Only parse consistency, convergence, reference comparison, and artifact
  completeness are `required_pass`. They must report `pass` and satisfy the
  exact preregistered threshold.

Reproduction may be promoted in a future contract only when the experiment
preregisters a distinct attempt nonce and runner identity and a trusted
scheduler signature/MAC or external registry receipt binds those fields to
both the experiment and request digests. Byte differences, warning text,
self-authored handles, or a second locally generated bundle do not satisfy
that requirement.

There is no fallback parser, route, backend, validator, artifact, or success
classification. The public outcome vocabulary is documented in
[`contracts/reason-codes.md`](contracts/reason-codes.md).

## Accumulating Library

[`library/README.md`](library/README.md) defines the append protocol. Records
are never edited or deleted. A correction is a new consecutive revision that
names the immediately prior revision in `supersedes`; a disagreement names
only earlier records in `contradicts`. The gate derives the effective latest
record without erasing history.

Every source and evidence entry carries an addressable, kind-checked `uri`
plus SHA-256. Repository skills and method/workflow cards must be exact
`skills/<normalized-name>/SKILL.md` paths relative to the repository root;
contract audits must be regular files below this team's `docs/` or `tests/`
directory. The gate opens and hashes those paths through confined directory
descriptors.
These checks establish local content identity, not historical immutability;
published Library state must also freeze an external Git commit/tip or
equivalent registry identity.

The seed entries are grounded workflow heuristics, not benchmark results.
Future solver attempts—success or failure—should append evidence-bearing
records so the growth curve is auditable.

## Status against issue #133

| Issue #133 requirement | Status in this PR |
|---|---|
| Versioned candidate problem with executable gate | **Candidate preregistration is implemented; candidate scientific acceptance is intentionally rejected without attestation** |
| Pre-registered, machine-checkable acceptance | **Implemented only for synthetic fixture contract closure, not a fresh candidate solve** |
| Provenance and reproducible evidence identities | **Implemented at contract/artifact level; trusted execution identity is not implemented** |
| Accumulating heuristics Library | **Schema, append protocol, validator, and seed records implemented** |
| Literature-mining problem generator | **Not yet implemented here** |
| Calibration against challenges #124–#128 | **Not run** |
| Five new human-accepted challenge problems (Tier 1) | **Not claimed** |
| Five fresh solved gates (Tier 2) | **Not claimed** |
| Refereed publication (Tier 3) | **Not claimed** |

**This PR achieves no success tier of issue #133.** It supplies a fail-closed
contract and fixture evaluator that can support a future independently
executed candidate; it does not claim a fresh solve, an accepted new problem,
or a publication result.

The next scientifically meaningful milestone is to use this contract to
generate one real candidate, freeze its gate before solving, publish its
generation/rejection log, and submit it for independent human review. Scaling
to five candidates should follow only after that first calibration survives.

## Scope and licensing

No third-party source code, model weights, papers, or numerical artifacts are
vendored here; the compact numerical files are synthetic contract fixtures.
This directory follows the upstream `quantum.harness` repository terms and
does not add a standalone or conflicting license. See
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) for referenced external
projects and repository documents.
