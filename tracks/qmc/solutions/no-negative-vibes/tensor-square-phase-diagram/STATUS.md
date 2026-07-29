# Tensor-Square Phase Diagram — Status

更新日期：2026-07-29  
状态：`STAGE 3 COMPLETE — FIRST ROUGH MAP AND SURVIVORS READY`

## 当前目标

冻结 tensor-square 模型约定与恒正 oracle，完成 `m=3,4` ED 侦察和 DQMC 小尺寸交叉验证，然后启动双机粗相图扫描。

## 阶段

- [x] Stage 0：oracle、Hermiticity、正规序和数守恒
- [x] Stage 1：`m=3,4` ED 侦察
- [x] Stage 2：DQMC 与 ED 交叉验证
- [x] Stage 3：双机粗扫描
- [ ] Stage 4：幸存者密集扫描
- [ ] Stage 5：有限尺寸标度与独立检查
- [ ] Stage 6：论文包

## 已批准的首个模型

```text
单粒子空间：V⊗V，dim(V)=m
M_A = A⊗I + I⊗A
Q_A = dΓ(M_A)
H = dΓ(k⊗I + I⊗k) - (1/2m)Σ_e g_e Q_e²
m=3 seed:
  A12 = E12 + E21
  A23 = E23 + E32
```

```text
k = -t(A12 + A23) + 0.15·diag(-1,0,1) - (μ/2)I
g1 = 1（能量单位）
g2/g1 = 0, 0.25, 0.5, 1, 2
μ/g1 = -1.5, 0, 1.5（ED 侦察另加 -3…3 扇区边界定位点）
base graph / boundary = P3 开链；单粒子 product graph = P3 □ P3
ensemble / particle number = grand canonical；μ=0 的半填充交叉检查另用固定 N=4,5 扇区
βg1 = 2, 4, 8
Δτg1 = 0.1（交叉验证时另做 0.2, 0.05 控制）
observables = E、density、gap、Q1²、Q2²、{Q1,Q2}/2、fiber nematic²、
              bond response、i[Q1,Q2]²、sign/zero-weight audit
git branch = work/zibojin/tensor-square-phase-diagram
```

## 最新正确性证据

| Check | Instance | Result | Tolerance / uncertainty | Artifact |
|---|---|---|---|---|
| Direct determinant vs factorization | `m=2,3,4`，54 个非对易 5-slice 历史 | PASS；最坏相对差 `1.59e-6`（极端尺度），moderate tests `<3e-9` | 极端尺度容差 `2e-5` | `results/stage0_oracle/aggregate/summary.json` |
| Nonnegative weights | 同上 + 构造的近零点 | PASS；最小随机权重 `1.1456`，近零权重 `2.50e-13` | 负值审计阈值 `-2e-10` | 同上 |
| Hermiticity | `m=3`, `t=0.6`, `g=(1,0.75)`，512 维全 Fock | PASS；max residual `0` | `<2e-14` | 同上 |
| Number conservation | 同一 Hamiltonian | PASS；max commutator `0` | `<2e-14` | 同上 |
| Normal ordering | `m=2` 随机实对称通道 | PASS；max residual `8.88e-16` | `<2e-12` | 同上 |
| ED eigensolver | `m=3` 全扇区；`m=4,N=8` | PASS；max residual `1.96e-14` / `7.27e-10` | `<1e-8` | `results/stage1_ed_m{3,4}/aggregate/summary.json` |
| DQMC vs finite-T ED | `m=3, β=2, Δτ=0.2,0.1,0.05` | PASS；E、density、Q-combined 全部 `|z|<1.5` | 4 replicas；最小 direct sign `+1` | `results/stage2_dqmc_validation/aggregate/summary.json` |
| DQMC low-T convergence | `m=4, β=4,8, Δτ=0.1` | PASS；β=8: `E=-17.879(122)` vs ED `-17.8512`；`Q²=1.2348(124)` vs ED `1.2377` | 4 replicas；稳定化 direct/structured log-weight 差 `1.35e-14` | 同上 |
| Weight-path benchmark | `m=3,4,6,8`，500 repeats | tensor-square 路径在 `m=8` 才打平 Python 直接路径；内存节省 `3.0–4.5×` | BLAS 单线程 | `results/stage2_weight_benchmark/aggregate/summary.json` |
| Coarse-grid completeness | `m=4,6,8` × `β=2,4,8` × 5 `g_B/g_A` × 5 `t/g_A` × 3 `μ/g_A` | PASS；`675/675` complete，0 missing/error/duplicate | WSL 135 + CPU 540 cells | `results/stage3_coarse_20260729/aggregate/summary.json` |
| Coarse-grid determinant audit | 同上 | PASS；minimum direct sign `+1`，0 BROKEN | max per-sample direct/structured log-weight error `9.86e-7`；17 个 β=2 cell 稳定化复跑；density range `[5.54e-9, 1+3.33e-8]` | 同上 |
| Coarse-grid provenance | 同上 | PASS；675 个 cell 均绑定同一干净源码 `b4459ae0d1c64ba021ffce634d26402362575171` | 每个 summary/checkpoint 含运行指纹；两机 manifest 均 `dirty=false` | `results/stage3_coarse_20260729/manifest_{wsl,cpu}.json` |
| Rough-map screen | 75 个 `(g_B/g_A,t/g_A,μ/g_A)` region | 14 SURVIVE，27 EXTEND，34 STOP，0 BROKEN | 每 region 含 3 尺寸 × 3 温度短链 | `results/stage3_coarse_20260729/aggregate/survivors.json` |

