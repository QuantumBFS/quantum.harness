# Challenge 148 QMC_SSE adapter

This is the primary SSE adapter for Challenge 148. It links QMC_SSE revision
`35f100af856f3273cc67d31962f3e67f801b0c37`, which is licensed
`GPL-3.0-only`; consequently this adapter is also distributed under
`GPL-3.0-only`.

Run it as:

```text
qmc-sse --request REQUEST.json --output-directory RUN_DIRECTORY
```

Trusted launchers can instead pass already-open descriptors:

```text
qmc-sse --request-fd REQUEST_FD --output-directory-fd OUTPUT_DIRECTORY_FD
```

The two launch modes are mutually exclusive. Descriptor mode duplicates and
validates both inherited descriptors, reads the request directly, and roots all
storage operations in the supplied directory descriptor without reopening a
`/proc/self/fd` or lexical request/output path.

`qmc-sse --build-info` prints the source and executable build fingerprints
that requests must bind.

## Sweep and RNG semantics

QMC_SSE does not expose the number of sites visited by a cluster. This adapter
therefore uses the conservative, observable rule required by the design: one
sweep is one diagonal update followed by exactly `N` cluster-update attempts,
where `N` is the number of graph sites. Raw bins report this as
`cluster_attempts_per_sweep=N`; they do not claim measured cluster size or site
visits.

The sole simulation RNG is rand 0.9.5 `SmallRng` (Xoshiro256++ on
64-bit targets). Its complete 256-bit seed is
`SHA256("qmc-sse-seed-v1" || request_seed.to_be_bytes())`, identified in bins
and build metadata as `sha256:qmc-sse-seed-v1||u64be`. The future QMC_LTFIM
adapter must use a different domain string.

Graph parsing rejects non-integer JSON types and checks arithmetic. Before
topology construction it enforces `L<=96`, at most 18,432 sites, at most 27,648
bonds, and a 2 MiB input-byte ceiling. These limits include both supported
lattices through `L=96` while bounding allocation and topology work.

## Durable publication

The output directory is protected by an exclusive
`.qmc-sse-lock-state/.qmc-sse.lock`, held across simulation, replay, audit, and
publication. A no-replace `run-lock-anchor.json` selection record binds one
canonical `run-lock-anchors/<sha256>.json` object by hash, path, device, and
inode. A durable `<sha256>.pin` hard link keeps that inode allocated, so
unlink/recreate cannot pass through immediate filesystem inode reuse. The
canonical anchor binds the lock-state directory, lock file, and
`identity.json` device/inode pairs plus the request hash and absolute output
namespace. Its canonical bytes define its filename hash. Initialization allows
exactly one canonical anchor plus its same-inode pin; a second object, missing
object or pin, filename/content mismatch, replacement inode, symlink, or changed
retained bytes fails closed. The pin is published and fsynced before the
canonical rename so interrupted initialization retains its staged recovery
object. Existing same-hash objects are byte-validated and never overwritten.

The selection, canonical anchor, state, lock, and identity descriptors remain
open. Their path identities, canonical bytes, anchor hash, and bindings are
checked before and after `flock` and before every mutation. Every checkpoint
generation and `current-generation.json` binds the selected anchor SHA256, so
published run history independently detects later anchor deletion or
substitution. Before the first generation, both the abstract lock and
filesystem lock remain held and no bin, generation, pointer, recovery, or
archive mutation starts until anchor selection is durable and self-hash-valid.

Before opening or mutating the run directory, the adapter also binds a Linux
abstract AF_UNIX socket. Its name is a versioned SHA256 derivation of the
effective uid, lexically canonical absolute output path, and request namespace.
Local contenders retry for a bounded interval (30 seconds by default,
test-adjustable with `QMC_SSE_ABSTRACT_LOCK_TIMEOUT_MS`) and fail with a
diagnostic if the holder does not exit. Socket setup is Linux-only and fails
closed. The supported threat model is fail-closed handling of concurrent
path/symlink/replacement races and independently corrupted or replaced control
objects while the selected anchor descriptors are retained. For cross-node
execution, orchestration assigns one cell/output path; the descriptor-anchored
filesystem lock remains the cooperative shared-filesystem guard between nodes.
This is not a claim against an omnipotent same-UID attacker that deletes every
run artifact and coherently rewrites the complete anchor and generation
history.

Linux file access retains the complete descriptor chain from
`/` through every output-path ancestor, opened component-by-component with
`openat2`
`RESOLVE_BENEATH|RESOLVE_NO_SYMLINKS`, `O_NOFOLLOW`, and descriptor type checks.
On kernels without `openat2` (`ENOSYS`), the same validated single-component
walk uses direct `openat` syscalls with `O_NOFOLLOW`; slash, dot, dot-dot, and
NUL components are rejected before either syscall. Other `openat2` failures do
not trigger fallback.
Every parent-to-child device/inode relationship is revalidated after locking
and before mutation.
Publication uses descriptor-relative `renameat2(RENAME_NOREPLACE)`; an
`EEXIST` winner is fully byte-, shape-, identity-, replay-, and
reference-validated rather than overwritten. Completed bins and checkpoint
generations are immutable SHA256-addressed objects. Recovery reconstructs the
model and RNG from the request and replays all updates; no opaque upstream
state is serialized.

For deterministic crash testing, `QMC_SSE_FAILPOINT` accepts
`before-bin-rename`, `after-bin-rename`, `before-generation-rename`,
`after-generation-rename`, or `before-pointer-replace`.
`QMC_SSE_FAILPOINT_OCCURRENCE` selects the matching occurrence.
`QMC_SSE_FAIL_FSYNC_AT` fails the selected fsync call.
`QMC_SSE_CRASHPOINT` hard-exits at named file-fsync, directory-fsync, rename,
and pointer-replace boundaries; `QMC_SSE_CRASHPOINT_OCCURRENCE` selects an
occurrence. `QMC_SSE_TEST_*` synchronization variables are test-only hooks used
to prove lock blocking and replacement-race behavior.
