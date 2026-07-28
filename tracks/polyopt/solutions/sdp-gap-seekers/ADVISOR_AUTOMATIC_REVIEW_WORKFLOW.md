# Proposed automatic advisor-review workflow

Date: 2026-07-28

## Recommendation

Use a **scheduled task in the existing advisor chat**, combined with a
repository review-request marker that the worker changes only at major
checkpoints.

Do not use Goal mode as the event detector. Goal mode preserves an objective
and automatically continues active work, but it is not a documented local
filesystem or Git-commit subscription mechanism. Leaving a goal alive while it
repeatedly polls Git would be less reliable, consume unnecessary work, and make
the stopping conditions harder to reason about.

The recommended workflow is polling rather than a native filesystem event, but
it requires no repeated message from the user. With a five-minute interval, the
worst expected detection latency is approximately five minutes.

Official references:

- [Scheduled tasks](https://learn.chatgpt.com/docs/automations)
- [Long-running work and Goal mode](https://learn.chatgpt.com/docs/long-running-work)
- [Codex GitHub Action](https://learn.chatgpt.com/docs/github-action)

## Why use an explicit marker instead of reviewing every commit?

The worker may make intermediate commits that are incomplete, internally
inconsistent, or only checkpoint work. Reviewing every commit would create
noise and could cause the advisor and worker to react to each other
continuously.

An explicit marker gives a stable contract:

- the worker decides when a substantial change is ready;
- the requested commit is immutable and reviewable even if the working tree
  changes afterward;
- the advisor reviews each request exactly once;
- the review result is a Markdown note keyed to the requested commit.

## Proposed marker

Worker-owned file:

```text
tracks/polyopt/solutions/sdp-gap-seekers/REVIEW_REQUEST.md
```

Suggested content:

```markdown
# Review request

Status: ready
Branch: challenge/polyopt-sdp-gap
Commit: <full 40-character commit SHA>
Previous-advisor-review: <previously reviewed commit SHA>
Requested-at: <ISO-8601 timestamp>

## Claimed changes

- ...

## Claims that should now be promotable

- ...

## Files or branches that need special attention

- ...

## Required review mode

Static review only. Do not run Julia, tests, solvers, or numerical jobs.
```

Rules for the worker:

1. Modify this marker only when a major checkpoint is ready for advisor review.
2. Point `Commit` to a committed, immutable snapshot, not merely the current
   working tree.
3. Use the full SHA, not only a short prefix.
4. List exactly which earlier comments are claimed to be fixed.
5. Do not edit an existing advisor review note.

## Proposed scheduled task

Create the task **inside this existing chat** so it retains the advisor context
and prior reviews. Use the local project containing this repository.

Suggested cadence:

```text
Every 5 minutes
```

A longer interval such as 15 minutes is appropriate if minimizing scheduled
runs matters more than response latency.

Suggested durable task prompt:

```text
Monitor:
tracks/polyopt/solutions/sdp-gap-seekers/REVIEW_REQUEST.md

If the file is absent, Status is not "ready", the requested commit does not
exist, or an advisor note already exists for the exact requested SHA, make no
repository changes and report no new review.

When a new valid request appears:

1. Read AGENTS.md and all applicable repository instructions.
2. Resolve the exact full SHA from REVIEW_REQUEST.md. Verify that it is the
   stated commit on challenge/polyopt-sdp-gap. Review that immutable commit,
   not a moving working tree.
3. Compare it with Previous-advisor-review and with the requirements in the
   most recent ADVISOR_REAUDIT/ADVISOR_RECHECK note.
4. Perform a static correctness and reliability review only. Do not run Julia,
   tests, solvers, SDPs, numerical experiments, package installation, or
   network-dependent jobs.
5. Inspect code and text closely enough to detect internal contradictions,
   unsound verification logic, stale evidence, API mismatch, missing
   provenance, and unsupported scientific claims.
6. Write the complete result to:
   tracks/polyopt/solutions/sdp-gap-seekers/
   ADVISOR_RECHECK_<YYYY-MM-DD>_COMMIT_<shortsha>.md
7. The note must state the exact full reviewed SHA, review scope, what is
   genuinely fixed, what remains, and an acceptance checklist for the worker.
8. Do not modify worker source, scripts, evidence, ledgers, branches, commits,
   or the review-request marker. Write only the new advisor note.
9. Preserve unrelated working-tree changes. Never checkout, reset, clean,
   stash, commit, push, or delete anything.
10. If the same SHA was already reviewed, remain idempotent and do not create a
    duplicate note.

After writing a new review note, return a concise chat message linking to it.
```

## Idempotence rule

The requested commit SHA should be the identity of a review.

Before acting, the task should search existing advisor notes for:

```text
Reviewed commit: <full SHA>
```

If found, the request is already handled. This avoids needing a mutable state
database and keeps the audit trail inside the Markdown notes.

## Concurrency and safety rules

The scheduled reviewer and worker may be active at the same time. To avoid
interference:

- review committed Git objects, not uncommitted working-tree contents;
- never switch the worker's checkout to another commit or branch;
- never run formatting or other commands that modify worker files;
- write only a new, commit-keyed advisor note;
- do not commit or push the advisor note automatically;
- preserve `Ion.lock` and all unrelated user changes;
- treat a missing or malformed commit SHA as “not ready,” not as permission to
  guess;
- if the branch moves after the request, continue reviewing the exact requested
  SHA;
- if the requested SHA is not reachable from the stated branch, record a
  blocker rather than reviewing an arbitrary HEAD.

Running the scheduled task in a dedicated worktree offers stronger write
isolation, but the resulting note would live in that worktree rather than the
worker's checkout unless another handoff mechanism is added. For the current
workflow, local-project mode with a strict “write only one advisor note” prompt
is simpler.

The computer must remain on and the desktop app must remain running when a
scheduled task needs local project files, as described in the scheduled-task
documentation.

## Why the other mechanisms are less suitable

### Goal mode

Goal mode is suitable when Codex should keep actively working toward a
completion condition over hours or days. It retains the same sandbox and
approval policy and can be steered in the same chat.

It is not the preferred way to wait indefinitely for a future filesystem
change. There is no documented “wake this goal when branch X advances” binding.
A watcher process plus an active goal could be engineered, but it would be a
custom long-running process rather than a durable product-level Git trigger.

### Codex `notify`

The `notify` configuration runs an external program when Codex emits supported
events, currently `agent-turn-complete`. It sends events **from Codex outward**.
It does not wake Codex when Git changes, so it does not solve this request.

### Local Git hook

A `post-commit` hook could invoke `codex exec` or touch a sentinel. This can be
truly event-driven for local commits, but it has drawbacks:

- hooks are local to a checkout and are not normally versioned;
- it can block or complicate the worker's commit;
- it must manage authentication, concurrency, failures, and logging;
- it normally starts a new Codex run rather than resuming this advisor chat;
- it is easy to create review loops if the reviewer itself commits.

If immediate event-driven local review later becomes essential, the safer
custom design is:

```text
post-commit hook -> atomically write/refresh REVIEW_REQUEST.md
                 -> lightweight external queue
                 -> isolated codex exec review
```

That is more engineering than the current project needs.

### GitHub Action

If the worker pushes every review checkpoint to a pull request, a GitHub Action
is the cleanest truly event-driven design. It can trigger on
`pull_request.synchronize` and run a committed review prompt with
`openai/codex-action@v1`.

Advantages:

- push/PR events are native triggers;
- the reviewed commit is unambiguous;
- the run is isolated and logged;
- feedback can be posted on the PR or saved as an artifact.

Disadvantages for the current workflow:

- it does not see unpushed local commits;
- it does not automatically inherit this chat's full context;
- it requires API/CI credentials and workflow configuration;
- producing the advisor Markdown note in the worker's local checkout requires
  an additional handoff.

Use this option if the collaboration moves to a PR-first workflow.

## Suggested choice for this project

Use:

```text
worker updates REVIEW_REQUEST.md at a major committed checkpoint
    -> scheduled task in this chat checks every five minutes
    -> advisor statically reviews the exact SHA
    -> advisor writes ADVISOR_RECHECK_<date>_COMMIT_<sha>.md
    -> worker reads the note
```

This is the best balance of:

- no repeated user message;
- preservation of this chat's context;
- exact commit pinning;
- low setup cost;
- no solver/test execution;
- minimal interference with the worker.

## Setup status

This note is a proposal only. No goal, scheduled task, Git hook, marker, or
automation has been created.

The current chat surface does not expose a callable Scheduled-task management
tool to the advisor, so the task would need to be created from the desktop
app's **Scheduled** interface (or another ChatGPT surface where Scheduled
management is available). The marker and any repository prompt files can be
added after the user approves this design.
