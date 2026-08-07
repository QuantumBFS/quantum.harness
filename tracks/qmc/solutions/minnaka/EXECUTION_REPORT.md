# Execution report

## Fixed physical setup

| Item | 2x2 exhaustive audit | 4x4 production audit |
|---|---|---|
| Model | Repulsive Hubbard | Repulsive Hubbard |
| Boundaries | PBC x PBC | PBC x PBC |
| Filling | Half filled, 2 up + 2 down | Half filled, 8 up + 8 down |
| Coupling | $t=1,\ U=8$ | $t=1,\ U=4$ |
| HS field | Real binary Hirsch spin | Real binary Hirsch spin |
| Time step | 0.1 | 0.05 |
| Projection | 6 slices | $\Theta=10,\ \beta=1$, 420 slices |
| Trial/constraint | RHF-x, RHF-y, UHF | $U_{\mathrm{eff}}=4$ UHF |

## Executed stages

| Stage | Work performed | Output used in the report |
|---|---|---|
| 2x2 exact enumeration | $2^{24}=16,777,216$ paths for each of three trials | Exact worst-one-percent physical-weight/CP-efficiency distribution |
| ALF free/UHF calibration | 128 independent chains, 20 retained cross-chain bins | $E=-13.62340(345)$ at 420 slices |
| Initial 4x4 path archive | 128 TI chains, 8 saved paths per chain | 1,024 complete 6,720-field paths |
| C++ CP replay | Complete UHF-CP proposal replay of every archived path | 976 positive paths in the efficiency analysis |
| Local trace audit | 5 low-efficiency cases + 5 matched controls | Conditional-probability event statistics |
| Direct reweighting | 1,920 independent chains x 50 paths | 96,000-path ratio-of-sums energy |

The ALF free/UHF calibration used 128 single-thread tasks on one node and
completed in about 6.3 minutes.  The free/free confirmation completed in about
3.8 minutes.

The direct-reweight production used ten parallel replicas and 1,920 CPU cores
in total.  The slowest replica completed in 28 minutes 28 seconds; the merge
took 25 seconds.  Cluster job ID: `416553`.

## Numerical results

| Estimator | Energy | Uncertainty source |
|---|---:|---|
| Exact finite-size value | −13.62192 | Exact diagonalization benchmark |
| ALF free/UHF PQMC | −13.623403 ± 0.003450 | 20 cross-chain bins |
| ALF free/free PQMC | −13.626885 ± 0.003640 | 20 cross-chain bins |
| Direct symmetric-cut reweighting (no CP rejection) | **−13.615477 ± 0.014050** | 50 cross-chain bins |
| Direct MATLAB UHF-CP | −13.468324 ± 0.003115 | Independent CP runs |
| Published UHF/spin-HS CP | −13.478 ± 0.002 | Qin, Shi, and Zhang (2016) |
| Published GHF/spin-HS CP | −13.623 ± 0.001 | Qin, Shi, and Zhang (2016) |

For the direct reweighting:

| Diagnostic | Value |
|---|---:|
| Paths | 96,000 |
| Effective sample size | 95,727.0 |
| Global ratio estimate | −13.615465 |
| Leave-one-chain uncertainty | 0.013070 |
| Nonpositive or nonfinite weights | 0 |
| Largest normalized weight | $1.44\times10^{-5}$ |
| Weight share of top one percent | 1.185% |

The reweighted estimate is statistically consistent with the exact energy and
is separated from direct UHF-CP by more than ten combined standard errors.

## Ergodicity diagnostics

### Exact 2x2 worst-efficiency tail

| Trial | Total paths | Worst 1% | Weight $\ge\langle D\rangle$ | Weight $\ge2\langle D\rangle$ |
|---|---:|---:|---:|---:|
| RHF-x | 16,777,216 | 167,773 | 4,140 | 2,282 |
| RHF-y | 16,777,216 | 167,773 | 4,618 | 2,430 |
| UHF | 16,777,216 | 167,773 | 799 | 316 |

### 4x4 sampled paths

| Quantity | Result |
|---|---:|
| Alive, retained TI paths | 976 |
| Worst-efficiency paths | 10 |
| Worst paths above median physical weight | 8 |
| Worst bottlenecks in final quarter | 10 |
| Distinct bottleneck field masks | 10 |
| Spearman: efficiency vs prefix barrier | −0.933099 |
| Spearman: efficiency vs $\log_{10}\sigma_{\min}$ | +0.758385 |
| Spearman: CP log probability vs physical log weight | +0.271929 |

The ten worst bottleneck layers do not share an all-$+1$, all-$-1$, or
checkerboard pattern.  Their local spatial descriptors remain close to the
ordinary-path population.  The reproducible signature is the cumulative
late-time proposal deficit.

### Detailed local traces

| Quantity | Five low-efficiency paths | Five matched controls |
|---|---:|---:|
| Mean total surprisal | 6,748.10 | 5,619.02 |
| Mean count, $q<10^{-3}$ | 46.4 | 23.2 |
| Mean count, $q<10^{-6}$ | 2.2 | 0.8 |
| Mean largest event surprisal | 16.57 | 14.02 |
| Mean top-100 event share | 11.21% | 10.53% |

These measurements identify accumulation over many low-probability events as
the dominant mechanism.  A small number of very rare events aggravates the
problem but does not account for most of the path-level deficit.

## Artifact inventory

- `figures/`: three report figures in PDF and PNG.
- `data/`: compact CSV/JSON evidence and provenance.
- `scripts/make_report_figures.py`: deterministic figure regeneration.
- `test/cpmc_path_audit/`: C++17 enumerator, replayer, path diagnostics, and
  tests.
- `test/alf_hirsch_binary/`: ALF 2.4 binary-Hirsch patches and regression
  workflow.
- `test/pqmc_cp_bridge/`: ALF/PQMC archive, C++ replay, MATLAB CP, statistics,
  and Slurm workflow.

Raw chain output, compiled binaries, and full path archives are deliberately
excluded from Git.
