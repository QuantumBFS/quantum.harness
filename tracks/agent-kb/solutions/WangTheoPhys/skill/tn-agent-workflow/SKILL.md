---
name: wangtheophys-tn-agent-workflow
description: Use when proposing or auditing a tensor-network research problem through the WangTheoPhys public experiment contract, exact promoted TeNPy bindings, executable evidence gate, and append-only heuristics Library.
---

# WangTheoPhys TN-Agent workflow

Use this Skill as a thin orchestrator. It does not own MPS methodology or
TeNPy API guidance:

- Read `skills/method-mps/SKILL.md` for algorithm selection and scientific
  validation.
- Read `skills/using-tenpy/SKILL.md` only after TeNPy is the selected tool.
- Use this team's `contracts/experiment-v1.schema.json`,
  `contracts/evidence-v1.schema.json`, and `gate.py` for preregistration and
  evaluation.

## Propose

1. State the exact Hamiltonian and sign convention, chain geometry and
   boundary, symmetry sector, target observable, and system size or unit cell.
2. Ask the human to ratify that setup before any compute.
3. Create a new experiment JSON with every field explicit. Do not add a
   fallback backend or infer omitted physics/numerics.
4. Register an energy-reference artifact before execution and freeze its
   value, normalization, physics digest, byte digest, method label, and
   citation in the experiment. The public gate verifies this identity; it
   does not rerun the reference method.
5. Mark synthetic tests as `test_fixture`; only a real proposed problem may
   use `candidate`.

## Validate and freeze

From the repository root, run:

```bash
python3 tracks/agent-kb/solutions/WangTheoPhys/gate.py validate EXPERIMENT.json
```

Report the canonical `experiment_digest`, capability, exact backend binding,
maturity, limitations, validator set, and thresholds. Stop on any nonzero
exit. `UNSUPPORTED_ROUTE` means adapter/validator promotion work is required;
it never authorizes a substitute route.

The two public capabilities are intentionally narrow. Consult the executable
gate for their exact shapes rather than copying route rules into a prompt.
Both routes require `energy` and `variance`. Finite `min_sweeps=0` and
`entropy_tolerance=null` are backend-fixed request values, not configurable
experiment fields. Infinite fit closure requires
`max_chi == max_bond_dim == chi_schedule[-1]`, and its XXZ convention is
`Jz=Jxy*Delta`. This standalone public capsule promotes only `Jxy=1` because
the external worker that implements the general mapping is outside this PR's
trust root. Treat non-unit `Jxy` as `UNSUPPORTED_ROUTE` until a versioned
worker or trusted execution receipt is included in the evidence boundary.

## Execute outside this capsule

This directory does not run tensor-network numerics. Hand the validated,
human-ratified experiment to an execution system that preserves:

- the canonical experiment digest;
- immutable capability/adapter/backend binding;
- one request accepted by the main repository's
  `parse_tenpy_request_json`;
- two strict normalized `tn-agent.backend-result.v1` bundles accepted by
  `BackendResultBundleV1`, each with the raw bounded result it identifies;
- distinct primary/repeat execution handles and raw-result byte identities;
- byte-addressed request, primary/repeat raw results, primary/repeat
  normalized results, reference, validator-evidence, and primary/repeat
  stdout/stderr artifacts;
- explicit required, reported-only, and backend-limited validator results
  plus both execution-stream digest pairs.

A process exit code, plot, or scalar value is not a scientific verdict. The
gate enforces structurally distinct repeat records and handles but cannot
prove scheduler-level independence; repeat consistency remains
`reported_only` with no threshold. Future promotion requires a preregistered
distinct attempt nonce and runner identity plus a trusted scheduler
signature/MAC or external registry receipt binding them to the experiment and
request digests.

## Evaluate

Run the evidence gate with the explicit artifact root:

```bash
python3 tracks/agent-kb/solutions/WangTheoPhys/gate.py evaluate \
  EXPERIMENT.json EVIDENCE.json --artifact-root ARTIFACT_ROOT
```

Only `ACCEPTANCE_PASSED` is acceptance. Preserve any other stable reason code;
do not weaken a digest, binding, artifact, validator, or threshold check.
`candidate` evaluation always returns `SCIENTIFIC_EVIDENCE_UNATTESTED` in this
contract version. `ACCEPTANCE_PASSED` is reserved for synthetic
`test_fixture` contract closure and is not evidence of a fresh solver run or
an issue #133 success tier.
The gate reparses the raw result, reconstructs the canonical main-model
backend bundles for primary and repeat, derives benchmark comparison from the
preregistered reference, derives reproducibility from the repeat raw result,
and compares the separate validator artifact. Reproducibility, variance,
canonical residual, and symmetry residual are reported-only unless a future
contract registers the required trusted receipt or state/certificate
evaluator; infinite variance is backend-limited. Do not promote those values
or derive acceptance from a worker's normalized pass or self-reported metric
alone.

## Learn

After every accepted or rejected attempt:

1. Distill one reusable claim and one concrete action.
2. Cite a confined source/evidence URI and its recomputed SHA-256.
3. Calibrate confidence and record contradictions.
4. Append a new JSONL line; never edit history.
5. For a correction, increment the revision and supersede the immediately
   prior revision.
6. Run `gate.py validate-library` before reporting the Library update.
7. Freeze the published Library state with an external Git commit/tip or
   equivalent immutable registry identity.

Lead the handoff with the accepted/rejected outcome, experiment/result
digests, exact route, verified artifact count, and the newly appended
heuristic record (if any).
