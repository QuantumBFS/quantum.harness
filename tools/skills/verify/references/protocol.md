# protocol

Compare `protocol.toml` against declared primary sources.

| Axis | Pass condition |
|---|---|
| Source | Paper-derived claims use `primary`; hints require explicit assumption. |
| Claims | Each non-assumption claim cites a primary passage. |
| Checks | Each non-assumption claim has a check or justified deviation. |
| Shape | Check kinds are one of `audit`, `run`, `exists`, `agree`, `near`, `fresh`, `cover`, `support`; ids are unique. |
| Cells | Each executable cell declares `method`, `stack`, `route`, `source`, `check`, `state`, and `scope`. |
| Route | `paper`, `canonical`, `fallback`, and `deviation` have the required authority; installed-library availability is not authority. |
| Figure semantics | Figure entries name paper-defined metric/observable, basis or representation, overlap bra/ket or operator objects, state-selection rule, sector, window, normalization, excluded nearby states, and proxy validation/deviation. |
| Deviation | Paper/setup/budget/scope differences are scoped, claim-tagged, and checked. |
| Repair | Contract-changing edits record `from`, `wrong`, `changed`, `invalidate`, and `state`. |
| Gates | Every template gate has checks sufficient to block stale or unsupported artifacts. |

Severity tags: `supported`, `unsupported`, `hint-leak`, `assumption`, `deviation`, `repair`, `missing-check`, `missing-route`, `unsupported-route`, `non-generic`, `proxy`, `state-mismatch`.
