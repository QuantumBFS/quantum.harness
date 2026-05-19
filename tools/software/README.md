# Software Stack Contracts

This directory declares install contracts for canonical software stacks.
The contracts are structured TOML so `/onboard`, `/slurm`, setup skills, and
audit checks can reason about installs without scraping prose.

Design rule:

- Profiles describe user-visible runtime intent: CPU, GPU, multi-process CPU,
  or multi-node GPU.
- Install strategies describe implementation details: package-manager command,
  modules, fallback command.
- Smoke tests state where they must run: login or compute allocation.

The executable source of truth remains the Makefile and setup scripts. Stack
contracts name the command, smoke test, rendered KB reference when available,
official upstream locators, and remote constraints.
Method cards reference stack ids; skills decide when to use or install a stack.

## Required TOML Shape

Every `stacks/*.toml` file must define:

```toml
id = "stack-id"
name = "Human-readable name"
language = "julia"
canonical_for = ["method"]
default_profile = "cpu"

[profiles.cpu]
label = "CPU"
default = true
install = "cpu"
smoke = "cpu"

[profiles.cpu.requirements]
allocation = "login-or-compute"
mpi = false

[install.cpu]
command = "make install stack-id"

[smoke.cpu]
where = "login"
command = "..."

[docs]
kb = "knowledge-base/literature/<method>/<rendered-reference>.md"
official = "https://official-docs.example/"
```

Optional profile fields:

- `fallback_install = ["strategy-id"]`
- `notes = "..."`

Optional install fields:

- `modules = ["cuda", "cudnn"]`
- `notes = "..."`

Optional top-level fields:

- `requires = [{ stack = "stack-id", note = "..." }]` declares prerequisite
  stacks that must already be installed and smoke-tested before this stack's
  install command is run. Use it for dependency order, not for package-manager
  details.

Optional docs fields:

- `kb` points to a tracked rendered Markdown reference and is the in-repo source
  material agents should cite when present.
- `official`, `install`, and `repository` are upstream locators, not replacements
  for a rendered KB entry.
