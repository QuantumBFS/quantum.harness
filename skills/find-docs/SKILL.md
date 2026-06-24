---
name: find-docs
description: Use when working with harness-relevant scientific/physics software APIs, local KB or reference snippets, examples, package capabilities, setup, migrations, or hard-to-find package documentation before writing code.
---

# Find Docs

Use this skill for harness-relevant or hard-to-find software API documentation. It is copied from Context7's upstream `find-docs` skill and adapted for this harness's local software knowledge base.

## Scope

Use this skill for:

- Physics, numerical, simulation, and scientific-computing packages used by this harness.
- APIs covered by `.knowledge/software/` or `skills/using-*/references/`.
- Before writing code that depends on a package-specific API, configuration, CLI, example, or capability.
- Hard-to-find, niche, fast-moving, or ambiguous package documentation.

Do not use this skill for common infrastructure or general programming knowledge unless the user explicitly asks for current docs or the answer is genuinely version-sensitive. Examples: `git`, basic shell, Makefile syntax, common Node/npm usage, Python standard library basics, or routine OS commands.

## Source Priority

Use exactly this order for software API questions:

1. **Local KB first.** Consult the relevant local software note or stack reference as the curated starting map. These files may already contain rendered snippets, worked examples, package-specific notes, and upstream links:
   - `.knowledge/software/<package>-api.md` for surveyed packages.
   - `skills/using-<tool>/references/<tool>-api.md` and `skills/using-<tool>/stack.toml` for harness stack packages.
2. **Context7 next.** Use Context7 when local KB is missing, incomplete, stale-looking, ambiguous, or exact API syntax matters.
3. **Official docs last.** Use upstream official docs when Context7 cannot find a canonical/version-appropriate result, gives weak coverage, or appears non-official.

Do not use training memory as an API source when one of these sources can answer the question.

## Context7 Workflow

Two-step process: resolve the library name to an ID, then query docs with that ID.

```bash
# Step 1: Resolve library ID
npx ctx7@latest library <name> "<query>"

# Step 2: Query documentation
npx ctx7@latest docs <libraryId> "<query>"
```

Call `ctx7 library` first to obtain a valid library ID unless the user explicitly provides a library ID in `/org/project` or `/org/project/version` format.

Do not run more than three Context7 commands per question. If Context7 does not produce a good result within that budget, move to official docs.

## Selecting a Context7 Library

Prefer the result that best matches:

- Exact package or project name.
- Query-relevant description.
- High or Medium source reputation.
- Higher code snippet count and benchmark score.
- User-requested or installed version, when available.

Reject or treat as weak:

- Similar but noncanonical projects.
- Unknown or low-reputation sources for critical API details.
- Missing version when the question is version-specific.
- Generic snippets that do not answer the actual API question.

## Query Rules

Use the user's full API question when possible. Include the package name, API surface, configuration key, or command being checked.

Do not include secrets, private data, or proprietary code in Context7 queries.

Good:

```bash
npx ctx7@latest library TeNPy "SpinModel coupling parameters and DMRG engine options"
npx ctx7@latest docs /tenpy/tenpy "SpinModel coupling parameters and DMRG engine options"
```

Bad:

```bash
npx ctx7@latest library tenpy "hooks"
```

## Error Handling

Context7 has quotas and can fail due to rate limits, network problems, service errors, or ambiguous index results. Do not spend repeated attempts on it.

If Context7 fails with quota or rate-limit errors, say that the Context7 quota/rate limit was hit and suggest `npx ctx7@latest login` or the documented Context7 environment variable for higher limits. Then move to official docs rather than answering from memory.

If `node`, `npm`, or `npx` is unavailable, run `make install node` first. This installs Node.js 18+ and npm for Context7 CLI lookups on macOS, Linux, and WSL. On native Windows, install Node.js 18+ manually or use WSL.

If Context7 fails with DNS, host resolution, or fetch errors inside the sandbox, rerun the same command outside the sandbox once before falling back.

## Common Mistakes

- Skipping local KB and losing harness-specific package context.
- Treating local rendered markdown as proof of API correctness.
- Accepting the first Context7 result without checking canonical source and version fit.
- Staying in Context7 after weak results instead of opening official docs.
