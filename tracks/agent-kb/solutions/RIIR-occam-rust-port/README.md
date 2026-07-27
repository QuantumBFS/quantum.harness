## Team

| | |
|---|---|
| **Team name** | Rewrite It In Rust! |
| **Members** | Chenxi Wan, Yedi Shen, Junkai Wang |

## Challenge

| Row | |
|---|---|
| **Challenge** | Port the Occam's Circuit verifier workflow to Rust: reuse the #71 Julia data and verifier as an oracle, implement a Rust netlist parser/evaluator, add bit-parallel verification, and report correctness/runtime gaps. |
| **Catalog issue** | Addresses #115 — "Port any challenge of this school to Rust", released by Hiroshi Shinaoka. The source challenge for the port is #71, "Occam's Circuit". |
| **Track** | `agent-kb`, chosen by the team because #115 is an agentic migration and Rust-ecosystem case study with `Method` field `Other`. |

## Scope Note

This registration targets the #115 migration deliverable, not a full solution of
the hardest #71 hidden-function discovery task. The first milestone is a
bit-exact Rust verifier and benchmark report against the original Julia
workflow.

## Working Repository

Development starts in the private AGPL-3.0 repository
`JunkaiWang-TheoPhy/quantum-harness-115-occam-rust-port`. The #71 implementation
line lives under the `challenge-71-occam/` subfolder.
