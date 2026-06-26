<!-- Method-card template. Axis definitions: ../method-property-checklist.md (M1–M14).
     Inverse model→method map: ../method-property-map.md. Cost derivations & citations:
     ../method-survey.md. Cite keys resolve in ../ref.bib. -->

# [Method name] ([abbrev])

[One line: what the method is and what it is for.]

## Method card

### What it is

[2–4 sentences: the core algorithmic idea — what object it represents/samples, what
it optimizes/evolves/diagonalizes, and what it returns.]

### Properties (M1–M14)

| Axis | Value | Note |
|---|---|---|
| M1 tasks / outputs | [..] | [..] |
| M2 regime | [T=0 / finite-T / real-time] | [..] |
| M3 accuracy class | [exact / variational-upper / certified-lower / controlled / uncontrolled; det/stoch] | [..] |
| M4 dimension fit (A1) | [..] | [where it wins / walls] |
| M5 statistics & local dim (A3) | [..] | [..] |
| M6 entanglement regime (B5) | [area / area+log / volume] | [..] |
| M7 sign-problem dependence (C12) | [needs sign-free / constraint-biased / sign-immune] | [..] |
| M8 symmetry exploitation (C9/C10) | [..] | [..] |
| M9 time complexity | [..] | [..] |
| M10 memory | [..] | [..] |
| M11 control knob | [..] | [error it bounds] |
| M12 scale frontier | [..] | [..] |
| M13 primary approximation / bias | [..] | [controlled?] |
| M14 hard blocker / failure mode | [..] | [..] |

### Cost & scaling
<!-- These four lines must match the M9–M12 rows in the table above (no divergent numbers). -->

- Time: [leading complexity]
- Memory: [leading]
- Control knob: [parameter + error it bounds]
- Scale frontier: [reachable N]

### Accuracy & guarantees

- Class: [exact / variational-upper / certified-lower / controlled / uncontrolled]
- Primary approximation & its control: [..]
- Error scaling: [..]

### Tasks it computes

- [GS energy / spectrum / finite-T / dynamics / spectral fn / exponents / bounds …]

### Recommended for (models / regimes)

- [which model axes A1–D16 / which zoo models this is the method of choice for]

### Key reference

[@citekey] — [one line on why it is the authoritative all-details source].
Rendered: `[path]` _(reused: `../../literature/<family>/<id>.md`; or downloaded
`./<id>_<slug>.md`; or: bib stub — no PDF reachable)_.

### Benchmarks

- [quantity] = [value] ([conditions]) [@source].

## How it is used / Operational

[Owning skill: `/method-*` (+ `/using-*`). Default workflow; verification pointers;
cross-link to the matching `method-survey.md` § and `method-property-map.md`.
For methods outside the core harness skill set, say so plainly.]
