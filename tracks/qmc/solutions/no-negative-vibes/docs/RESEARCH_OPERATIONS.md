# Reusable research operations

Updated: 2026-07-29

This public file records reusable, secret-free operating knowledge. Hostnames,
usernames, passwords, private-key paths, and private handoff material never
belong here.

## Git and collaboration

- `research/no-negative-vibes` is the shared integration base.
- Work on `work/zibo/<topic>` and open an internal PR early so the teammate can
  see the claim.
- Preserve failures, exact no-go certificates, and known reductions in Git.
- Push each interpreted experiment immediately after its log and compact
  evidence are committed.
- Never point the default research push at the organizer-facing branch.
- Teammate forks may proceed independently. Do not periodically review, merge,
  or synchronize them unless the research owner explicitly asks; protect
  compute and review time for the active topic branch.
- If a merge is needed, distinguish mechanical integration verification from
  scientific content review. A green merge test does not endorse a claim.

## WSL transfer when GitHub is unreachable

If the worker cannot reach GitHub, transfer a Git bundle rather than an
unversioned source archive:

1. create and verify a bundle for the exact research ref;
2. copy it through the authenticated SSH hop;
3. clone or fetch the bundle in a fresh worker directory;
4. verify `git rev-parse HEAD` before running;
5. remove or replace only uniquely named transfer artifacts.

Observed failure mode: HTTPS clone may terminate with a GnuTLS receive error or
port-443 timeout even when conda mirrors work. Forcing HTTP/1.1 and a shallow
clone is worth one retry; after that, use the bundle path instead of spending
research time on transport.

## SSH and nested WSL commands

- Keep strict host-key checking enabled. Compare a new host's ED25519
  fingerprint through an independent trusted channel before accepting it.
- A Windows SSH server may parse shell operators before a nested WSL `bash`
  sees them. Prefer direct commands of the form `wsl.exe -- <program> <args>`
  and use WSL's `--cd` option for the working directory.
- Avoid `||`, pipes, and complex nested quoting in remote probes. Split probes
  into independent read-only commands.
- If Git reports repository ownership mismatch because sandbox and interactive
  users differ, use command-scoped `git -c safe.directory=<exact-repo> ...`.
  Do not weaken the global Git safety configuration.

## Python test environment

Run the solution tests from the solution directory:

```text
PYTHONPATH=. python -m pytest tests -q
```

Set `OMP_NUM_THREADS`, `MKL_NUM_THREADS`, and `OPENBLAS_NUM_THREADS` to one.
The current dedicated environment needs NumPy, SciPy, SymPy, mpmath, pytest,
pandas, and matplotlib. A passing baseline at merge commit `04e72bd` is
recorded as `ENV-0001`.

## CPU allocation

- Use process-level parallelism for independent parameter cells.
- Set workers to `max(1, logical_cpus - 2)`.
- Keep BLAS at one thread per process to prevent oversubscription.
- Run one deterministic smoke cell before allocating the full worker pool.
- Assign disjoint cell ranges to the WSL and CPU workers; use independent
  seeds only when the purpose is cross-verification.
- The current WSL worker has 16 logical CPUs / 31 GiB RAM; cap it at 14
  processes. The current CPU worker has 64 logical CPUs / 503 GiB RAM; cap it
  at 62 processes.
- On a worker without `python3-venv` or direct GitHub access, do not require
  sudo and do not keep retrying GitHub. Use a checksum-verified user-space
  Miniforge installer from a reachable institutional mirror, override conda
  channels to a reachable conda-forge mirror, and transfer source as a
  verified Git bundle.
- Verify a new worker with an exact commit SHA and one focused test before
  assigning parameter cells.

## Experiment closure

An experiment is not closed when the program exits. It is closed after:

1. output integrity and residuals are checked;
2. the result is interpreted against the pre-registered prediction;
3. exact/high-precision upgrade is performed when required;
4. `EXPERIMENT_LOG.md` is updated;
5. compact evidence and replay tests are committed;
6. the commit is pushed to the shared topic branch.

