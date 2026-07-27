## Team

| | |
|---|---|
| **Team name** | Rewrite It In Rust! |
| **Members** | Chenxi Wan, Yedi Shen, Junkai Wang |

## Challenge

| Row | |
|---|---|
| **Challenge** | Develop design notes and a small prototype path toward a Rust-inspired certified tensor DSL where tensor computation, resource discipline, and proof obligations share one kernel. |
| **Catalog issue** | Addresses #82 — "All in one: a native language for code + theorem + proof", released by Huanhai ZHOU. |
| **Track** | `agent-kb`, chosen by the team because the issue's `Method` field is `Other` and the work is agent-native language and verification infrastructure. |

## Scope Note

This registration starts from a conservative design track. The immediate output
is a Rust-inspired typed tensor DSL design memo grounded in the #129 ED/FCI
workbench and the #114 tensor-library verification line, before committing to a
full native language implementation.

## Working Repository

Development starts in the private AGPL-3.0 repository
`JunkaiWang-TheoPhy/quantum-harness-82-certified-tensor-dsl`, with initial
design notes and a small Rust prototype crate under `prototype/`.
