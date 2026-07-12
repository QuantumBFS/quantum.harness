# [Model name] — exact-solution oracle

Technique: [T1–T7] · Tier: [A/B/C/D] · Script: [S/P/T]

## Hamiltonian & conventions

$$ H = [\dots] $$

Conventions: [...] — see `.knowledge/conventions.md`.
[If a model-zoo card exists: "Physics card: `.knowledge/models/<name>/MODEL.md`."]

## Solvability statement

[Technique + what exactly is exact.] **Not exact:** [what is not].

## Exact results

- [quantity] : $[closed form]$ [@citekey]

## Oracle script

`python oracle.py --L 16 --h 1.0` → prints `[keys]`. Importable: `compute(**params)`.
Self-test anchors: [list].
[T-flag cards: "No oracle script — tabulated benchmarks below."]

## Benchmarks

| Quantity | Params | Exact value | Source |
|---|---|---|---|

## Verification recipes

- To check a [method] run at [size/params], compare [quantity] via `oracle.py [flags]`; tolerance [..].

## Key reference

[@citekey] — [why authoritative]. Rendered: _(Wave 3)_.
