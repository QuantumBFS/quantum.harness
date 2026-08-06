# Heuristics Library

`heuristics.jsonl` is an append-only scientific memory. Each line is one
complete `wangtheophys.tn-heuristic.v1` record validated by
`heuristic-v1.schema.json` and the cross-record rules in `gate.py`.

## Append protocol

1. Never edit, reorder, or delete a published line.
2. A new `heuristic_id` starts at revision `1`; `record_id` is exactly
   `<heuristic_id>@<revision>`.
3. Revisions for one heuristic are consecutive. Revision N's `supersedes`
   array must contain exactly revision N−1 of that same heuristic; it cannot
   supersede an unrelated heuristic.
4. `contradicts` and `supersedes` may reference only records appearing
   earlier in the file. A record cannot both contradict and supersede the same
   record.
5. Every revision repeats its applicability, claim, action, source, evidence,
   calibrated confidence, and status. Nothing is inherited silently.
6. A failed attempt is valid evidence. Record what was learned without
   relabeling failure as success.
7. `repository_skill` source URIs and `method_card`/`workflow_card` evidence
   URIs are exact `skills/<normalized-name>/SKILL.md` repository-relative
   paths. `contract_audit` evidence URIs must name a regular file below this
   team's `docs/` or `tests/` directory. Every URI has a recomputed SHA-256;
   kind/path confusion, traversal, missing files, symlinks, hardlinks, and
   digest mismatches are rejected.

`claim_status` describes the claim at the moment that revision was appended.
The effective current record is the last revision that has not been
superseded by a later line; history remains visible.

Validate after every append:

```bash
python3 tracks/agent-kb/solutions/WangTheoPhys/gate.py validate-library \
  tracks/agent-kb/solutions/WangTheoPhys/library/heuristics.jsonl
```

The seed records cite the repository's existing method/tool skills. They are
workflow heuristics, not new numerical anchors.

The local sequence validator proves internal ordering and cross-reference
consistency only. It cannot prove that a published file was never rewritten.
Every release must also pin the Library to an external Git commit/tip or an
equivalent immutable registry receipt.