## 正面结果

| Date | Experiment | Model/size | Signal | Evidence | Interpretation | Next test |
|---|---|---|---|---|---|---|
| 2026-07-29 | `stage0-oracle-20260729` | `m=2,3,4` oracle；`m=3` Fock | 恒正、厄米、数守恒与正规序约定全部通过 | `8 passed`；54 个随机历史；近零权重三式一致 | tensor-square 基础设施可冻结，允许进入 ED | `m=3` 全谱粗扫、`m=4` 半填充分块 |
| 2026-07-29 | `stage1-ed-m3` | `m=3,N=4` | `g_B/g_A≈1` 的不同能级 gap 谷、channel/nematic 重排 | `t=0.5`: gap `0.238→0.0244→0.343`；可对易同点 gap `1.078` 且 commutator²≈0 | 非对易竞争候选；不是相声明 | DQMC 验证 `t=0.5,g_B/g_A=1` 与两侧控制 |
| 2026-07-29 | `stage1-ed-m4` | `m=4,N=8` | C4 交替通道重现 gap 谷与通道换序 | `t=1`: gap `1.034→0.507→1.957`；局部 commutator² `O(1e-2)` | 信号不只属于 9 模式种子 | DQMC 验证 `t=1,g_B/g_A=1` |
| 2026-07-29 | `stage2-dqmc-ed-m3` | `m=3,β=2` | 三个 Trotter 步长的热力学量均与有限温 ED 相容 | 最坏 `|z|=1.47`；direct sign 全为 `+1` | 连续高斯 HS、Wick 观测量和 checkpoint/resume 路径通过交叉验证 | 启动 `m=4,6,8` 粗扫 |
| 2026-07-29 | `stage2-dqmc-ed-m4` | `m=4,β=4,8` | 降温后 E 与 combined-Q² 向 ED 基态值收敛 | β=8: `E=-17.879(122)`，`Q²=1.2348(124)` | 稳定化低温 DQMC 可用于 β=8 粗扫 | 粗扫中 β≥4 使用稳定化长乘积 |
| 2026-07-29 | `stage3-coarse-half-filled-ridge` | `m=4,6,8`，`μ=0` | `g_B/g_A=0.25–0.5, t/g_A=0.25–0.5` 出现一致的尺寸/降温增强 | `m=8` 的 β8−β2 combined-Q² 增量 `0.296–0.519`（`5.26–10.81σ`）；m4→m8 增量 `1.18–1.25` | 首个稳健正面候选带；仍是短链筛选，不是相声明 | 加长 `(g,t)≈(0.25–1,0.25–1)` 半填充网格并做 susceptibility/Binder |
| 2026-07-29 | `stage3-coarse-channel-reordering` | `g_B/g_A≈1`，三个填充 | channel balance 在竞争区跨越零并与 ED 的 `g_B/g_A≈1` gap 谷相接 | 14 个 SURVIVE 中 8 个含 reordering 标记；代表点 `(g,t,μ)=(1,1,-1.5)` 同时有 β8−β2 `0.135`（`11.6σ`） | 次级候选：可能是竞争/混合响应，也可能受短链自相关影响 | 对 `μ=±1.5` 成对复测，排查粒子-空穴非对称的统计来源 |