## Review gates for exact algebra

- A fixed basis transform test must assert the literal basis rows and identity
  action outside the active sector, not only orthogonality.
- Embedding tests must compute at least one expected global basis index
  independently of the embedding helper.
- Record a single-generator Metzler witness as such. Do not upgrade it to an
  open-cone, arbitrary-depth, novelty, or physical-HS claim without the
  corresponding separate certificates.

## Exact cone-coordinate exclusions

- An LP status alone is not a theorem. For inequalities `C x >= 0`, an exact
  nonnegative dual with `C^T y_+ = e_a` proves `x_a >= 0`; an independent
  exact nonnegative dual with `C^T y_- = -e_a` proves `x_a <= 0`. Only the
  replayed pair proves `x_a = 0` throughout the cone.
- Report sign-local evidence. If one sign has an exact primal while the other
  is only numerically infeasible, write exactly that; do not describe the
  numerical sign as rigorously excluded. Reserve `certified-zero` for the
  verified two-sided dual pair.
- A coordinate no-go inherits every convention in the compiled system:
  transform, family, support mask, exact field, and basis. State those
  qualifiers next to the conclusion. It does not automatically exclude a BdG
  enlargement, a different transform, a micro-word construction, an open cone
  elsewhere, or a physical positive-coefficient HS map.
- Under the exact inclusion from a number-conserving cone into its BdG
  enlargement, a hopping primal with every pair-creation and
  pair-annihilation coefficient zero must already be a number-conserving
  primal. Treat an all-zero-pairing hopping survivor after an exact
  number-conserving hopping no-go as a hard contradiction, not as new physics.
- Hopping, pair-creation, and pair-annihilation bridge anchors are distinct
  directed coordinates. Separate directed survivors do not construct one
  Hermitian cone element: impose the hopping adjoint pair or `pc=pa` in one
  common functional anchor. If every directed coordinate is independently
  exact zero, the common Hermitian target is already excluded and needs no
  extra functional solve.

## Deterministic smoke-to-production promotion

- A production cell earns promotion only after its own one-worker smoke with
  the same family, mask, and full source commit. A smoke from a smaller support
  mask is not evidence for a larger one.
- Preserve every runner invocation at a new `attempt-NN` path. The atomic JSON
  writer intentionally replaces its target; attempt numbering is what keeps a
  retry auditable.
- After both runs, remove only the top-level `execution` object and require the
  complete remaining scientific payloads to be equal. Comparing only summary
  classifications can miss a certificate, provenance, ordering, or solver
  diagnostic change.
- Replay every embedded exact certificate before interpreting the cell. An
  exit code of zero and the absence of `status="error"` are necessary but not
  sufficient.
- Hash each ignored raw JSON before deriving a tracked fixture. The fixture
  records the raw path, SHA-256, worker/thread metadata, full source commit,
  package versions, classifications, sign-local statuses, and only the exact
  certificates needed for replay.
- Put source identity at experiment scope and package versions plus public
  host role at cell or raw-pair scope. One top-level source/package record is
  false provenance as soon as a fixture contains multiple experiments or
  software hosts.
- Raw and compact schemas need not have identical names. In the R01 fixture,
  raw branch field `exact_primal_certificate` becomes `certificate`;
  `zero_certificate` stays unchanged. Make such conversions explicit in the
  fixture schema and test the compact form directly.
- Across a CPU-to-WSL-to-gateway-to-local return path, receive into a unique
  `.part`, recompute SHA-256 on both sides of every hop, and atomically rename
  only after equality. Preserve the source and any mismatched `.part`; never
  overwrite a prior attempt name.

## Windows-to-WSL validation helpers

- Do not inline nontrivial Python through a Windows OpenSSH command that then
  invokes WSL. Nested quoting can remove the `python -c` argument boundary
  before Python starts. Put the read-only helper in a uniquely named temporary
  file, transfer it over the authenticated hop, and invoke that exact path.
