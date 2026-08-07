# Overnight reproduction — results tables

Generated from `results.csv` by `make_results_md.py`. Do not hand-edit:
`results.csv` is the source of truth.

- protocol_sha256 `d9e9728b357e91a7d9c161749a546f385bd2e1c90aead8bd94c9489a711dbea3`
- qmbcertify_commit `be63c27ece7322effe6d95c69ce6c3c5d8d92c14` (unmodified)
- julia `1.12.6`, mosek `Mosek=11.2.0;MosekTools=0.15.10`
- cpu `Intel(R) Core(TM) i9-14900HX`

## 1. Fixed parameters (CONFIG A; identical across every cell)

| parameter | value | note |
|---|---|---|
| `d` | `4` | relaxation order; get_basis has no branch above d>3, so d>=4 is equivalent |
| `extra` | `4` | r = extra + 1; max separation of two-site basis words |
| `r` | `5` | effective reach |
| `three_type` | `[1, 1]` | adjacent triple for three-body basis words |
| `SU2_symmetry` | `false` |  |
| `lattice` | `chain` |  |
| `Gram` | `false` |  |
| `correlation` | `false` |  |
| `J2` | `0` | plain Heisenberg, no next-nearest-neighbour term |
| `supp` | `[[1, 4]]` | sigma^x_1 sigma^x_2 (index = 3*(site-1)+component) |
| `coe` | `[0.75]` | SU(2) collapses (1/4)*sum_a onto one component -> 3/4 |
| `mosek_tol_pfeas` | `1.0e-8` |  |
| `mosek_tol_dfeas` | `1.0e-8` |  |
| `mosek_tol_relgap` | `1.0e-8` |  |
| `lol` | `N` | tracks the cell's N |

## 2. Per-cell varied knobs and measured data

| cell | N | rdm | pso | lso | opt | dev vs Table3 New | delta = opt_A - opt_cell | termination | solve_s | wall_s | RSS GB | limit_hit |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| gate | 10 | 10 | 3 | true | -0.45154459452835116 | +5.472e-09 | - | OPTIMAL | 20.9 | 2067 | 1.1 | - |
| step2_A | 14 | 10 | 3 | true | -0.44739636848093645 | +3.152e-08 | - | OPTIMAL | 145.9 | 2190 | 1.1 | - |
| step2_B | 14 | false | 3 | true | -0.4473985952430302 | -2.195e-06 | +2.2268e-06 | SLOW_PROGRESS | 2.6 | 5 | 13.8 | - |
| step3_C | 14 | 10 | 0 | true | -0.4473963899319207 | +1.007e-08 | +2.1451e-08 | OPTIMAL | 89.1 | 2192 | 13.9 | - |
| step3_D | 14 | 10 | 3 | false | -0.44739634903517306 | +5.096e-08 | -1.9446e-08 | OPTIMAL | 135.5 | 2185 | 15.7 | - |
| ladder | 18 | 10 | 3 | true | (none) | - | - | *N/A* | nan | 600 | 3.2 | MAX_WALL_S |
| ladder | 22 | 10 | 3 | true | (none) | - | - | *N/A* | nan | 600 | 1.6 | MAX_WALL_S |
| ladder | 26 | 10 | 3 | true | (none) | - | - | *N/A* | nan | 600 | 1.6 | MAX_WALL_S |
| ladder | 30 | 10 | 3 | true | (none) | - | - | *N/A* | nan | 600 | 1.7 | MAX_WALL_S |
| ladder | 34 | 10 | 3 | true | (none) | - | - | *N/A* | nan | 600 | 1.8 | MAX_WALL_S |
| ladder | 40 | 10 | 3 | true | (none) | - | - | *N/A* | nan | 600 | 2.1 | MAX_WALL_S |
| ladder | 46 | 10 | 3 | true | (none) | - | - | *N/A* | nan | 600 | 2.2 | MAX_WALL_S |
| ladder | 50 | 10 | 3 | true | (none) | - | - | *N/A* | nan | 600 | 2.4 | MAX_WALL_S |
| lad | 10 | 8 | 3 | true | -0.45154457774281065 | +2.226e-08 | - | OPTIMAL | 2.2 | 12 | 1.4 | - |
| lad | 14 | 8 | 3 | true | -0.4473967708312458 | -3.708e-07 | +4.0235e-07 | SLOW_PROGRESS | 5.7 | 16 | 1.9 | - |
| lad | 18 | 8 | 3 | true | -0.4457104197357416 | -1.920e-06 | - | SLOW_PROGRESS | 11.1 | 22 | 2.8 | - |
| lad | 22 | 8 | 3 | true | -0.4448640232152412 | -5.523e-06 | - | SLOW_PROGRESS | 19.5 | 36 | 3.8 | - |
| lad | 26 | 8 | 3 | true | -0.4443800955269053 | -8.696e-06 | - | SLOW_PROGRESS | 32.6 | 53 | 5.2 | - |
| lad | 30 | 8 | 3 | true | -0.44407763514631926 | -1.084e-05 | - | SLOW_PROGRESS | 44.0 | 65 | 8.9 | - |
| lad | 34 | 8 | 3 | true | -0.4438777732472986 | -1.457e-05 | - | SLOW_PROGRESS | 71.8 | 99 | 11.4 | - |
| lad | 40 | 8 | 3 | true | -0.44368276029850706 | -1.786e-05 | - | SLOW_PROGRESS | 128.4 | 178 | 16.7 | - |
| lad | 46 | 8 | 3 | true | (none) | - | - | *N/A* | nan | 86 | 18.0 | MAX_RSS_GB |

