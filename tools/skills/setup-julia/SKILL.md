---
name: setup-julia
description: >-
  Use when Julia is missing, wrong-version, uninstantiated, or mirror-misconfigured —
  symptoms like `julia: command not found`, missing `julia-env/Manifest.toml`,
  package downloads timing out, fresh cluster account, fresh laptop,
  package-mirror change, or Julia-version bump.
---

# setup-julia

Install and configure Julia for the harness — install via juliaup, configure the package mirror (defaults to Chinese mirror if `region == mainland_china` in the cluster profile), and instantiate the project env (`julia-env/`). Generic over target (local or remote ssh alias). Idempotent — re-running is safe and quick.

Idempotence is enforced, not aspirational:

<checklist name="idempotence">
- (a) Probe MUST succeed before any install attempt — step 3 short-circuits when `julia` is already at the requested version.
- (b) Mirror config replaces (NEVER appends) the `JULIA_PKG_SERVER` line in `startup.jl` and the matching lines in shell rc files.
- (c) `Pkg.instantiate()` is safe to re-run; subsequent runs no-op on already-resolved manifests.
- (d) `verify` MUST pass on the no-op path (re-running the whole workflow on an already-set-up host exits 0 without modifying anything).
</checklist>

This skill is for *Julia-specific configuration*. Cluster-side conventions (ssh, scheduler, partitions) live in `tools/cluster/<active>.md` and are read here for `region` defaults and (when target is remote) the ssh alias and `repo_path_remote`.

Julia package stacks are declared separately in `tools/software/stacks/*.toml`.
This skill only makes Julia itself and `julia-env/` usable locally or remotely;
after that, the selected stack's install command (for example `make install itensors`,
`make install sse`, or `make install pepskit`) installs method packages.

## When to activate

- A workflow about to run Julia code finds `julia` not installed.
- A fresh laptop / fresh cluster account needs the harness's Julia stack.
- Package mirror changes (e.g., the user moves region or the institutional mirror updates).
- Bumping Julia version (`--version 1.11.x`).
- `/slurm`'s pre-submit check sees `julia-env/Manifest.toml` not yet instantiated on the cluster.

## Inputs

| flag | type | default | source-of-default |
|---|---|---|---|
| `--target` | `local` \| `remote:<alias>` | `local` | CLI; for remote, `<alias>` matches `tools/cluster/<active>.md`'s `ssh.alias` field; the skill reads `repo_path_remote` for where the project lives. |
| `--region` | name | from cluster profile's `region` field | See [Mirror reference](#mirror-reference). |
| `--mirror` | URL | unset | Advanced override for `JULIA_PKG_SERVER`. |
| `--version` | `X.Y.Z` \| `release` | `release` | juliaup's stable channel. When `release`, the project's `julia_version` is also consulted. |
| `--instantiate` / `--no-instantiate` | flag | `--instantiate` | Runs `Pkg.instantiate()` after install. |

