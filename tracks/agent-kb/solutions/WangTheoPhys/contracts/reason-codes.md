# Public gate reason codes

`gate.py` emits one stable `reason_code`. Codes do not contain local paths,
environment values, exception messages, or rejected input.

## Successful outcomes

| Code | Meaning |
|---|---|
| `OK` | A document or Library passed validation. |
| `ACCEPTANCE_PASSED` | Evidence matched the experiment and every acceptance condition passed. |

Evidence documents use `VALIDATOR_PASS` for a successful required validator,
`REPORTED_ONLY` for a bound diagnostic that cannot affect acceptance, and
`BACKEND_LIMITED` only for a limitation preregistered by the route.

## Document and structure rejection

| Code | Meaning |
|---|---|
| `DOCUMENT_DUPLICATE_KEY` | Strict JSON found a duplicate object key. |
| `DOCUMENT_NONFINITE` | NaN or Infinity was present. |
| `DOCUMENT_INVALID_JSON` / `DOCUMENT_INVALID_UTF8` | The bytes are not the accepted JSON encoding. |
| `DOCUMENT_IO_ERROR` / `DOCUMENT_UNSAFE_PATH` / `DOCUMENT_TOO_LARGE` | The input was unreadable, not a regular non-symlink file, or over the limit. |
| `DOCUMENT_NOT_CANONICAL` | A value cannot be represented as canonical JSON. |
| `CLI_USAGE_ERROR` | The command line is incomplete or contains an unsupported argument. |
| `INTERNAL_ERROR` | An unexpected implementation failure was converted to a sanitized JSON rejection; no traceback is exposed. |
| `SECURE_FILE_IO_UNAVAILABLE` | The platform cannot provide the required no-follow read primitive. No unsafe compatibility mode is used. |
| `SCHEMA_VERSION_UNSUPPORTED` | The exact version is not supported. |
| `UNKNOWN_FIELD` / `MISSING_FIELD` | The object is lossy or incomplete. |
| `TYPE_MISMATCH` / `VALUE_INVALID` | A field has the wrong JSON type or violates a closed value constraint. |

## Scientific authority and acceptance rejection

| Code | Meaning |
|---|---|
| `UNSUPPORTED_ROUTE` | The requested physics/algorithm combination is not one of the two promoted capabilities. |
| `SCIENTIFIC_EVIDENCE_UNATTESTED` | A valid candidate definition lacks a trusted runner receipt or independently checkable state certificate, so it cannot receive scientific acceptance. |
| `BINDING_MISMATCH` | Capability, adapter, backend, or request/result schema differs from the preregistration. |
| `EXPERIMENT_DIGEST_MISMATCH` / `RESULT_DIGEST_MISMATCH` | Canonical content does not match its claimed identity. |
| `EXECUTION_NOT_SUCCEEDED` | Execution is not a successful, non-retryable terminal result. |
| `PROVENANCE_MISMATCH` | Plan, request, generator, raw-result, or normalized-result identities do not form the registered chain. |
| `OBSERVABLE_SET_MISMATCH` / `OBSERVABLE_STATUS_INVALID` | Observable evidence is missing, extra, or incorrectly classified. |
| `VALIDATOR_SET_MISMATCH` / `VALIDATOR_POLICY_MISMATCH` | Validator evidence or preregistration policy differs from the route contract. |
| `VALIDATOR_STATUS_INVALID` / `VALIDATOR_FAILED` | A validator result is internally inconsistent or did not pass. |
| `VALIDATOR_THRESHOLD_FAILED` | A metric violates its preregistered `max`, `min`, or `equals` threshold. |
| `ACCEPTANCE_CONTRACT_INVALID` | Required, reported-only, and backend-limited validator sets do not close exactly. |
| `EVIDENCE_ARTIFACT_MISSING` | Evidence points to a digest that was not verified from disk. |

## Artifact and Library rejection

| Code | Meaning |
|---|---|
| `ARTIFACT_IO_ERROR` / `ARTIFACT_UNSAFE_PATH` | An artifact cannot be read safely under the explicit root. |
| `ARTIFACT_TOO_LARGE` / `ARTIFACT_LIMIT_EXCEEDED` | Per-file, count, or aggregate limits were exceeded. |
| `ARTIFACT_DIGEST_MISMATCH` | Raw bytes or size differ from the evidence manifest. |
| `LIBRARY_RECORD_INVALID` / `LIBRARY_RECORD_LIMIT` | A JSONL record is invalid or the record limit was exceeded. |
| `LIBRARY_SEQUENCE_INVALID` | Append order, revision sequence, contradiction, or supersession history is invalid. |

Exit status `2` is a document/contract rejection. Exit status `3` is evidence
that cannot pass the preregistered contract and its JSON output includes
`"accepted": false`. A successful command exits `0`.
