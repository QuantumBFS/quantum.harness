# OmniEvolve — #71 Occam's Circuit

## Team

| | |
|---|---|
| **Team name** | OmniEvolve |
| **Members** | 結凪 (UynajGI) |

## Challenge

| Row | |
|---|---|
| **Challenge** | Recover hidden Boolean arithmetic functions from polynomially many input–output pairs by evolving minimal quantum circuits, testing Occam's razor as an explicit optimization objective. |
| **Catalog issue** | Addresses #71 — released by Jin-Guo Liu, HKUST(GZ). |
| **Track** | `qcs` — per the issue's own instruction ("work under `tracks/qcs/solutions/<your-team>/`"). |

## Approach

OmniEvolve: evolutionary algorithm discovery powered by LLM-guided code mutation. The optimizer evolves circuit-construction programs that are scored on gate count (minimality) × test accuracy (generalization), directly mapping the gate-count-vs-generalization curve the challenge asks for.
