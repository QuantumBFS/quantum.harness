## Team

| | |
|---|---|
| **Team name** | Ranger |
| **Members** | Chenxi Wan, Yedi Shen, Junkai Wang |

## Challenge

| Row | |
|---|---|
| **Challenge** | Port the Occam's Circuit verifier workflow to Rust: reuse the #71 Julia data and verifier as an oracle, implement a Rust netlist parser/evaluator, add bit-parallel verification, and report correctness/runtime gaps. |
| **Catalog issue** | Addresses #115 — "Port any challenge of this school to Rust", released by Hiroshi Shinaoka. The source challenge for the port is #71, "Occam's Circuit". |
| **Track** | `agent-kb`, chosen by the team because #115 is an agentic migration and Rust-ecosystem case study with `Method` field `Other`. |

## Scope Note

**Status: Completed — v0.5.0 (July 28, 2026).**

The completed #115 migration now includes the bit-exact Rust verifier,
bit-parallel and compiled evaluation backends, deterministic benchmark and
evidence pipelines, pinned ABC/Yosys/Espresso provenance, bounded fuzzing, and
the measured, auditable Occam generalization study. The companion #71 solution
is submitted in [PR #220](https://github.com/QuantumBFS/quantum.harness/pull/220).

## Working Repository

The completed implementation is maintained in the private AGPL-3.0 repository
`JunkaiWang-TheoPhy/quantum-harness-115-occam-rust-port`. The #71 implementation
line lives under the `challenge-71-occam/` subfolder. The audited v0.5.0 source
commit is `e9120224fe0b1f45ed309ad6b40bf7c9c381af38`; private CI and Release
links are available to authorized reviewers.
