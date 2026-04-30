---
name: onboard
description: Use when the user is new to the harness, asks "where do I start", or opens with an unclear / empty problem. Routes them to the right problem skill without architecture lecture or tutorial.
---

# Onboard

First-touch intake for the harness. Get the user productive on a real problem within one exchange. No tutorial, no architecture lecture.

## When to activate

- "I'm new here" / "where do I start" / "how do I use this".
- Empty or unclear opening.
- User explicitly invokes `/onboard` or asks for orientation.

## Workflow

1. **Check the install.** Verify Julia + ITensors are present (`julia --version`, `julia --project=julia-env -e 'using ITensors'`). If missing, run `make install julia` and `make install itensors`. Don't block the conversation on these — explain in one line and keep going.

2. **Ask one question** — open, short:
   > "What problem are you trying to solve?"

3. **Route to the matched skill.** Infer the model or physics topic from the answer and hand off. The matched skill takes over. If ambiguous, use `AskUserQuestion` with 2-3 candidate skills as options — don't list all 13.

4. **If nothing fits**, be honest in one line — "That's outside current scope (ground-state lattice problems). Want me to try an off-skill approach, or help you reframe?"

## What this skill does NOT do

- Lecture about the harness architecture.
- Walk through a tutorial calculation.
- Demand the user read AGENTS.md or the README first.
- Force the install to complete before any conversation.

The agent's job here is to start solving a real problem as fast as possible. If a model or physics skill applies, this skill should be a single short exchange, then it exits.

## Related skills

All `tools/skills/problems/models/*` and `tools/skills/problems/physics/*` skills are the routing targets. After the handoff, the chosen skill runs the workflow; this skill does not stay involved.