**Killed rows.** Cells with `limit_hit=MAX_WALL_S` and no `opt` were killed
during construction and never reached MOSEK. `results.csv` records
`termination_status=OPTIMAL` for them, which is FALSE — the parser treats an
absent warning line as OPTIMAL, valid only when a solve actually ran. Shown
as *N/A* here; the CSV rows are left unedited and corrected in `LOG.md`.

**RSS caveat.** step2_B / step3_C / step3_D values are cumulative process
memory, not per-cell (the pre-fix `@async` monitor under-sampled). Only the
ladder rows use the thread-based monitor and are per-cell.

## 3. Solver residuals (what actually bounds the trustworthy digits)

| cell | pfeas | dfeas | duality gap (MU) | termination |
|---|---|---|---|---|
| gate | 3.4e-9 | 1.6e-10 | 9.4e-12 | OPTIMAL |
| step2_A | 3.4e-9 | 5.0e-10 | 6.9e-12 | OPTIMAL |
| step2_B | 1.2e-8 | 1.6e-9 | 3.1e-11 | SLOW_PROGRESS |
| step3_C | 1.1e-8 | 2.5e-7 | 6.3e-12 | OPTIMAL |
| step3_D | 5.4e-9 | 4.9e-9 | 1.2e-11 | OPTIMAL |
| lad | 4.5e-9 | 5.5e-9 | 1.9e-11 | OPTIMAL |
| lad | 9.8e-9 | 9.1e-10 | 2.6e-11 | SLOW_PROGRESS |
| lad | 3.0e-8 | 7.4e-10 | 4.3e-11 | SLOW_PROGRESS |
| lad | 2.0e-8 | 1.9e-10 | 3.3e-11 | SLOW_PROGRESS |
| lad | 1.3e-7 | 1.1e-9 | 3.9e-11 | SLOW_PROGRESS |
| lad | 2.8e-7 | 6.9e-10 | 8.9e-11 | SLOW_PROGRESS |
| lad | 1.0e-7 | 3.8e-9 | 5.1e-11 | SLOW_PROGRESS |
| lad | 1.7e-7 | 4.5e-9 | 1.3e-10 | SLOW_PROGRESS |

Declared tolerance is 1e-8. Any difference at or below ~1e-8 is not
resolvable: `delta_RDM` (~1e-6) is, `delta_pso` and `delta_lso` (~1e-8)
are not, and the negative sign of `delta_lso` is numerical noise.

## 4. Table 3 reference values (arXiv:2604.01555)

| N | DMRG | SDP Old | SDP New | reproduced? |
|---|---|---|---|---|
| 10 | -0.4515446 | -0.4515446 | -0.4515446 | yes |
| 14 | -0.4473964 | -0.4474032 | -0.4473964 | yes |
| 18 | -0.4457083 | -0.4457344 | -0.4457085 | no — no opt produced |
| 22 | -0.4448582 | -0.4448981 | -0.4448585 | no — no opt produced |
| 26 | -0.4443707 | -0.4444334 | -0.4443714 | no — no opt produced |
| 30 | -0.4440654 | -0.4441512 | -0.4440668 | no — no opt produced |
| 34 | -0.4438616 | -0.4439644 | -0.4438632 | no — no opt produced |
| 40 | -0.443663 | -0.443782 | -0.4436649 | no — no opt produced |
| 46 | -0.443537 | -0.4436656 | -0.4435397 | no — no opt produced |
| 50 | -0.4434771 | -0.4436101 | -0.4434798 | no — no opt produced |

## 5. Provenance

| field | value |
|---|---|
| `harness_commit` | `aacfde820fb8b339a9fc3fe6e2b9ad9c2251892e` |
| `qmbcertify_commit` | `be63c27ece7322effe6d95c69ce6c3c5d8d92c14` |
| `project_toml_sha256` | `e65de1408ebaa9331ce2d7c5d1f3d6087909425a2d55682e8fc64a05d9143fa7` |
| `manifest_toml_sha256` | `f3053e2a84a5dfcb8dd575009ea707f7e437ad85f81c74f047d5562062110ccb` |
| `julia_version` | `1.12.6` |
| `mosek_version` | `Mosek=11.2.0;MosekTools=0.15.10` |
| `hostname` | `localhost` |
| `script_sha256` (gate) | `6fb508f9be9e73164f4db1c9eb5dba0693fa98234f4c954616d29bb69a38ebf8` |
| `script_sha256` (step2_A) | `5610877df426bf3d70cff416c6ce792a4691cc0b19c152034ce303e71ec50407` |
| `script_sha256` (ladder) | `32126b5a6340fd354e0086f843bdb3fa7be7168ce70c7e25fd862ee4fad97a6d` |

`script_sha256` differs across groups because the harness was changed twice
mid-run (add `mosek_version`; thread-based monitor + enforced wall kill).
Project/Manifest hashes and `qmbcertify_commit` are identical throughout, so
the groups remain comparable.