| Date | Experiment | Stop reason | Minimum evidence | Avoid repeating |
|---|---|---|---|---|
| 2026-07-29 | `m3-v0-symmetric-seed` | P3 对称种子产生大量机器零 gap 与扇区漂移，fidelity 为假异常 | `m=3, v=0` 粗网格在多条线上 `sector_gap < 1e-14` | 不再扩展该线；改用 `v/g1=0.15 diag(-1,0,1)` 并固定列出 `N=4,5` |
| 2026-07-29 | `stage2-beta8-unstabilized` | 长时间片乘积条件数达到 `O(10^17)`，朴素 `I+X⊗X` 退化并产生伪负号/奇异 Green 函数 | 真实 checkpoint：不稳定 direct/structured log-weight 相差 `111.7`；SVD 缩放后两路径同为 `383.5036485799` | β≥4 扫描不再使用朴素长乘积；保留该失败作为稳定化回归 |
| 2026-07-29 | `stage2-weight-python-small-m` | Python 实现中 `m≤6` 的结构化 determinant 未提供 wall-time 加速 | 500 repeats：direct/structured speedup `0.70,0.75,0.83`（m=3,4,6） | 不以小 m 速度作为正面结论；只利用内存优势并在 m=8 以上复测 |
| 2026-07-29 | `stage3-control-lines` | `g_B=0` 单通道线和 `t=0` 线只作为基准，不进入密集预算 | 全部 30 个对应 region/cell-group 已计算；Stage 1 已对 `t=0` 早停 | 粗图继续显示控制数据，但分类强制 STOP；不重复扩展 |
| 2026-07-29 | `stage3-short-chain-low-ESS` | 27 个 region 只有 EXTEND；部分 β=8,m=8 有效样本 `<4` 或接受率 `>0.995` | 代表点 `(g,t,μ)=(0.5,1,0)` 有强趋势但 ESS `2.97` | 只选择与核心候选带相邻的少数 EXTEND 加长，不给全部 27 点预算 |
| 2026-07-29 | `stage3-density-audit-roundoff` | 稳定化 `t=0` 对照点出现单样本密度 `1+3.33e-8`，属于双精度舍入而非物理越界 | 同点平均密度 `0.999874`、log-weight error `5.68e-14`、direct sign `+1`；回归测试保留 `2e-6` 越界拦截 | 密度审计容差统一为 `1e-7`；不把纳米级舍入误标为 BROKEN，也不放宽权重/符号审计 |

## 运行中任务

无。双机粗扫已结束并完成回收、聚合与绘图。

| Machine | Job / PID | Cells | Started | Progress | Output |
|---|---|---|---|---|---|

## 下一步

1. Stage 4 第一优先：半填充核心带 `g_B/g_A=0.25,0.5,1`、`t/g_A=0.25,0.5,1`，包含 SURVIVE 和相邻低-ESS EXTEND。
2. 第二优先：`g_B/g_A≈1,t/g_A≈1,μ/g_A=±1.5` 的成对长链，验证通道换序与粒子-空穴一致性。
3. 增加统计量与一个更大尺寸，计算 susceptibility、Binder ratio 和相关长度 proxy；继续保留 `g_B=0`、`t=0` 控制但不扩展。

## 最近提交

