# Tensor-Square Phase Diagram — Status

更新日期：2026-07-29  
状态：`STAGE 0 COMPLETE — STAGE 1 STARTING`

## 当前目标

冻结 tensor-square 模型约定与恒正 oracle，完成 `m=3,4` ED 侦察和 DQMC 小尺寸交叉验证，然后启动双机粗相图扫描。

## 阶段

- [x] Stage 0：oracle、Hermiticity、正规序和数守恒
- [ ] Stage 1：`m=3,4` ED 侦察
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
k = -t(A12 + A23) - (μ/2)I
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
| QMC vs ED | — | — | — | — |

## 正面结果

| Date | Experiment | Model/size | Signal | Evidence | Interpretation | Next test |
|---|---|---|---|---|---|---|
| 2026-07-29 | `stage0-oracle-20260729` | `m=2,3,4` oracle；`m=3` Fock | 恒正、厄米、数守恒与正规序约定全部通过 | `8 passed`；54 个随机历史；近零权重三式一致 | tensor-square 基础设施可冻结，允许进入 ED | `m=3` 全谱粗扫、`m=4` 半填充分块 |

## 已早停方向

尚无。

记录格式：

| Date | Experiment | Stop reason | Minimum evidence | Avoid repeating |
|---|---|---|---|---|

## 运行中任务

`m=3` 全谱 ED 粗扫与 `m=4` 半填充分块侦察。

| Machine | Job / PID | Cells | Started | Progress | Output |
|---|---|---|---|---|---|

## 下一步

1. 运行 `m=3` 全谱和 `m=4` 分块 ED 粗扫描。
2. 依据 avoided crossing、gap 与竞争通道重排选择 DQMC 交叉验证点。
3. 单通道/自由基准无区分力的 cell 立即早停。

## 最近提交

尚无。

| Commit | Branch | Content | Verification |
|---|---|---|---|
