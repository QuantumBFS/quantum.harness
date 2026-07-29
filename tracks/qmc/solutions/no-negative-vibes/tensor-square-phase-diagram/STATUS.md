# Tensor-Square Phase Diagram — Status

更新日期：2026-07-29  
状态：`STAGE 1 COMPLETE — STAGE 2 STARTING`

## 当前目标

冻结 tensor-square 模型约定与恒正 oracle，完成 `m=3,4` ED 侦察和 DQMC 小尺寸交叉验证，然后启动双机粗相图扫描。

## 阶段

- [x] Stage 0：oracle、Hermiticity、正规序和数守恒
- [x] Stage 1：`m=3,4` ED 侦察
- [ ] Stage 2：DQMC 与 ED 交叉验证
- [ ] Stage 3：双机粗扫描
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
| QMC vs ED | — | — | — | — |

## 正面结果

| Date | Experiment | Model/size | Signal | Evidence | Interpretation | Next test |
|---|---|---|---|---|---|---|
| 2026-07-29 | `stage0-oracle-20260729` | `m=2,3,4` oracle；`m=3` Fock | 恒正、厄米、数守恒与正规序约定全部通过 | `8 passed`；54 个随机历史；近零权重三式一致 | tensor-square 基础设施可冻结，允许进入 ED | `m=3` 全谱粗扫、`m=4` 半填充分块 |
| 2026-07-29 | `stage1-ed-m3` | `m=3,N=4` | `g_B/g_A≈1` 的不同能级 gap 谷、channel/nematic 重排 | `t=0.5`: gap `0.238→0.0244→0.343`；可对易同点 gap `1.078` 且 commutator²≈0 | 非对易竞争候选；不是相声明 | DQMC 验证 `t=0.5,g_B/g_A=1` 与两侧控制 |
| 2026-07-29 | `stage1-ed-m4` | `m=4,N=8` | C4 交替通道重现 gap 谷与通道换序 | `t=1`: gap `1.034→0.507→1.957`；局部 commutator² `O(1e-2)` | 信号不只属于 9 模式种子 | DQMC 验证 `t=1,g_B/g_A=1` |

| Date | Experiment | Stop reason | Minimum evidence | Avoid repeating |
|---|---|---|---|---|
| 2026-07-29 | `m3-v0-symmetric-seed` | P3 对称种子产生大量机器零 gap 与扇区漂移，fidelity 为假异常 | `m=3, v=0` 粗网格在多条线上 `sector_gap < 1e-14` | 不再扩展该线；改用 `v/g1=0.15 diag(-1,0,1)` 并固定列出 `N=4,5` |

## 运行中任务

DQMC 原型与 `m=3,4` ED 交叉验证。

| Machine | Job / PID | Cells | Started | Progress | Output |
|---|---|---|---|---|---|

## 下一步

1. 实现连续高斯 HS 的朴素与 tensor-square 权重路径。
2. 在 `m=3,t=0.5,g_B/g_A=1,v=0.15,μ=0` 比较有限温 ED。
3. 在 `m=4,t=1,g_B/g_A=1,μ=0` 比较低温固定扇区 ED，并保留 `g_B/g_A=0.5,2` 控制。

## 最近提交

尚无。

| Commit | Branch | Content | Verification |
|---|---|---|---|