| Commit | Branch | Content | Verification |
|---|---|---|---|
| `9f1a13a` | `work/zibojin/tensor-square-phase-diagram` | Stage 0 oracle 与 Hamiltonian 回归 | `8 passed` |
| `08a9c42` | 同上 | `m=3,4` ED 侦察与候选点 | `11 passed` |
| `efb2e18` | 同上 | 稳定化 DQMC/ED 交叉验证与权重基准 | `13 passed` |
| `5e8cefb` | 同上 | 双机粗扫代码、首轮聚合与候选分类 | `26 passed`；675/675 |
| `37ae584` | 同上 | 运行指纹、干净源码约束与逐样本审计 | `26 passed` |
| `b4459ae` | 同上 | 密度舍入容差与聚合源码溯源 | `27 passed`；两机干净重跑 |

## Stage 4 round 0 — frozen production contract (2026-07-29)

- Stage 3 delivery was re-verified at `3322167`; the 675 fingerprinted coarse
  cells were not rerun.
- Frozen Stage 4 pilot grid: 90 cells (54 half-filled core and 36 matched
  `mu/g_A = +/-1.5` competition cells), two pilot replicas per cell.
- Frozen production rule: four new replicas, worst-observable tau-driven
  extension to ESS >= 40 per replica, with recoverable extension only up to the
  preregistered caps.
- New audited observables: exact Gaussian first-to-fourth channel moments,
  central-moment Binder ratios, contact-subtracted HS static susceptibility,
  staggered/neighbor structure factors, and an open-chain second-moment
  correlation-length proxy.
- Production cannot start from a self-asserted plan: it must revalidate all 180
  pilot summaries, exact seeds/configs/fingerprints/common source, full-summary
  digest, recomputed budgets, and equal matched-`mu` budgets.
- Independent code review found four Important issues in the first
  implementation; all were fixed. Final re-review: PASS, no remaining
  Critical/Important findings.
- Verification: `49 passed`; runner and pilot aggregator compile cleanly.
- Commits: `4b7a0bb`, `8037e4a`, `bd0bcb0`, pushed to
  `work/zibojin/tensor-square-phase-diagram`.
- No Stage 4 physics result has been inspected yet. Next action is a one-cell
  clean-commit smoke run, followed by the two-machine 180-replica pilot.

## Stage 4 rounds 1-3 — dense scan and m=10 judgement (2026-07-29)

Current status: `STAGE 4 STATISTICAL EARLY STOP — NO STAGE 5 PHASE CLAIM`

- Pilot completed 180/180 replicas with zero errors. Provenance and frozen
  budget validation released 44/90 cells; 46/90 stopped at the pilot
  autocorrelation budget gate.
- Production completed all 176 requested replicas: 95 passed ESS, 81 reached
  the frozen autocorrelation cap, and zero had worker/determinant errors.
- At the strict cell level, 15/44 released cells had all four replicas pass and
  29/44 had at least one early stop. Minimum passing ESS was 40.03, direct sign
  remained +1, and maximum log-weight error was 1.14e-13.
- Updated candidate ranking: `SURVIVE=0`, `EXTEND=0`, `STOP=21`. These are
  statistical-only stops caused by incomplete audited endpoint grids, not
  physical no-go statements.
- A single numerical-only `m=10, beta=4` sentinel was released at
  `(g_B/g_A,t/g_A,mu/g_A)=(0.25,0.5,0)`. Two of four replicas passed; two hit
  the autocorrelation cap. The passing subset has `Q=2.9168(90)` versus
  `m=8: 2.3603(42)`, while staggered structure and `xi/m` also increase.
- Because the complete four-replica m=10 audit failed and the required
  `beta=8` endpoints are censored, the first finite-size judgement is:
  **达到早停；当前信号按有限尺寸或普通 crossover 处理，不支持继续
  Stage 5 的相主张。**
- No m=12 expansion, literature novelty claim, or PRL package is released.
- Remote verification: 60 tests passed on the clean CPU sentinel commit
  `dc87c6c`; all numerical work, aggregation, and plotting ran on the approved
  WSL/CPU machines. The local Windows control host ran no numerical job.
- Artifacts: `results/stage4_20260729/`; scientific note:
  `notes/stage4_dense_results.md`.
- Code/result commits `3a3fce2`, `dc87c6c`, and `b1c2b88` were pushed to
  `work/zibojin/tensor-square-phase-diagram`; PR #178 was not modified.
