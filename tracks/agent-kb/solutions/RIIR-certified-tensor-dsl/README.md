## Team

| | |
|---|---|
| **Team name** | Ranger |
| **Members** | Chenxi Wan, Yedi Shen, Junkai Wang |

## Challenge

| Row | |
|---|---|
| **Challenge** | Complete a Rust-inspired certified tensor DSL where tensor computation, resource discipline, theorem checking, and proof obligations share one native kernel. |
| **Catalog issue** | [#82, "All in one: a native language for code + theorem + proof"](https://github.com/QuantumBFS/quantum.harness/issues/82), released by Huanhai ZHOU. |
| **Submission PR** | [QuantumBFS/quantum.harness#216](https://github.com/QuantumBFS/quantum.harness/pull/216) |
| **Track** | `agent-kb`, chosen by the team because the issue's `Method` field is `Other` and the work is agent-native language and verification infrastructure. |
| **Selected bar** | Mandatory Goal 1a and Goal 1b, plus Goal 2a. |
| **Status** | Complete. |

## Result

The submission implements a Rust-native parser, type checker, proof checker,
proof-producing optimizer, Loop IR, and Cranelift execution path.

- Goal 1a compiles one dynamic-input, five-step dense MPS TDVP program as one
  artifact. It produces an exact accumulated truncation certificate and checks
  the local, step, and trajectory proof chain before proof erasure.
- Goal 1b compiles a separate strict-U1 whole program. Illegal charge fusion is
  rejected before execution; three checked zero-block rewrites reduce forbidden
  operations from 18 to 0; associativity, F-symbol agreement, and the pentagon
  relation are checked without axioms.
- Goal 2a records a pass-on native median of `0.354256687 s` against
  `0.510079958 s` for the JAX CPU reference on the fixed Apple M4 review host.
  All eight claim gates pass.

The Goal 1a review records a native median of `9.649689875 s` against
`11.952629188 s` for JAX across 30 measured runs per mode. All 17 artifact,
parity, proof, provider, and provenance gates pass.

## Goal 2 Selection

Challenge #82 defines Goal 2 as "choose one" and states that the single bar is
Goal 1 plus one of Goal 2. This submission selects Goal 2a. Goal 2b derived
automatic differentiation is the alternative Goal 2 path, not an additional
requirement for this submission.

## Evidence

| Evidence | Repository path | SHA-256 |
|---|---|---|
| Completion audit | [`docs/challenge-82-completion-evidence.md`](https://github.com/JunkaiWang-TheoPhy/quantum-harness-82-certified-tensor-dsl/blob/v0.2.0/docs/challenge-82-completion-evidence.md) | committed with `v0.2.0` |
| Goal 1a report | [`benchmarks/results/2026-07-28T162926Z-tdvp-review.json`](https://github.com/JunkaiWang-TheoPhy/quantum-harness-82-certified-tensor-dsl/blob/v0.2.0/benchmarks/results/2026-07-28T162926Z-tdvp-review.json) | `9e9858e5d83f00525a4ce38ee862ee96620ab7d9c51e75a3cadca9d9528ac016` |
| Goal 2a report | [`benchmarks/results/2026-07-28T125641Z-u1-review.json`](https://github.com/JunkaiWang-TheoPhy/quantum-harness-82-certified-tensor-dsl/blob/v0.2.0/benchmarks/results/2026-07-28T125641Z-u1-review.json) | `4e4ab3eee6fcd89a88e48214d58fbf49284eb51dd01142044d6e09e885625b17` |

Native and JAX complex SVD both resolve through Apple Accelerate LAPACK. The
submission includes an explicit generated TCB, proof-erasure provenance,
schema-validated reports, fixed workload manifests, and reproducibility
instructions.

## Scope

The result does not claim a floating-point rounding or stability theorem,
non-Abelian symmetry, arbitrary-rank symmetric contraction, symmetric TDVP, or
Goal 2b automatic differentiation.

## Working Repository

The implementation and
[`v0.2.0` release](https://github.com/JunkaiWang-TheoPhy/quantum-harness-82-certified-tensor-dsl/releases/tag/v0.2.0)
are hosted in the private AGPL-3.0 repository
`JunkaiWang-TheoPhy/quantum-harness-82-certified-tensor-dsl`. The links above
resolve for authorized reviewers. Organizers and reviewers can be granted
direct access without changing the repository's private visibility.
