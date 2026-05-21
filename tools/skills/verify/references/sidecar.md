# sidecar

The audit subagent writes both markdown and TOML sidecar. Top-level `status = "pass"` is required for the gate to pass; `warn` and `fail` block unless the user records an override.

```toml
status = "pass"      # pass | warn | fail
mode = "protocol"    # protocol | plan | kb | script | result | mismatch | close | report | solve
target = "protocol.toml"
hash = "sha256:..."  # target hash when declared by the audit check
author = "<author-identity>"
reviewer = "<reviewer-identity>"
brief = "sha256:..."
coverage = true

[[items]]
id = "source"
status = "pass"

[[items]]
id = "tacits"       # required when method/model values are declared
status = "pass"    # pass only after relevant TACITS.toml signal sweep

[[verdicts]]
claim = "claim.example"
status = "warn"
note = "short explanation"
```

Markdown shape:

```markdown
# /verify report — <artifact> — <date>

**Mode**: protocol | plan | kb | script | result | mismatch | close | report | solve
**Reference**: <path / lines>

| Axis / Row | Status | Severity | Claim ids | Notes |
|---|---|---|---|---|
| Tacits | pass | match | claim.example | methods/models checked; matched tacit ids or `none` |

## Detailed findings
### Axis N — <name>
... verbatim evidence, line numbers, conclusion ...
```

Do not include `Action items` or `Next steps`.
