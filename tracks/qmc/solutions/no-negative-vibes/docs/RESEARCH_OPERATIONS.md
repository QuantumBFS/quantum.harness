# Reusable research operations

Updated: 2026-07-28

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
