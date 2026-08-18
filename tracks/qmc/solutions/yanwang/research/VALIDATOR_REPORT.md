# Validator Self-Test Report

Date: 2026-07-27

Status: **PASS as draft host validator; pending protocol review and container rerun**

## Environment

- Python: `3.14.3`
- Docker: unavailable
- macOS sandbox: `/usr/bin/sandbox-exec`
- third-party Python dependencies: none
- per-case timeout: 2 seconds
- network: denied by sandbox profile
- user workspace, peer temporary files, and system credential reads: denied
  except for the candidate and supplied input

## Commands

```sh
for f in research/schema/*.json \
         research/validator/manifest.json \
         research/validator/dev/*.json
do
  python3 -m json.tool "$f" >/dev/null
done

research/validator/validate --self-test
research/validator/validate \
  research/validator/reference_candidate \
  --suite dev

research/validator/validate \
  --attempt-kind ed-oracle \
  WORKTREE \
  --out WORKTREE/report.json
```

## Results

| Test | Expected | Observed |
|---|---|---|
| reference candidate | pass | pass |
| wrong answer | fail numeric/oracle comparison | fail |
| dev-ID cheater | fail unseen transformed cases | fail |
| infinite loop | hard timeout | fail by timeout |
| file/network escape | sandbox denial | fail by sandbox/runtime error |
| visible development suite | 3/3 | 3/3 |
| missing ED implementation | fail fixed scientific interface check | fail |

The self-test private cases are ephemeral and do not consume the scientific
holdout budget. The user authorized the pilot validator gate on 2026-07-27.
The production validator gate remains locked because `sandbox-exec` is not a
container/VM boundary.

The `ed-oracle` scientific mode executes a checker stored outside the candidate
worktree, under the same network/file sandbox and the `STATE.md` hard
wall-time. It scores fixed graph, matrix-invariant, infinite-temperature,
independent-spin, and classical-limit tests and writes the machine-readable
attempt `report.json`.

## Interpretation

This result validates the validator's behavior and negative controls. It does
not validate a QMC result, the ED implementation, the FSS pipeline, or the
claim about \(\sqrt5\).
