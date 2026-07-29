# Tensor-Square Phase Diagram — Status

更新日期：2026-07-29  
状态：`STAGE 2 COMPLETE — STAGE 3 STARTING`

## 当前目标

冻结 tensor-square 模型约定与恒正 oracle，完成 `m=3,4` ED 侦察和 DQMC 小尺寸交叉验证，然后启动双机粗相图扫描。

## 阶段

- [x] Stage 0：oracle、Hermiticity、正规序和数守恒
- [x] Stage 1：`m=3,4` ED 侦察
- [x] Stage 2：DQMC 与 ED 交叉验证
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
| DQMC vs finite-T ED | `m=3, β=2, Δτ=0.2,0.1,0.05` | PASS；E、density、Q-combined 全部 `|z|<1.5` | 4 replicas；最小 direct sign `+1` | `results/stage2_dqmc_validation/aggregate/summary.json` |
| DQMC low-T convergence | `m=4, β=4,8, Δτ=0.1` | PASS；β=8: `E=-17.879(122)` vs ED `-17.8512`；`Q²=1.2348(124)` vs ED `1.2377` | 4 replicas；稳定化 direct/structured log-weight 差 `1.35e-14` | 同上 |
| Weight-path benchmark | `m=3,4,6,8`，500 repeats | tensor-square 路径在 `m=8` 才打平 Python 直接路径；内存节省 `3.0–4.5×` | BLAS 单线程 | `results/stage2_weight_benchmark/aggregate/summary.json` |

## 正面结果

| Date | Experiment | Model/size | Signal | Evidence | Interpretation | Next test |
|---|---|---|---|---|---|---|
| 2026-07-29 | `stage0-oracle-20260729` | `m=2,3,4` oracle；`m=3` Fock | 恒正、厄米、数守恒与正规序约定全部通过 | `8 passed`；54 个随机历史；近零权重三式一致 | tensor-square 基础设施可冻结，允许进入 ED | `m=3` 全谱粗扫、`m=4` 半填充分块 |
| 2026-07-29 | `stage1-ed-m3` | `m=3,N=4` | `g_B/g_A≈1` 的不同能级 gap 谷、channel/nematic 重排 | `t=0.5`: gap `0.238→0.0244→0.343`；可对易同点 gap `1.078` 且 commutator²≈0 | 非对易竞争候选；不是相声明 | DQMC 验证 `t=0.5,g_B/g_A=1` 与两侧控制 |
| 2026-07-29 | `stage1-ed-m4` | `m=4,N=8` | C4 交替通道重现 gap 谷与通道换序 | `t=1`: gap `1.034→0.507→1.957`；局部 commutator² `O(1e-2)` | 信号不只属于 9 模式种子 | DQMC 验证 `t=1,g_B/g_A=1` |
| 2026-07-29 | `stage2-dqmc-ed-m3` | `m=3,β=2` | 三个 Trotter 步长的热力学量均与有限温 ED 相容 | 最坏 `|z|=1.47`；direct sign 全为 `+1` | 连续高斯 HS、Wick 观测量和 checkpoint/resume 路径通过交叉验证 | 启动 `m=4,6,8` 粗扫 |
| 2026-07-29 | `stage2-dqmc-ed-m4` | `m=4,β=4,8` | 降温后 E 与 combined-Q² 向 ED 基态值收敛 | β=8: `E=-17.879(122)`，`Q²=1.2348(124)` | 稳定化低温 DQMC 可用于 β=8 粗扫 | 粗扫中 β≥4 使用稳定化长乘积 |

| Date | Experiment | Stop reason | Minimum evidence | Avoid repeating |
|---|---|---|---|---|
| 2026-07-29 | `m3-v0-symmetric-seed` | P3 对称种子产生大量机器零 gap 与扇区漂移，fidelity 为假异常 | `m=3, v=0` 粗网格在多条线上 `sector_gap < 1e-14` | 不再扩展该线；改用 `v/g1=0.15 diag(-1,0,1)` 并固定列出 `N=4,5` |
| 2026-07-29 | `stage2-beta8-unstabilized` | 长时间片乘积条件数达到 `O(10^17)`，朴素 `I+X⊗X` 退化并产生伪负号/奇异 Green 函数 | 真实 checkpoint：不稳定 direct/structured log-weight 相差 `111.7`；SVD 缩放后两路径同为 `383.5036485799` | β≥4 扫描不再使用朴素长乘积；保留该失败作为稳定化回归 |
| 2026-07-29 | `stage2-weight-python-small-m` | Python 实现中 `m≤6` 的结构化 determinant 未提供 wall-time 加速 | 500 repeats：direct/structured speedup `0.70,0.75,0.83`（m=3,4,6） | 不以小 m 速度作为正面结论；只利用内存优势并在 m=8 以上复测 |

## 运行中任务

双机 `m=4,6,8` 首轮粗相图扫描。

| Machine | Job / PID | Cells | Started | Progress | Output |
|---|---|---|---|---|---|

## 下一步

1. 按批准网格运行 `m=4,6,8`、`β=2,4,8`、五个 `t`、五个 `g_B/g_A`、三个 `μ` 的短链粗扫。
2. 合并 WSL 与 CPU machine 结果，审计 sign、稳定化 residual、热化和有效样本数。
3. 生成粗相图并按尺寸/温度趋势输出幸存参数列表；失败点达到早停条件后不扩展。

## 最近提交

| Commit | Branch | Content | Verification |
|---|---|---|---|
| `9f1a13a` | `work/zibojin/tensor-square-phase-diagram` | Stage 0 oracle 与 Hamiltonian 回归 | `8 passed` |
| `08a9c42` | 同上 | `m=3,4` ED 侦察与候选点 | `11 passed` |
