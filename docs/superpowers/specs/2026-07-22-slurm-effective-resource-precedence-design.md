# Slurm Effective Resource Precedence Fix

## Goal

Make `scripts/harness_slurm.sh submit` derive profile-required GRES from the
partition that Slurm will actually use, while refusing to override directives
from a submission script that cannot be inspected locally.

## Effective resource precedence

For partition selection, later command-line options win. The helper will use
this explicit order:

1. the last partition option in `--extra`;
2. the dedicated `--partition` value;
3. the local script's `#SBATCH --partition` directive; and
4. `scheduler.default_partition` from the cluster profile.

The `--extra` parser will recognize `--partition=value`, `--partition value`,
`-p value`, and `-pvalue`. It will use Python `shlex` so quoted values follow
the same shell-like tokenization already implied by the raw `--extra` string.
Malformed quoting will fail closed with a concise error.

When `--extra` selects the effective partition, the helper will not emit a
lower-precedence generated `--partition` option. The original `--extra` string
will still be appended to the `sbatch` command unchanged.

## Required GRES

The helper will look up `required_gres` using the effective partition above.
It will add that profile value only when neither `--extra` nor the script
contains an explicit `--gres` request. Existing GRES precedence remains:

1. `--extra --gres`;
2. the local script's `#SBATCH --gres`; and
3. the effective partition's profile `required_gres`.

## Script inspection safety

Before resolving partition or GRES directives, `submit` will require
`--script` to name a locally readable regular file. The normal workflow ships
that same relative path to the remote checkout before feasibility testing.

If the local file is absent, submission and `--test-only` both stop before SSH
or `sbatch`. This avoids silently adding command-line profile defaults that
would override directives in an uninspected remote-only script. Remote script
inspection is intentionally excluded because it would add an SSH round trip,
complicate dry-run behavior, and introduce a second quoting boundary.

## Implementation boundaries

- Extend `scripts/cluster_guardrail.py` with a small CLI operation that reads an
  sbatch option from a shell-like argument string.
- Keep TOML parsing in `scripts/cluster_profile.py` and submission mechanics in
  `scripts/harness_slurm.sh`.
- Do not refactor the existing raw-string construction of the complete remote
  command; that broader quoting concern is outside this fix.
- Update `/using-slurm` documentation to state the local-script requirement and
  the precise partition precedence.

## Error handling

- Missing or unreadable local script: exit nonzero with a `submit:` diagnostic.
- Malformed `--extra` quoting: exit nonzero rather than guessing precedence.
- Partition absent from the profile: retain current behavior; omit derived GRES
  and let `sbatch --test-only` report scheduler feasibility.

## Tests

Regression tests will prove:

- `--extra --partition=explicit-gpu` selects `explicit-gpu` and derives its
  required GRES without emitting the profile-default partition;
- space-separated and short `-p` forms resolve with the same precedence;
- the last partition option in `--extra` wins;
- malformed `--extra` quoting fails closed;
- a missing local script stops before a dry-run or real remote submission; and
- existing dedicated CLI, script-directive, profile-default, and GRES
  precedence tests remain green.

Verification will run the focused parser and Slurm-helper tests, the complete
Python test suite, Bash syntax checking, and `git diff --check`.