- PowerShell variable names are case-insensitive and some common names are
  built in and read-only. Use task-specific names such as `$sshTarget`; do not
  reuse `$Host`, `$HOME`, or similarly global state.
- A nested SSH command starts in the remote account's default directory, not
  the repository directory named by an absolute pytest target. Consequently,
  `PYTHONPATH=.` can fail collection even when the test path is absolute. Use
  an absolute solution-directory `PYTHONPATH` or explicitly change the remote
  working directory before invoking Python.
- Before writing a validator, inspect one real raw's top-level, `system`,
  `execution`, anchor, and sign-branch keys. Reuse the runner's actual schema:
  for overlap-klein v1 the shape is `system.system_shape`, while
  `execution.blas_threads` maps environment names to the string `"1"`.
- Exact certificate replay may outlive an outer SSH timeout even though it is
  making CPU progress. On timeout, check the specific remote PID and wait for
  it to exit before retrying with a longer keepalive/timeout; never stack a
  duplicate replay or mistake exit 124 for a certificate verdict.
- For remote pytest runs that can outlive the connection, use a hash-matched
  detached wrapper that writes stdout/stderr to a unique log and writes the
  numeric exit code to a unique status `.part` before atomically renaming it.
  Poll the status path with simple argv-only commands. Partial pytest dots,
  disappearance of the controller connection, and a missing status marker are
  all non-verdicts.
- A quoting or transfer-helper failure that never started the scientific
  runner is an operational failure, not a new scientific attempt. Preserve
  the original raw file, verify its hash, record the mechanical lesson here,
  and continue with a new helper invocation rather than rerunning the cell.

## Raw-backed fixture candidate gates

- A tracked boolean saying that smoke and production payloads matched is an
  audit record, not validation evidence. Before accepting a candidate, open
  every referenced ignored raw and recompute the comparison.
- Keep ordinary tests hermetic with synthetic raw pairs under a temporary
  repository. Run the real-raw gate separately and explicitly at candidate
  time; missing ignored raws must fail that gate rather than skip it.
- Resolve each raw path against an explicit repository root, require the
  resolved file to remain inside that root, hash the bytes actually parsed,
  and reject missing, extra, duplicated, or malformed provenance fields.
- Require exactly one smoke and one production role per cell. Match the full
  raw execution object to the fixture, including the complete BLAS-thread map,
  process start method, workers, and exact parsed wall time.
- For deterministic smoke/production comparison, shallow-copy each top-level
  payload, delete exactly `execution`, and deep-compare everything remaining.
  Do not recursively strip timing-like fields or compare only summaries.
- JSON reserialization can shorten decimal spellings even when the parsed
  binary float remains usable. When raw literals are part of recorded
  provenance, preserve their original decimal text and let the raw-backed gate
  enforce parsed execution equality.
- Track resolved canonical raw paths in addition to fixture path strings.
  Distinct spellings such as an inserted `./` must not let smoke and production
  alias the same file.
- Require the raw system object's exact schema before using selected fields.
  Bind its exact field and transform to fixture scope rather than validating
  only `system_shape`.
- A raw-pair match does not prove that a compact tracked fixture came from that
  pair. Mechanically project the common raw anchors through the documented
  schema conversion and require exact equality with the fixture anchors.

## Mode-aware survivor dispatch

- A shared terminal label such as `survivor` is not a downstream type
  contract. Validate payload schema and mode before promotion, route only
  eligible records to a dedicated incoming directory, retain non-applicable
  payloads in a separate preserved directory, and hash-check both streams.
  A downstream type rejection is operational routing evidence, not a
  scientific failure.
- When one heterogeneous cell contains a long serial sample axis, top-level
  cell parallelism can leave that cell as the sole straggler after every other
  worker becomes idle. Freeze deterministic sample identities and exact input
  weights, shard by disjoint sample-index ranges, and merge with the original
  stable ranking key. Do not change the seeded sample stream merely to obtain
  better load balance.
