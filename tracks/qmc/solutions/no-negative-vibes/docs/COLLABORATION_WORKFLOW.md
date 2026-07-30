# No Negative Vibes shared-research collaboration design

Date: 2026-07-28
Status: approved conversational design, pending written-spec review

## Objective

Give both No Negative Vibes members a shared GitHub workspace where all claimed
research directions, code, evidence, and reviews are visible early enough to
prevent duplicated work. Keep that workspace operationally separate from
`ZiboJin:challenge/qmc-sign-free-hunter`, whose pushes automatically update the
organizer-facing PR `QuantumBFS/quantum.harness#178`.

## Repository topology

The collaboration workspace will be a public fork owned by a new GitHub
organization:

```text
QuantumBFS/quantum.harness
├── ZiboJin/quantum.harness
│   └── challenge/qmc-sign-free-hunter     organizer-facing PR head
├── xianzhipan/quantum.harness
│   └── challenge/qmc-sign-free-hunter     existing research snapshot
└── no-negative-vibes/quantum.harness      shared research fork
    ├── research/no-negative-vibes         internal integration branch
    ├── work/zibo/<topic>                  Zibo's topic branches
    └── work/xianzhi/<topic>               Xianzhi's topic branches
```

The GitHub namespace `no-negative-vibes` was not present when checked on
2026-07-28. If GitHub rejects it during creation, stop and ask the user to
approve a different public organization name; do not silently choose one.

## Access model

- Invite both members to the organization.
- Grant both members `Write` access to the shared fork.
- Keep organization ownership and repository administration with Zibo unless
  the user later chooses shared administration.
- Do not grant outside GitHub Apps, deploy keys, or automation write access as
  part of this setup.
- Do not change permissions on either personal fork.

## Branch roles

### Internal integration branch

`research/no-negative-vibes` is the only base branch for internal research pull
requests. It starts from the teammate's audited snapshot:

```text
e915e485a7f75b5cd1a02007a0865ef2bc8a4bcb
```

The full commit ID must be preserved in the initial integration commit or
branch description. Updated teammate work is not imported until its new head
has been reviewed against this fixed snapshot.

### Individual work branches

Each topic uses a short-lived branch:

```text
work/zibo/<topic>
work/xianzhi/<topic>
```

Members may push freely to their own topic branches. Changes reach
`research/no-negative-vibes` only through an internal pull request reviewed by
the other member.

### Organizer-facing branch

`ZiboJin:challenge/qmc-sign-free-hunter` remains outside the daily
collaboration loop. No automation, merge target, or default push remote in the
shared workspace may point to it.

Any action that updates organizer PR #178 requires explicit user approval at
the time of that action.

## Work-claim protocol

Before substantive computation, every new direction starts with a small
candidate card committed on the member's topic branch. The card contains:

1. the candidate matrix class or research question;
2. what is new relative to snapshot `e915e48`;
3. the physical weight: determinant, Pfaffian, or Spin trace;
4. the proposed Hamiltonian/HS source, if applicable;
5. known-mechanism checks against split, Kramers, Majorana, contraction, and
   TN mechanisms;
6. separate success and failure evidence;
7. the smallest planned computation and stopping condition;
8. the member claiming the direction and the claim date.

Opening the internal pull request publishes the claim. The other member must
check existing open internal pull requests before starting a new direction.
Overlapping work is allowed only when the second pull request explicitly labels
itself an independent verification.

## Evidence and storage

- Source, tests, fixtures, and compact certificates live under
  `tracks/qmc/solutions/no-negative-vibes/`.
- Large scans remain under `tracks/qmc/results/no-negative-vibes/` and stay out
  of Git.
- Each reported numerical result records protocol, seed, software versions, and
  the source commit.
- Exact counterexamples are committed as machine-readable rational, algebraic,
  or symbolic certificates with verification tests.
- A zero-failure randomized scan is reported as survival evidence, never as a
  proof.

## Pull-request workflow

1. Create a topic branch from the current internal integration branch.
2. Commit the candidate card before expensive work.
3. Open an internal pull request immediately, marked as work in progress.
4. Push incremental code, tests, evidence summaries, and compact certificates.
5. The other member reviews novelty boundaries and reproducibility.
6. Merge only when the pull request has a clear conclusion: exact failure,
   known-mechanism reduction, bounded survival result, or proved result.
7. Keep organizer-facing publication as a separate, explicitly approved
   export step.

## Protection and failure handling

- Protect `research/no-negative-vibes` against force pushes and deletion.
- Require a pull request before merging into the integration branch.
- Do not rewrite shared history.
- If CI fails, keep the pull request open and record the failure; do not merge
  around it.
- If the shared fork cannot be created or the teammate cannot accept access,
  fall back to cross-fork internal pull requests rather than using the
  organizer-facing branch.
- If a branch contains secrets or private keys, stop, revoke the exposed
  credential, and remove it using a separately approved history-repair
  procedure.

## Initial setup sequence

1. Create the public GitHub organization `no-negative-vibes`.
2. Invite the teammate and wait for membership acceptance.
3. Fork `QuantumBFS/quantum.harness` into the organization.
4. Grant the two members `Write` access.
5. Create `research/no-negative-vibes` from fixed commit `e915e48`.
6. Add branch protection for the integration branch.
7. Push this collaboration specification to the integration branch.
8. Verify both members can create a topic branch and open an internal pull
   request.
9. Do not modify `ZiboJin:challenge/qmc-sign-free-hunter`.

## Acceptance criteria

The collaboration setup is complete when:

- the organization fork exists and both members have `Write` access;
- `research/no-negative-vibes` points to the audited research baseline plus
  this collaboration specification;
- direct force push and deletion of the integration branch are blocked;
- each member can publish a topic branch and open an internal pull request;
- no commit or branch update has changed organizer PR #178.
