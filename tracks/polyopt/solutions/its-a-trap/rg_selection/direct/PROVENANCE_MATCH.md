# T0 — PROVENANCE MATCH: reuse of morning A/B arms for the DirectCG comparison

Verdict: **MATCH — A@14, B@14, A@20, B@20 from
`rg_selection/results/replacement_solve.csv` are reused; not re-run.**

| signature element | morning replacement arms | direct-MVP arms | match |
|---|---|---|---|
| chassis | d=4, rdm=false, pso=0, lso=false | same | ✓ |
| extra formula | A: N÷2−1; B: r_of(N)−1 (explicit kwarg) | same formulas in direct_mvp.jl | ✓ |
| vspace | :stock (A, B) | :stock (A, B) | ✓ |
| builder | build_rg_selection_model, rg_selection/src/rg_builder.jl — file unchanged between both runs (extra-kwarg version, committed 06e335f; no edits since) | same file | ✓ |
| quotient/solver/env | be63c27 pin, Mosek 11.2, julia-env, same host, tol 1e-8 | same | ✓ |
| live-override evidence | A@14 (E=−0.44741734, r=7) ≠ B@14 (E=−0.44746412, r=2) — the extra kwarg demonstrably acted | — | ✓ |
| config hashes | replacement_configs.jsonl sha16 rows 6d985fe1 (A@14), c7f360bd (B@14), a2b0991c (A@20), 9535bf2d (B@20) | direct arms print the same resolved kwargs | ✓ |

Consequence (per the tier plan): reused rows d(14) = +4.679e-05,
d(20) = +1.566e-04, A/B build rows at N=14/20/26/30 from
replacement_build.csv. Direct-campaign C/C4/D rows appended to
`direct/solve_results.csv` reference these as their A/B comparators.
