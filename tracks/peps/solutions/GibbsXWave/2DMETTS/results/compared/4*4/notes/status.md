# Status

Last updated: 2026-07-28 (Asia/Shanghai)

## Current State

- `[Decision]` Project name: `HarnessingQuantum-2026`.
- `[Tested]` The independent local Git repository and initial project scaffold
  have been created.
- `[Source]` The event runs July 27–31, 2026, in Hefei.
- `[Source]` The official repository is `QuantumBFS/quantum.harness`.
- `[Decision]` This repository is the personal coordination layer; the official
  harness fork will remain the submission-code repository.
- `[Tested]` The first research structure is in place under `research/` and
  `planning/`.
- `[Tested]` The 2026-07-22 snapshot of 23 accepted challenges is preserved.
  A separate opening-day snapshot captured 40 open accepted issues on
  2026-07-27, an increase of 17. A same-day later update captured 42, with
  #147 and #148 as the delta; the 40-issue snapshot was not overwritten.
- `[Source]` The published mentor desk schedule contains eight half-day slots
  from Monday through Thursday. Lei Wang and Kun Chen appear in all 8; Shi-Xin
  Zhang appears in 4 (Wednesday and Thursday); Mingpu Qin appears in 1
  (Wednesday afternoon). No PEPS track lead or PEPS challenge releaser appears
  in those eight slots.
- `[Tested]` The Chinese XeLaTeX note now combines the original PEPS/QMC/VMC
  technical survey with both opening-day snapshots, mentor coverage, the
  preserved old shortlist, and the final #147 PEPO/METTS analysis.
- `[Decision]` Final challenge: #147, “2D finite-temperature tensor networks —
  extend PEPO/METTS to 2D and benchmark against QMC,” released by Wei Li.
- `[Decision history]` The previous #119/#86/#87/#121/#89/#90 ordering and
  the prior wish to avoid Wei Li's challenge remain preserved as an opening-day
  snapshot, but they are superseded and are no longer the current shortlist.
- `[Decision]` The challenge is fixed; PEPO/purification versus 2D PEPS-METTS
  remains open until a runnable scaffold, QMC reference, compute budget, and
  mentor-approved five-day floor are audited.
- `[Source]` #147's official method is `PEPS Based Algorithm`; its mandatory
  benchmark is the 10x10 OBC square-lattice TFIM over beta J in [0.1, 1.0],
  validated against QMC.
- `[Tested]` This coordination repository has both a local mirror remote and a
  private ITP GitLab remote for team sharing.
- Formal event track registration: not recorded. The selected issue declares
  `PEPS Based Algorithm`.
- `[Decision]` `FTPEPO/` is a separately scoped local Julia package for
  finite-temperature PEPO development. It is not official harness submission
  code unless a validated change is later ported to the harness fork.
- `[Tested]` The initial `FTPEPO` package scaffold, imaginary-time schedule,
  and unit-test suite were created on 2026-07-27 without external scientific
  dependencies; all 13 tests pass under Julia 1.11. This is infrastructure
  only: tensor states, gates, compression, environments, and observables are
  not implemented yet.
- `[Tested]` The detailed
  [`2x2` ED / `4x4` SSE-QMC check of Chuanshu Xu's finite PEPS-METTS
  table](2026-07-28-qmc-check-xu-peps-metts.md) is recorded with all 440
  replica rows, aggregate tables, error interpretation, source fingerprints,
  commands, and a comparison figure. At `2x2`, the METTS discrepancy exceeds
  three quoted statistical standard errors at `beta=5,7,8,9,10`; at `4x4`,
  all ten points are compatible with SSE at the current roughly `1e-3`
  total-energy resolution. This is an `h=0.5` development check, not the
  challenge-field `10x10` reference.
- `[Tested]` The private
  [`wuguoliang/QuantumMC-Methods`](https://code.itp.ac.cn/wuguoliang/QuantumMC-Methods)
  GitLab project now contains the full `PRELEARNING_BASELINE` at commit
  `008f3ecf70423c5bb6debf45038cf22084e46136`. It is attached here as the
  `QuantumMC-Methods/` submodule using the relative URL
  `../QuantumMC-Methods.git` and branch `main`.
- Team membership and role allocation: not recorded in this repository.
- Official harness fork and working branch: not created or linked here yet.
- Environment readiness audit: not started.

## Immediate Next Actions

1. Register #147 using the current `/take-challenge` workflow and open the draft
   PR; record fork, branch, PR, and team roles here.
2. Ask Wei Li to choose PEPO/purification or 2D METTS and provide the runnable
   scaffold commit, one known output, QMC reference data, compute budget, and
   mentor-approved five-day acceptance floor.
3. Fix a first benchmark at h/J=3.0: pass a 4x4 ED oracle before expanding to
   10x10 QMC, bond-dimension/sample, or beta sweeps.
4. Keep tensor truncation errors (D, environment chi, Trotter step) separate
   from METTS/QMC statistical errors; preserve raw data and a one-command plot.
5. Confirm the authoritative PR freeze/review timeline and the correct current
   challenge command through the event Zulip.
6. Audit GitHub authentication, terminal tools, `make`, compute access, and an AI
   coding agent using `planning/readiness.md`.
7. Create the personal official-harness fork as soon as the team workflow is
   confirmed; attach it at `quantum.harness/`. Formal event work belongs there,
   while this GitLab project remains the coordination layer.

## Schedule Risks to Confirm

- `[Source]` The guide asks for a submitted PR with passing checks by Thursday
  morning, while the program mentions a Thursday 20:00 PR update deadline.
- `[Source]` The guide and program describe Friday's review/presentation order
  differently.
- `[Decision]` Use the event Zulip or an organizer announcement as the final
  authority before planning against either deadline.

## Official Links

- Event: https://giggleliu.github.io/summer-school-2026/zh/
- Guide: https://giggleliu.github.io/summer-school-2026/zh/guide
- Program: https://giggleliu.github.io/summer-school-2026/zh/program
- Harness: https://github.com/QuantumBFS/quantum.harness
- Challenges: https://github.com/QuantumBFS/quantum.harness/issues?q=is%3Aissue%20label%3Achallenge%20label%3Aaccepted
