# QDES Slurm Cluster Profile Design

## Goal

Add a public, reusable QDES cluster profile for `/using-slurm` and make the
skill stop before a costly or impractically delayed submission. The primary
deliverable is the configuration file; the skill change is limited to the
generic pre-submit guardrail revealed by the live QDES probe.

## Live evidence

The profile is based on read-only checks through the local SSH alias
`qdeshell` on 2026-07-20:

- passwordless SSH, `sbatch`, and `sinfo` work from a non-login shell;
- the visible partition is `qdagnormal`, with eight 64-core nodes, about 2 TB
  RAM per node, and eight A800 GPUs per node;
- QOS `partition_qdagnormal` requires `gres/gpu=1` for every job;
- a CPU-only one-minute `sbatch --test-only` request fails with `QOSMinGRES`;
- the same request with `--gres=gpu:A800:1` is valid but was estimated to start
  on 2026-08-31, so no real job was submitted;
- login-node internet access is unavailable; and
- the remote shell emits locale warnings because `C.UTF-8` is not installed.

The QDES documentation confirms that compute must run through its customized
Slurm scheduler and that `mix` nodes may still accept work.

## Public profile

Add `skills/using-slurm/profiles/qdeshell.toml` as a site profile rather than a
personal profile.

The file will:

- rely on the SSH alias `qdeshell` and omit host, username, port, and key path;
- use `~/quantum.harness` as the portable remote checkout path;
- set `qdagnormal` as the scheduler default and record the probed node shape;
- add optional `required_gres = "gpu:A800:1"` to the partition row;
- record login internet as unavailable and treat compute-node internet as
  unavailable until a scheduled probe proves otherwise;
- use conservative student limits: one node, 64 CPUs, 24 hours, and 200 array
  cells, with warnings at 8 hours and 16 CPUs;
- confine fetch/delete operations to `~/quantum.harness/results` and
  `~/scratch`; and
- record official QDES documentation links plus the QOS, locale, and queue
  gotchas.

The profile must contain no account name, personal home path, hostname, port,
or identity-file path. Each user remains responsible for defining the local
`qdeshell` SSH alias.

## Schema and skill change

Extend the `[[partitions]]` reference schema with optional `required_gres`.
This is an additive field, so existing profile parsing remains compatible.

In `/using-slurm`, add one pre-submit feasibility contract:

1. Include a partition's `required_gres` in the proposed resource request.
2. Run the exact request through `sbatch --test-only` before submission when
   the cluster supports it.
3. Treat QOS/resource rejection as a configuration error to fix before submit.
4. If the scheduler predicts an impractical start time, show wait/change/stop
   choices and do not leave a real job queued without user ratification.

This PR will not teach QDES-specific behavior in `SKILL.md`; the site-specific
facts stay in `qdeshell.toml`.

## Validation

Use test-first validation:

1. Add a cluster-profile test that initially fails because `qdeshell.toml` is
   absent, then checks TOML parsing, required anchors, `required_gres`, safety
   limits, and absence of personal SSH fields.
2. Run a baseline fresh-agent scenario against the current skill using the raw
   QDES probe transcript. Record whether it submits a CPU-only job, overlooks
   `QOSMinGRES`, or queues the delayed GPU job.
3. Add the minimal skill guidance and repeat the same scenario with the revised
   skill. It must include the GPU requirement, use `sbatch --test-only`, and
   stop before the delayed real submission.
4. Run the focused tests, skill validation, and the repository test suite.
5. Re-run profile-driven `precheck`, `probe-partitions`, and a dry-run submit.
   Do not submit a live QDES job unless its predicted start becomes practical
   and the user separately ratifies the GPU allocation.

## Pull request scope

The PR contains only:

- the public QDES TOML profile;
- the additive profile-schema documentation;
- the minimal generic pre-submit guidance in `/using-slurm`; and
- focused regression tests.

It excludes personal connection data, a live `active.toml` symlink, remote
repository installation, real queued jobs, and unrelated Slurm refactors.
