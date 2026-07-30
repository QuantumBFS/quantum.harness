# Exact 347-gate Occam arithmetic circuits

## Team

| | |
|---|---|
| Team name | `Genshin_Impact` |
| Members | Kexiang Mao ([@Mao-Kexiang](https://github.com/Mao-Kexiang)) |
| Track | `qcs` |

Kexiang is discussing a possible future team-up with Zongyue Liu. This submission does not list Zongyue as a member or co-author without mutual confirmation; it credits his prior circuit baseline explicitly below.

## Challenge

| | |
|---|---|
| Challenge | Recover and minimize the four hidden arithmetic circuits |
| Catalog issue | [QuantumBFS/quantum.harness issue #71](https://github.com/QuantumBFS/quantum.harness/issues/71) |
| Solution path | `tracks/qcs/solutions/Genshin_Impact-71/` |

## Bottom line

This submission identifies all four hidden functions, supplies exact predictions and legal fanin-2 netlists, and reduces the independently audited public 355-gate baseline to **347 gates**:

| Instance | Recovered function | Baseline | This submission | Reduction |
|---|---|---:|---:|---:|
| A | `x + y` | 37 | 37 | 0 |
| B | `abs(x - y)` | 49 | 49 | 0 |
| C | `x * y` | 156 | **152** | −4 |
| D | `x^2 + y^2` | 113 | **109** | −4 |
| Total | — | 355 | **347** | **−8** |

All four canonical circuits pass exhaustive direct-formula verification: 87,040 input assignments and 764,928 output bits checked with zero mismatches. No canonical circuit contains a dead gate, constant gate, duplicate gate function, or complementary gate-function pair.

This is an improvement over the best public baseline we located and froze on 2026-07-30. It is not a proof that 347 is globally optimal. A=37 matches the known `5n - 3` adder bound in the relevant basis; B, C, and D remain open.

## Prior work and credit

The 37/49/156/113 = 355 baseline is from **Zongyue Liu's [PR #156](https://github.com/QuantumBFS/quantum.harness/pull/156)**.

We treated all external PR material as untrusted. We did not execute competitor code or instructions. We extracted only strict plain-text netlists and independently verified them against direct arithmetic formulas. The submitted A37 and B49 netlists retain those verified pure-data circuits. The new circuit contribution here is:

- C: 156 → 152 gates;
- D: 113 → 109 gates.

## 1. Verified result

| Instance | Gates | Assignments | Output bits | Netlist SHA-256 |
|---|---:|---:|---:|---|
| A | 37 | 65,536 | 589,824 | `56c95acceeedb40f54fdae2e5fc2840d1bf58e0989f46a950e6a56742fd20e24` |
| B | 49 | 16,384 | 114,688 | `289b60494a703cf7f74a4aef2f540d225aeff22d86c4d709aaa5b661cc69a0a7` |
| C | 152 | 4,096 | 49,152 | `67540307369fedfffdb2b1a6473eff5e0bbfeb0e4873d03fddbeceb653cd071c` |
| D | 109 | 1,024 | 11,264 | `cd3f317f4a0b88818e54869e40b4550fd67549f8eb4a5eb02c74db4ec6864dbd` |

The immutable evidence snapshot is in `frontier-347/`; `SHA256SUMS` and `COMPLETE` are emitted only after every audit and manifest stage succeeds.

The practice instances also pass every input:

| Practice circuit | Gates | Audit |
|---|---:|---|
| 4-bit addition | 17 | 256/256 exact; official commitment matches |
| 4×4 multiplication | 64 | 256/256 exact; official commitment matches |

These practice counts are not claimed globally optimal.

## 2. How the reduction was found

The successful route is relation-SAT local resynthesis through a pinned eSLIM build, combined with immediate rebasing after each verified improvement.

The C search is a branching history, not a linear `156 → 154 → 153 → 152` claim:

```text
C156
├── size 5, job 43027 task 5  → C154
│   └── size 7, job 43188 task 3 → C152
└── size 8, job 43027 task 8  → C153
```

D113 → D109 came from job 42633 at size 6. A second D stage found no further reduction. A third C stage tested sizes 4–8 from C152; all five jobs completed as `VALIDATED_NO_IMPROVEMENT`.

The main empirical lesson is to run several local scales in parallel and rebase immediately. A small rewrite changes downstream support, candidate divisors, relations, and the next useful windows. Continuing only on the old parent leaves reductions on the table.

## 3. Every suggested method family was attempted

| Method family | Actual experiment | Outcome |
|---|---|---|
| Tensor-network/MPS completion | 64 continuous MPS configurations, rank/order audits, Boolean distillation | No full-domain exact learned model; useful structural diagnostic |
| Exact Boolean/GF(2) tensor networks | Exact TT/graph contraction and legal-gate conversion | Exact, but A/B/C/D cost 114/488/4,831/1,132 gates |
| BDD/ZDD learning | Shared BDD, minimum-width/reachable-state MaxSAT, genuine shared ZDD | Completed versions generalize poorly and map to large circuits; three exact jobs remain research-in-progress |
| SAT exact synthesis | MFFC, divisor, and safe multi-root window searches | Many local UNSAT certificates; no additional canonical reduction |
| Independent 0-1 IP/MILP | Explicit ports, phases, gate selection, and truth values in HiGHS | 18 windows: 13 proven infeasible, 5 limits, 0 candidate |
| ABC logic synthesis | EXDC, exact ROBDD→ABC, and direct C152/D109 optimization | Direct frontier run remains 152/109; other exact mappings are larger |
| Espresso | Berkeley 1994 build attempted repeatedly | Infrastructure failure from a modern-libc `strlen` declaration conflict; no scientific result claimed |
| Symbolic/template hybrid | Frozen train-only semantic dispatch into generic arithmetic templates | Exact templates 17/64/37/50/168/127, then relation-SAT supplies the frontier compression |

The issue's tensor-network hint was therefore taken seriously. Exact ranks reveal useful structure: interleaving inputs lowers A's maximum TT rank from 255 to 3 and gives B rank 5, while C remains around 57–61. The right use of TN here is to rank cuts and windows, not to equate tensor rank with final six-gate cost.

## 4. Correctness lesson: safe local boundaries

An early window encoding allowed descendants of target roots as external divisors. That can create cycles and false SAT candidates. Those candidates are invalid and are not shipped.

A safe replacement window must satisfy all of:

1. its boundary excludes removed gates;
2. its boundary excludes descendants of every target root, preserving acyclicity;
3. every root is uniquely determined by the boundary on the reachable input space.

The final safe-v3 finite-budget results are:

| Parent | Windows | UNSAT | TIMEOUT | Candidates |
|---|---:|---:|---:|---:|
| C156 | 100 | 99 | 1 | 0 |
| C154 | 100 | 97 | 3 | 0 |
| D109 | 79 | 64 | 15 | 0 |

UNSAT means only the fixed parent hash, roots, boundary, gate library, and budget are impossible. A timeout is not an infeasibility proof, and certificates do not automatically transfer to a new parent.

## 5. Reproduce

From the repository root:

```bash
python tracks/qcs/solutions/Genshin_Impact-71/search/audit_arithmetic_formula.py \
  A tracks/qcs/solutions/Genshin_Impact-71/frontier-347/netlists/mystery-A.txt
python tracks/qcs/solutions/Genshin_Impact-71/search/audit_arithmetic_formula.py \
  B tracks/qcs/solutions/Genshin_Impact-71/frontier-347/netlists/mystery-B.txt
python tracks/qcs/solutions/Genshin_Impact-71/search/audit_arithmetic_formula.py \
  C tracks/qcs/solutions/Genshin_Impact-71/frontier-347/netlists/mystery-C.txt
python tracks/qcs/solutions/Genshin_Impact-71/search/audit_arithmetic_formula.py \
  D tracks/qcs/solutions/Genshin_Impact-71/frontier-347/netlists/mystery-D.txt

cd tracks/qcs/solutions/Genshin_Impact-71/frontier-347
sha256sum -c SHA256SUMS
```

Core regression suites:

```bash
python -m unittest discover \
  -s tracks/qcs/solutions/Genshin_Impact-71/search \
  -p 'test_*.py'
python tracks/qcs/solutions/Genshin_Impact-71/routes/exact_tn/test_exact_tn.py -v
python tracks/qcs/solutions/Genshin_Impact-71/routes/symbolic_hybrid/test_routes.py -v
python tracks/qcs/solutions/Genshin_Impact-71/search/ip_milp/test_exact_milp.py -v
```

Heavy searches were run through Slurm on `t02-server`, with seed 42 as the canonical root seed. The eSLIM source was pinned to commit `51e9f77429627473db623058157b66a1192cbb59`.

## 6. File map

| Path | Role |
|---|---|
| `mystery-{A,B,C,D}.txt` | Submission-ready canonical circuits |
| `predictions/mystery-*/test_outputs.csv` | Predicted hidden outputs |
| `frontier-347/` | Netlists, four direct-formula audits, manifest, hashes, completion sentinel |
| `search/audit_arithmetic_formula.py` | Independent exhaustive arithmetic verifier |
| `search/bridge.py` | Strict netlist/BLIF/eSLIM bridge |
| `search/*safe*v3*` | Acyclic, functionally sufficient exact-window workflow |
| `search/ip_milp/` | Independent exact 0-1 MILP route and report |
| `tensor_network/` | Approximate MPS experiments and rank diagnostics |
| `routes/exact_tn/` | Exact Boolean/GF(2) tensor-network route |
| `search/bdd_route/` | BDD/ZDD/MaxSAT route |
| `routes/symbolic_hybrid/` | Arithmetic templates, ABC, and Espresso route |

Generated row-level results and solver logs remain under the gitignored `results/occam71/` tree on `t02-server`; compact final evidence is tracked here.

## 7. Issue #71 deliverable audit

| Required deliverable | Status | Evidence |
|---|---|---|
| `mystery-*.txt` legal circuits | Complete | Four root netlists and `frontier-347/` |
| Predicted `test_outputs.csv` | Complete | `predictions/mystery-*/` |
| Search scripts | Complete | SAT/eSLIM, TN, BDD/ZDD, MILP, ABC/template routes |
| Pitch-style README | Complete | This document |
| Hidden-function beliefs | Complete and commitment-checked | A add, B absolute difference, C multiply, D sum of squares |
| Exact hidden accuracy | Complete | Direct-formula exhaustive audits, zero mismatches |
| Gate-count improvement | Complete | 355 → 347 relative to the frozen public baseline |

## 8. Claim boundary and next work

This work does not prove global optimality for B, C, or D; does not turn TIMEOUT into UNSAT; and does not count BDD nodes, ABC internals, PLA cubes, or TN rank as legal gates.

Most promising next steps:

1. regenerate safe-v3 windows on C152;
2. add exact-TT separator scores to C window ranking;
3. preserve SAT/MILP UNSAT certificates as a parent-hash-bound cache;
4. repair or replace the Espresso build;
5. continue multi-scale immediate-rebase search for C151 and D108.

## 9. Suggested reading order

1. `frontier-347/manifest.json` and the four audits;
2. this README, Sections 2–4;
3. `tensor_network/TN_RESULTS.md`;
4. `routes/exact_tn/README.md`;
5. `search/ip_milp/REPORT.md`;
