# Attempt journals

Benchmark v0 implementation is limited to five worktree-isolated attempts.
The rules and worktree naming convention are in
[`../docs/execution-protocol.md`](../docs/execution-protocol.md).

| Attempt | Branch | Outcome | Benchmark status | Journal |
|---:|---|---|---|---|
| 01 | `challenge/qmc-chiral-graviton-a01` | slice-pass | ED reference ready; candidate pending | [attempt-01.md](attempt-01.md) |
| 02 | `challenge/qmc-chiral-graviton-a02` | benchmark-pass | all frozen v0 gates true | [attempt-02.md](attempt-02.md) |
| 03 | `challenge/qmc-chiral-graviton-a03` | not started | not run | -- |
| 04 | `challenge/qmc-chiral-graviton-a04` | not started | not run | -- |
| 05 | `challenge/qmc-chiral-graviton-a05` | not started | not run | -- |

Copy `attempt-template.md` to `attempt-NN.md` when an attempt actually starts.
Do not consume an attempt number for setup-only work.

