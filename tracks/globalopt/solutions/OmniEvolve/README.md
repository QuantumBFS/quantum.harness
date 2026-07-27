# OmniEvolve — #117 Lennard-Jones Cluster Global Optimization

## Team

| | |
|---|---|
| **Team name** | OmniEvolve |
| **Members** | 結凪 (UynajGI) |

## Challenge

| Row | |
|---|---|
| **Challenge** | Discover record-beating Lennard-Jones cluster ground-state geometries using evolutionary code optimization (OmniEvolve/AlphaEvolve-style LLM-driven algorithm discovery). |
| **Catalog issue** | Addresses #117 — released by Lei Wang (王磊), IOP CAS. |
| **Track** | `globalopt` — from the issue's Method field (Global optimization / basin-hopping). |

## Approach

OmniEvolve: evolutionary algorithm discovery powered by LLM-guided code mutation and multi-population island-model search. The optimizer evolves *algorithms* (Python programs) that are evaluated against LJ energy landscapes, selecting for both solution quality and computational efficiency.
