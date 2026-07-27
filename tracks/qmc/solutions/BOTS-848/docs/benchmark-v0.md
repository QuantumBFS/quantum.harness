# Challenge #15 Benchmark v0

> 状态：基准定义；以 GitHub Challenge #15 的最低验收标准为边界。
> 日期：2026-07-27
> 目的：先建立可重复、可判定的最小 benchmark；研究增强项不阻塞通过。
>
> 项目入口：[BOTS:848 Challenge #15](../README.md)

## 1. 固定问题

- Geometry：Haldane sphere。
- Particles：N 个完全极化电子。
- Filling：ν=1/3。
- Flux：2Q=3(N−1)。
- Hilbert space：lowest Landau level（LLL）。
- Interaction：chord-distance Coulomb interaction；背景电荷、能量零点和 sphere density correction 必须在报告中写明。
- Units：e²/(εℓ_B)，并取 ħ=1。
- Target sectors：ground state L=0；最低 excited state L=2。
- Primary quantity：

  Δ₂(N)=E(L=2;N)−E(L=0;N)。

## 2. Benchmark v0 实例

### 必做实例

- N=6，2Q=15。
- 同时运行 ED reference 与 NQS/VMC candidate。

选择 N=6 的原因：它是非平凡、可快速 ED 的小系统，足以验证 L=0/L=2 sector、五重简并、误差传播和完整数据管线；符合 Challenge “one or more N”的最低要求。

### 可选实例

- N=8，2Q=21：用于检查同一实现是否能无人工改写地迁移到第二个 system size。
- N>ED：属于扩展 benchmark，不属于 v0 通过条件。

## 3. Candidate 必交输出

1. E₀=E(L=0) 及 Monte Carlo standard error。
2. 五个 E₂M，M=−2,−1,0,1,2，各自的 standard error。
3. 五分量联合估计的 E₂。
4. Δ₂=E₂−E₀ 及正确传播的 statistical error。
5. ⟨L²⟩、Var(L²)。
6. antisymmetry residual。
7. SO(3) equivariance residual。
8. multiplet splitting：max_M E₂M−min_M E₂M。
9. ED reference：E₀^ED、E₂^ED、Δ₂^ED。
10. 运行配置：seed、样本数、链数、burn-in、blocking/autocorrelation 方法、dtype、硬件和 wall time。

## 4. 硬性通过条件

### A. Ansatz 与问题定义

- 波函数在交换任意两个电子时变号。
- ansatz 严格处于给定 monopole charge Q 和 LLL；若只有 finite-κ leakage/extrapolation，只能标记为 prototype，不能通过 v0 final。
- L=0 和 L=2 必须来自同一文档化的 variational family；允许 shared trunk + sector-specific irrep/reference head。

### B. Spin-2 认证

- excited state 满足 ⟨L²⟩=6 within reported uncertainty。
- 同时报告 Var(L²)，排除只在平均值上偶然等于 6 的 sector mixing。
- 构造并评估 M=−2,…,2 五个分量。
- 五个能量在各自统计误差内相容；不能只训练/报告一个 M。

### C. 对称性实测

- 给出至少一个随机 particle swap test。
- 给出至少一个随机 R∈SO(3) test：
  - L=0 按 scalar 变换；
  - 五分量 L=2 tower 按 D^(2)(R) 混合。
- 测试必须输出数值 residual，不能只引用“by construction”。

### D. 能量与误差

- 报告 E₀、E₂、Δ₂ 和统计误差。
- statistical error 必须来自 blocking、integrated autocorrelation time 或独立链/seed bootstrap；不能把未修正的 sample standard deviation 当成最终 error bar。
- N=6 与 ED 做同一 Hamiltonian、同一归一化约定下的对比。
- 若 NQS 与 ED 不在合并误差内相容，结果仍可记录，但 benchmark 状态为 accuracy failure，不能宣称通过。

### E. 可复现交付

- 一条从干净 checkout 可运行的命令。
- 固定配置文件或完整命令行参数。
- 原始数值结果（机器可读）。
- 简短报告：ansatz、system size、error bar、对称性检查、ED 对比。

## 5. Benchmark 指标

### Pass/fail gates

- `lll_valid`
- `antisymmetry_valid`
- `so3_equivariance_valid`
- `l2_casimir_valid`
- `fivefold_multiplet_valid`
- `mc_error_valid`
- `ed_crosscheck_valid`
- `reproducible_run_valid`

所有 gate 为 true 才算 Benchmark v0 passed。

### 连续评分指标

- `abs_gap_error = |Δ₂^NQS−Δ₂^ED|`
- `ground_energy_error = E₀^NQS−E₀^ED`
- `excited_energy_error = E₂^NQS−E₂^ED`
- `multiplet_splitting`
- `l2_casimir_error = |⟨L²⟩−6|`
- `energy_variance_ground`
- `energy_variance_excited`
- `effective_sample_size_per_second`
- `wall_time`

不在 v0 中人为规定统一的绝对数值阈值。数值相容性用 candidate 自己报告的统计误差和 ED reference 判定；以后收集多个实现后，再根据实测分布冻结 v1 tolerance，避免先拍脑袋设置阈值。

## 6. 不属于 v0 通过条件的研究增强项

- N>ED 与 N→∞ extrapolation。
- chiral metric operators O_±、W_± 和 helicity polarization。
- κ-dependent Landau-level mixing。
- 与 L=N transport gap 的比较。
- 多容量 energy-variance extrapolation。

这些项目可以作为 `extended` 字段和额外排行榜列，但不得让未完成它们的正确最小实现判为失败。

## 7. 推荐实施顺序

1. ED oracle：固定 N=6 Hamiltonian 和能量 convention。
2. 数据 schema：先让 ED 结果通过同一 report/JSON schema。
3. NQS candidate：L=0 与完整 L=2 tower。
4. symmetry gates：swap、rotation、L²、fivefold。
5. VMC statistics：blocking/ESS/error propagation。
6. 一键运行和 benchmark report。

只有 Benchmark v0 稳定通过后，再开启 larger-N、chirality 或 κ 扫描。