Recognized regions for `--region` (see [Mirror reference](#mirror-reference) for the contract):

| region | JULIAUP_SERVER | JULIA_PKG_SERVER | source |
|---|---|---|---|
| `mainland_china` | `https://mirror.nju.edu.cn/julia-releases/` | `https://mirrors.nju.edu.cn/julia` | Jinguo guide (Nanjing University mirror) |
| other / unset | unset | unset | Julia defaults (no mirror config) |

## Workflow

This skill follows the Jinguo-group recipe verbatim (https://book.jinguo-group.science/stable/chap2/julia-setup/). **Mirror first, then install** — juliaup itself respects `JULIAUP_SERVER` if exported before the curl installer runs.

1. **Probe target**: detect if `julia` is reachable (PATH, `module load`, or `~/.juliaup/bin/julia`). For remote: `ssh <alias> 'command -v julia || command -v juliaup'`. Also read the manifest's `julia_version` to verify version compatibility against any pre-existing Julia.
2. **Configure mirror first** (only if `--region` resolves to a mirror): `tools/cli/setup-julia.sh mirror --region <name>`. This step runs BEFORE installing Julia even though the Jinguo guide numbers it "Step 2" — the mirror env var MUST be exported before the curl installer fetches juliaup. See [Mirror reference](#mirror-reference) for region defaults and URLs.

   The script writes BOTH `JULIAUP_SERVER` and `JULIA_PKG_SERVER` env vars to **every shell rc the script detects** (any of `~/.bashrc`, `~/.zshrc`, `~/.profile`); idempotently replaces any prior `JULIAUP_SERVER=` / `JULIA_PKG_SERVER=` line. Login-shell user (`$SHELL`) is ALSO written to `~/.profile` to cover non-interactive ssh. AND writes `JULIA_PKG_SERVER` to `~/.julia/config/startup.jl` for julia subprocesses.

   Precedence note: shell-rc env var beats `startup.jl` for julia subprocesses launched in interactive shells; `startup.jl` beats nothing for julia subprocesses launched without env (e.g., julia invoked from a Slurm script). Both are rewritten on every `mirror` invocation so they cannot drift.
3. **Install Julia.** **Skip if** step 1's probe found a working `julia` whose `julia --version` matches `--version` (or matches the project's `julia_version` when `--version release`). Otherwise: `tools/cli/setup-julia.sh install [--region <name>] [--version X.Y.Z]`.

   <note name="what the script does">
   The script exports `JULIAUP_SERVER` for the current shell (so the curl installer downloads through the mirror); runs `curl -fsSL https://install.julialang.org | sh` to install juliaup; writes the guide's Revise try/catch snippet to `~/.julia/config/startup.jl`; and `Pkg.add("Revise")` into the default env.
   </note>

   **The skill verifies AFTER the script returns** — all binary, ALL MUST pass:

   <checklist name="install-verify">
   - (a) `julia --version` reports the requested version (or matches the project's `julia_version` when `--version release`).
   - (b) `~/.julia/config/startup.jl` contains the `JULIA_PKG_SERVER` mirror line (when a mirror region was set).
   - (c) `julia -e 'using Revise'` exits 0.
   </checklist>
4. **Instantiate.** Local: `tools/cli/setup-julia.sh instantiate <project_dir>` (runs `Pkg.instantiate(); Pkg.precompile()` inside `<project_dir>`). Remote: same via `ssh <alias> 'cd <repo_path_remote> && tools/cli/setup-julia.sh instantiate julia-env'`.
5. **Verify**: `tools/cli/setup-julia.sh verify <project_dir> <package_name>` — three binary items, ALL MUST exit 0:

   <checklist name="verify-contract">
   - (a) `julia --project=<project_dir> -e 'using Pkg; Pkg.status()'` exits 0.
   - (b) `julia --project=<project_dir> -e 'using <package_name>'` exits 0.
   - (c) Reported version of `<package_name>` matches the `Project.toml` compat bound.
   </checklist>
6. **Hand back**: Julia version, mirror url, project env state. Hand-back report per [AGENTS.md → Output norms](../../../AGENTS.md#ui-ux).

## Output

- For local: Julia installed and on `$PATH`; `~/.julia/config/startup.jl` configured; `julia-env/` instantiated and precompiled.
- For remote: same, on `<alias>:<repo_path_remote>`.
- Hand-back report per [AGENTS.md → Output norms](../../../AGENTS.md#ui-ux).

## Composition

**Callers** (who calls `/setup-julia`):

- `/onboard` — if the user signals they will write Julia code (e.g., DMRG / ITensors workflows).
- `/slurm` — pre-submit when the remote cluster's `julia-env/Manifest.toml` hasn't been instantiated yet.
- `make install julia` and `make install itensors` recipes (the makefile recipes can dispatch the skill via `${CLAUDE_SKILL_DIR}/setup-julia/...` once registered).

**Downstream** (what runs after `/setup-julia`):

- Any `language = "julia"` stack contract in `tools/software/stacks/*.toml` — `/setup-julia` precedes the stack's install command.

**Data dependencies** (what `/setup-julia` reads):

- `tools/cluster/<active>.md` — for the `region` default mirror and (for remote) the ssh alias and `repo_path_remote`.

## Mirror reference

Single source of truth for region → mirror mapping and mirror-config semantics. The Inputs table, step 2, and Anti-patterns all link here.

For users in mainland China, package downloads from `pkg.julialang.org` are typically slow or unreliable. The Jinguo-group setup guide (https://book.jinguo-group.science/stable/chap2/julia-setup/) configures **two mirror env vars**, both pointing at Nanjing University:

```bash
export JULIAUP_SERVER=https://mirror.nju.edu.cn/julia-releases/    # for the juliaup binary download
export JULIA_PKG_SERVER=https://mirrors.nju.edu.cn/julia           # for Pkg downloads
```

`JULIAUP_SERVER` matters for the *initial Julia install* — without it, juliaup downloads from AWS S3 (slow from mainland China). `JULIA_PKG_SERVER` matters for every subsequent `Pkg.add` / `Pkg.instantiate`. The mirror MUST be set before invoking the curl installer; this skill orders step 2 before step 3 when `--region mainland_china`.

This skill applies the NJU mirror automatically when the cluster profile's `region` field is `mainland_china`. For other regions, no mirror is set. For an institutional mirror, pass `--mirror <url>` to override `JULIA_PKG_SERVER`.

## Manifest policy

- **Rule.** `julia-env/Project.toml` is committed (the dependency contract); `julia-env/Manifest.toml` is gitignored and regenerated per machine on first `Pkg.resolve()` + `Pkg.instantiate()`.
- **Reason.** Manifests are pinned to a specific `julia_version` and don't port across Julia major versions, so committing one would break cross-machine setup.
- **Trade-off.** Exact dependency-version reproducibility is sacrificed for cross-platform / version portability — acceptable for a research harness running across laptop + cluster + colleagues' machines.

## Notes

- Both module-loaded Julia (`module load julia/1.10.9`) and juliaup-installed Julia are supported. **Default: juliaup** — user-controlled Julia version makes `Project.toml` compatibility easier across laptop + cluster + collaborators. Use module-loaded Julia ONLY when the admin enforces it or the cluster blocks user binaries.
- This skill does NOT do cluster-level setup (ssh keys, scheduler config, account setup). That's `/onboard`'s cluster-setup stage and the cluster profile's `bootstrap_one_time`.

## Anti-patterns (auto-reject)

<checklist name="anti-patterns">
- Hardcoding a Chinese mirror for every install — only when `region == mainland_china` (or `--mirror` explicit). See [Mirror reference](#mirror-reference).
- Reinstalling Julia when it's already on `$PATH` and at the requested version — be idempotent.
- Editing `~/.julia/config/startup.jl` destructively — preserve unrelated lines, replace ONLY the `JULIA_PKG_SERVER` line.
- Committing `julia-env/Manifest.toml` to the repo — see [Manifest policy](#manifest-policy).
- Bundling cluster bootstrap (clone repo, module load, etc.) into this skill — that's `/onboard` + `bootstrap_one_time`.
</checklist>

<example name="startup-edit bad">
# rewrite ~/.julia/config/startup.jl entirely with just the mirror line
echo 'ENV["JULIA_PKG_SERVER"] = "https://mirrors.nju.edu.cn/julia"' > ~/.julia/config/startup.jl
</example>

<example name="startup-edit good">
# replace ONLY the JULIA_PKG_SERVER line; preserve Revise's try/catch and any user content
# (sed -i.bak is portable across BSD/macOS and GNU/Linux; we remove the backup afterwards)
sed -i.bak '/^ENV\["JULIA_PKG_SERVER"\]/d' ~/.julia/config/startup.jl
echo 'ENV["JULIA_PKG_SERVER"] = "https://mirrors.nju.edu.cn/julia"' >> ~/.julia/config/startup.jl
rm -f ~/.julia/config/startup.jl.bak
</example>
