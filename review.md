# QMC 赛道与挑战 #15 复现审核

- 审核日期：2026-07-30
- 审核者：Codex
- 审核对象：`tracks/qmc/solutions/Plasma-Team/`、相关 `tracks/qmc/results/`、CPMC-Lab Figure 4 复现材料、本地 Git 状态及 PR #208
- 审核性质：代码、产物、统计证据与交付状态的独立审阅

## 1. 最终结论

**整体结论：不接受为“QMC 赛道与挑战 #15 已完整复现”。**

当前成果可以接受为：

> **有限尺寸、完整枚举的 SO(3) 投影神经变分基准，附 CPMC-Lab Figure 4 的条件复现。**

它已经给出了可信的有限尺寸物理结果，尤其是挑战 #15 中的有限尺寸能隙、`L²=6` 和五重态结构；但尚未满足完整复现所要求的独立性、可扩展 NQS/VMC、严格输入旋转等变性、手性完整验证、受控热力学极限、失败闭合的自动验收，以及可从公开 PR 干净重跑的交付要求。

| 审核项 | 结论 | 摘要 |
|---|---|---|
| CPMC-Lab Figure 4 | **有条件通过** | 参数和主要趋势可信，但导数处理、统计诊断、独立参照和干净重跑链条不完整 |
| 挑战 #15 基础有限尺寸结果 | **部分通过** | 有可信的有限尺寸能隙、`L²=6` 和五重态构造证据 |
| 挑战 #15 强目标 | **不通过严格验收** | 可扩展 NQS/VMC、神经网络输入等变性、完整手性和受控外推均未完成 |
| 代码内部一致性 | **通过** | 本地 35 项测试全部通过，核心小系统代数与数据流一致 |
| 自动验收可靠性 | **不通过** | 优化失败和部分 CPMC 失败仍可能以成功状态结束 |
| 可复现交付 / PR | **不通过** | PR #208 截至审核时只提交登记 README，主要实现仍未进入该 PR |

## 2. 我的复现验收标准

以下标准用于判断“结果看起来合理”与“他人可以独立复现并严格验收”之间的差别。

### 2.1 科学设置一致性

必须明确并逐项匹配原任务或论文中的：

- 哈密顿量和相互作用定义；
- 几何、磁通、边界条件和粒子数；
- 单位、归一化和能量零点；
- 目标量、量子数扇区与基准曲线；
- 任何近似、截断或替代模型。

只复现定性趋势而没有说明定义差异，不能视为完整复现。

### 2.2 数值正确性

结果必须有足够的数值证据，包括：

- 优化是否真正收敛；
- 能量方差、残差或本征方程误差；
- Monte Carlo 自相关、有效样本量和分块误差；
- 步长、walker 数、网络宽度、随机种子等敏感性；
- 统计误差和系统误差分别报告。

仅给出很多小数位，或只报告抽样均值的标准误，不等于高精度物理解。

### 2.3 独立交叉验证

交叉验证必须尽量避免共享同一物理内核。若 NQS 与 ED 共用赝势、pair table 和哈密顿量构造器，它们可以验证优化器和状态表示，但无法排除共同的符号、归一化或单位错误。

严格通过至少需要一种真正独立的参照，例如：

- 单独实现的 ED；
- 文献原始数值表；
- 不共享相互作用构造代码的计算；
- 可追溯的外部标准程序结果。

### 2.4 方法与声明一致

代码实际执行的方法必须与 README、报告和 PR 中的声明一致。特别是：

- “VMC”应包含真实的采样驱动优化，而不是完整状态向量的确定性期望值；
- “可扩展 NQS”不能依赖完整枚举固定粒子数 Fock 空间；
- “SO(3) 等变网络”应验证旋转后的输入或电子构型，而不仅是输出态经投影后满足固定 `L²`；
- “手性 NQS 结果”不能仅由 ED 子程序给出。

### 2.5 可复现性与来源追踪

陌生审阅者应能从干净 checkout 开始，按照记录命令得到同类结果。至少需要：

- 锁定或精确记录依赖版本；
- 完整运行命令、随机种子、停止条件和容差；
- Python、NumPy、SciPy、SymPy、平台和 Git commit；
- 外部程序的准确版本、来源、hash 或 commit；
- 原始数据、派生数据、绘图脚本和报告之间的清晰映射；
- 结果文件的校验和或可持久访问位置。

### 2.6 验收程序必须“失败闭合”

任何关键失败都必须产生非零退出码，并阻止结果被标记为完成。至少包括：

- 优化器未收敛；
- NaN/Inf；
- 方差或残差超阈值；
- 关键数据点缺失；
- 子任务为 `partial` 或 `failed`；
- 报告生成只完成了部分面板。

### 2.7 报告诚信

报告必须清楚区分：

- 直接计算量与派生量；
- NQS 结果与 ED 结果；
- Monte Carlo 抽样噪声与变分/训练误差；
- 定性证据与定量验收；
- 已完成目标与未来桥接方案。

### 2.8 交付完整性

要声称挑战已提交，相关代码、测试、配置和最小证据必须实际进入目标分支或 PR。只存在于本地工作树、忽略目录或未跟踪目录的成果，不计入公开交付。

### 2.9 判定标签

- **通过（PASS）**：主要要求有直接证据，验证可重复，失败路径可靠。
- **部分通过（PARTIAL）**：核心方向正确且有实质结果，但仍缺少一个或多个关键证据。
- **不通过（FAIL）**：未实现要求、声明与实现不符、无法公开重跑，或验收程序可能误报成功。

## 3. 审核范围与实际检查

本次检查包括：

- 阅读挑战 #15 方案、源代码、测试、报告和结果 JSON；
- 阅读 CPMC-Lab Figure 4 的 MATLAB 包装器、原始 block 数据、派生脚本和图片材料；
- 检查本地 Git 分支、未跟踪文件和 PR #208 的公开交付状态；
- 对 Python 源码执行语法检查，对 PowerShell 脚本执行解析检查；
- 在本地环境运行测试：**35 passed in 6.38 s**；
- 对 CPMC block 数据做只读统计复核，并检查热力学外推的模型敏感性。

测试环境记录为：Python 3.12.12、NumPy 2.5.1、SciPy 1.18.0、SymPy 1.14.0、pytest 9.1.1。

本次没有重新执行耗时数小时的 N=8/9 训练，也没有重新运行完整 MATLAB CPMC 任务。因此，对这些部分的结论基于已有原始产物、脚本、日志和统计复核，而不是第二次端到端计算。

## 4. 挑战 #15 审核

### 4.1 已经成立的结果

以下结果有较强的本地证据：

- 反对称性由有序 LLL Fock determinant 基底保证；
- 有限尺寸基态、`L=2` 激发态与能隙得到明确数值；
- 投影后的目标态满足 `L²=6`；
- 从最高权态经降算符构造了五个 `M=-2,-1,0,1,2` 分量；
- 小系统 NQS 与 ED 的能量和态结构一致；
- N=7 的强结果文件给出了五重态构造证据。

对应证据主要位于：

- `tracks/qmc/solutions/Plasma-Team/REPORT.md`
- `tracks/qmc/results/20260729-chiral-graviton-strong/nqs-multiplet-n7.json`
- `tracks/qmc/solutions/Plasma-Team/src/chiral_graviton/`

因此，**有限尺寸能隙、`L²=6` 和五重态作为构造性结果可以接受**。

### 4.2 实际方法不是可扩展 VMC

当前主要实现枚举完整固定 `M` 的 Fock 空间，显式构造稀疏哈密顿量，并用完整振幅向量计算 `H @ psi` 和确定性能量目标。所谓 Monte Carlo 估计，是优化完成后从已经枚举的概率分布中独立抽样，并非采样驱动的 VMC 训练。

关键位置：

- `tracks/qmc/solutions/Plasma-Team/src/chiral_graviton/nqs.py:27`
- `tracks/qmc/solutions/Plasma-Team/src/chiral_graviton/nqs.py:162`
- `tracks/qmc/solutions/Plasma-Team/src/chiral_graviton/nqs.py:173`
- `tracks/qmc/solutions/Plasma-Team/src/chiral_graviton/nqs.py:253`
- `tracks/qmc/solutions/Plasma-Team/src/chiral_graviton/scalable_nqs.py:15`

这仍然是一个真实的神经变分态，不是硬编码 ED 本征向量；但其计算复杂度依赖完整空间枚举，不能作为挑战强目标中的可扩展 NQS/VMC 实现。

**判定：基础有限尺寸神经变分基准部分通过；可扩展 VMC/NQS 不通过。**

### 4.3 SO(3) 性质是输出投影，不是输入等变网络

网络主体是对占据向量作用的普通共享 MLP，随后把状态精确投影到 `ker(L_+)`。当前 `equivariance_error` 实际检查的是投影态的 `L²` 偏差；通用轴旋转也在同一角动量表示内部完成，没有将旋转后的电子坐标或输入构型重新送入网络比较。

关键位置：

- `tracks/qmc/solutions/Plasma-Team/src/chiral_graviton/nqs.py:147`
- `tracks/qmc/solutions/Plasma-Team/src/chiral_graviton/nqs.py:153`
- `tracks/qmc/solutions/Plasma-Team/src/chiral_graviton/nqs.py:244`
- `tracks/qmc/solutions/Plasma-Team/src/chiral_graviton/cli.py:123`

所以可以准确声明“最终态经精确 SO(3) 投影并属于正确不可约表示”，但不能据此声明“神经网络对旋转输入本身严格等变”。

**判定：SO(3) 投影态通过；神经网络输入等变性未证明。**

### 4.4 手性证据仅为部分完成

当前手性命令调用的是 ED `solve_fixed_l`，不是 NQS 求得的手性响应；扰动只涉及 `m=1 ↔ 3` 的 parent channel，并不是完整有限球面 Coulomb 度量导数。

关键位置：

- `tracks/qmc/solutions/Plasma-Team/src/chiral_graviton/cli.py:158`
- `tracks/qmc/solutions/Plasma-Team/src/chiral_graviton/chirality.py:13`
- `tracks/qmc/solutions/Plasma-Team/src/chiral_graviton/chirality.py:22`

已有极点不对称比值提供了有意义的定性手性证据，但它应标记为 **ED 代理量**，不能作为完整 NQS 手性验收。

**判定：部分通过。**

### 4.5 热力学极限尚不受控

对 N=4…9 的外推对拟合模型和奇偶子序列较敏感：

- 全数据线性外推：0.12887
- 偶数序列：0.12692
- 奇数序列：0.13609
- 二次外推：0.14223
- 模型包络约：0.01336
- 单一回归误差约：0.00353

证据文件：`tracks/qmc/results/20260729-chiral-graviton-strong/scaling_fit.json`。

此外，N=4…8 主要是 ED，只有 N=9 是 NQS。因此当前结果更接近“有限尺寸 ED 序列加一个 NQS 延伸点”，不足以证明可扩展 NQS 已经控制了 `N→∞`。

N=9 报告的约 `6.64e-9` 误差仅是从固定枚举分布后验抽样得到的 Monte Carlo 标准误，没有覆盖网络表达误差、优化误差、随机重启差异和系统外推误差。以该误差支持过多有效数字会造成精度高估。

**判定：热力学趋势有参考价值，严格外推不通过。**

### 4.6 ED 交叉检查不是完全独立 oracle

NQS 和 ED 共用了赝势、pair table 与哈密顿量构造器。该检查能有效发现优化器或状态表示问题，但无法发现共同物理内核中的归一化、符号或单位错误。

因此 README 中的“independent oracle”应改为“shared-kernel exact diagonalization cross-check”，或者增加真正独立实现。

### 4.7 挑战 #15 分项矩阵

| 要求 | 判定 | 说明 |
|---|---|---|
| 费米反对称性 | PASS | 由有序 Fock 基底保证 |
| 有限尺寸 `E0/E2/gap` | PASS | 有直接计算和小系统交叉检查 |
| `L²=6` | PASS | 精确投影后成立 |
| 五重简并结构 | PASS | 以降算符构造得到五个分量 |
| 小 N ED 对照 | PASS（有保留） | 数值一致，但共享物理内核 |
| Monte Carlo 误差 | PARTIAL | 只有固定态后验 IID 抽样误差 |
| 神经网络输入 SO(3) 等变 | FAIL / 未证明 | 当前验证的是输出态投影性质 |
| 可扩展 VMC/NQS | FAIL | 依赖完整 Fock 空间枚举 |
| 手性 | PARTIAL | ED 代理量和单一 parent channel |
| `N→∞` | PARTIAL | 模型敏感且仅一个超出主要 ED 序列的 NQS 点 |
| 公开 PR 交付 | FAIL | 主体实现未进入 PR #208 |

## 5. CPMC-Lab Figure 4 审核

### 5.1 成立的部分

本地设置与论文示例的主要参数一致：

- 16-site 一维 Hubbard 系统；
- `N_up=5`、`N_down=7`；
- `Nwlk=5000`；
- `dtau=0.01`；
- U=0…8 共 9 个点；
- 每个点保留 MAT 文件和 150 个 block。

U=0 与解析值之差约 `8e-13`，总能量及派生曲线的定性行为与 Figure 4 一致。这说明包装器、数据读取和主要物理趋势是可信的。

### 5.2 尚未满足完整复现的部分

1. Figure 4(a) 最终图只绘制 U=0、2、4、6、8，虽然本地实际存在 9 个整数 U 点。
2. ED 曲线来自数字化，不是本地独立 ED；其提取过程、原始点和误差传播不够完整。
3. 面板 (a) 使用手工设定的 ±0.10，(b)/(c) 使用 ±0.01，而不是由全部统计和数值系统误差推导。
4. (b)/(c) 使用步长 `h=1` 的五点四阶及端点差分。替换合理差分方案时，部分派生值变化约 0.008–0.054t，明显大于多数报告的 Monte Carlo SEM；该差分系统误差没有进入最终误差棒。
5. 缺少正式 blocking/autocorrelation 报告。大多数 lag-1 相关较小，但 U=3 约为 0.264；U=6 的前后半段差异约 2.86σ，10-block 批处理 SE 约 0.00202，高于报告的 0.00161。该现象不足以否定结果，但需要平台期诊断、额外种子或 `dtau/walker` 敏感性检查。
6. 包装器对 U=1…8 基本直接标为接受，异常被捕获后不重新抛出；finalizer 对 `partial` 状态仍可能完成并写出 `FINALIZED`。
7. CPMC 复现目录当前未跟踪，外部包也被忽略；缺少从干净 checkout 开始的包来源、准确版本、hash 和完整命令。`run.json` 标为 CPMC-Lab 2.0，而本地源文件注释显示 v1.0，需要核实。

相关实现：

- `tracks/qmc/solutions/Plasma-Team/cpmc_lab_fig4/finalize_cpmc_fig4.py:13`
- `tracks/qmc/solutions/Plasma-Team/cpmc_lab_fig4/finalize_cpmc_fig4abc.py:49`
- `tracks/qmc/solutions/Plasma-Team/cpmc_lab_fig4/run_cpmc_fig4_point.m:122`
- `tracks/qmc/solutions/Plasma-Team/cpmc_lab_fig4/monitor_cpmc_fig4.ps1:55`

**CPMC 结论：主要参数、U=0 校验和定性趋势通过；完整独立复现仅有条件通过。**

## 6. 代码与自动验收审核

### 6.1 正面结果

- 本地测试：35 项全部通过；
- Python 源码语法检查通过；
- PowerShell 脚本解析通过；
- 小系统哈密顿量、角动量算符、投影和结果序列具有较好的内部一致性。

### 6.2 优化失败仍可能返回成功

CLI 记录了 `optimizer_success`，但最终退出条件主要检查对称性。以 `max_iterations=0` 进行审计测试时，优化器明确失败、能量方差约 `3.57e-4`，而对称性误差仍约 `5.33e-15`；按当前逻辑该任务可以返回 0。

关键位置：

- `tracks/qmc/solutions/Plasma-Team/src/chiral_graviton/cli.py:94`
- `tracks/qmc/solutions/Plasma-Team/src/chiral_graviton/cli.py:123`
- `tracks/qmc/solutions/Plasma-Team/src/chiral_graviton/cli.py:239`

这是严格验收中的阻断问题。

### 6.3 验证脚本不是可靠质量门

`scripts/verify.ps1` 抑制错误并打印分数，但没有可靠阈值和非零失败退出；`verify_research.ps1` 使用固定目录并只做较弱 JSON 阈值检查。当前脚本适合作为报告助手，不适合作为 CI 验收门。

### 6.4 元数据与环境不完整

`pyproject.toml` 只给出依赖下界，没有 lockfile、容器或精确 requirements。CLI 元数据主要记录 Python、NumPy 和硬编码包版本，缺少 SciPy、SymPy、Git commit、时间戳、平台、最大迭代数、容差及 ED 罚项等关键配置。

另外，`validate` 对 NaN/Inf、优化状态、残差、单位和方法来源的检查不足。

### 6.5 测试覆盖缺口

当前测试以小 N 和核心代数为主，尚未覆盖：

- N=8/9 的实际训练与报告链条；
- 优化失败必须非零退出；
- CPMC `partial/failed` 不得 finalise；
- verifier 阈值失败；
- NaN/Inf 和缺失元数据；
- 从干净环境执行完整最小复现。

## 7. Git 与 PR 交付状态

截至审核时，公开 PR #208 为开放状态，只有 1 个提交和 1 个变更文件：

- `tracks/qmc/solutions/Plasma-Team/README.md`
- PR：<https://github.com/QuantumBFS/quantum.harness/pull/208>

主要实现存在于本地分支后续提交或未跟踪目录中，尤其 CPMC 复现目录尚未被 Git 跟踪。因此，公开 PR 不能支持审阅者复跑本报告中的主体结果。

同时，PR/README 中描述的 Slater + backflow + Jastrow、CG message-passing 方案，与本地实际的有序 LLL Fock determinant、共享 MLP 和 `ker(L_+)` 精确投影不一致。应更新公开描述，使其准确反映实现。

**交付判定：不通过。**

## 8. 必须修复的优先级

### P0：阻断验收

1. 将正确的 solution 代码、测试、配置和必要的 CPMC 包装器提交到 PR 分支，并更新 PR 方法说明。
2. 所有入口改为失败闭合：优化失败、非有限值、方差/残差超阈值、CPMC `partial/failed` 均返回非零；不得写 `FINALIZED`。
3. 为上述失败路径添加自动测试。

### P1：完整复现链条

1. 增加真实的旋转输入/电子构型等变性测试；若暂不实现，应将声明改为“精确 SO(3) 投影 NQS”。
2. 提供锁定环境、干净安装命令、完整运行命令和结果元数据，记录 Git commit 与外部包 hash。
3. CPMC Figure 4(a) 绘制全部 9 个 U 点；保存数字化 ED 的原始点和提取来源。
4. 对导数给出差分方案敏感性和系统误差；对 block 数据做 blocking/自相关分析，并至少补充一个随机种子或 `dtau/walker` 敏感性点。

### P2：挑战强目标

1. 增加不共享物理内核的 ED 或其他独立参照。
2. 实现不枚举完整 Hilbert 空间的 autoregressive/MCMC NQS，并在多个超过 ED 能力的 N 上展示标度。
3. 用 NQS 而非 ED 计算手性响应，并实现完整的 `s2±` / Coulomb 度量导数。
4. 用多个大 N、奇偶分序列和模型比较给出受控的热力学极限及系统误差。

## 9. 可接受的当前成果表述

在完成 P0/P1 前，建议使用以下表述：

> 本工作实现了有限尺寸、完整 Fock 空间枚举下的 SO(3) 精确投影神经变分态，复现了目标 `L=2` 激发的有限尺寸能隙与五重态结构；同时对 CPMC-Lab Figure 4 给出了参数一致、趋势可信但仍需补充统计和来源追踪的条件复现。当前结果不代表已完成可扩展 VMC、神经网络输入等变性、完整 NQS 手性响应或受控热力学极限。

## 10. 审核边界

本次审核以只读检查和测试为主。除新增本文件 `review.md` 外，没有修改现有源码、结果、用户已有 Git 变更，也没有推送、提交或改写分支历史。

---

## 11. Revalidation Addendum — 2026-07-30

### 11.1 Purpose and baseline

This addendum revalidates the current QMC worktree against the acceptance
standards in Section 2 after two new local commits:

- a974109 — experiment: remediate graviton review findings
- 84ae498 — experiment: record graviton review convergence

Commit a974109 contains the substantive Challenge #15 remediation. Commit
84ae498 only records project-development orchestration state and does not add
scientific implementation.

The revalidation covered the current local branch
challenge/qmc-chiral-graviton-clean at HEAD
84ae4988bf44d5f0bb751696dc3f49dcca70048f. No N=8/N=9 production training and
no hours-long MATLAB CPMC calculation was repeated. Existing raw artifacts were
rechecked, focused calculations were rerun, and positive and negative software
paths were exercised.

### 11.2 Updated executive verdict

**The overall strict verdict remains NOT ACCEPTED as a complete QMC-track and
Challenge #15 reproduction.**

The work is materially stronger than at the first review. The finite-size
projected-NQS benchmark is now better validated, the small-system oracle is
genuinely independent, NQS-derived parent-channel chirality exists, provenance
is substantially better, and the main CLI gates fail closed. The CPMC Figure 4
analysis now includes all nine interaction points, blocking diagnostics, and a
finite-difference scheme uncertainty.

The remaining blockers are nevertheless central requirements rather than
cosmetic defects:

- the neural map is not input SO(3)-equivariant;
- the NQS optimization still enumerates the full fixed-M Fock sector and is not
  a scalable VMC/MCMC implementation;
- chirality is still a parent-channel proxy rather than the full Coulomb metric
  derivative;
- the thermodynamic extrapolation remains model-sensitive and uncontrolled;
- only one CPMC seed, time step, and walker setting has been run;
- the CPMC implementation and its strict gate are still untracked;
- the public PR still contains only the registration README.

| Area | Previous verdict | Revalidated verdict |
|---|---|---|
| Challenge #15 finite-size core | PARTIAL | **PASS for the explicitly limited finite-size projected-NQS benchmark** |
| Challenge #15 strong method targets | FAIL / PARTIAL | **Still FAIL / PARTIAL** |
| Small-N independent oracle | Missing | **PASS for N=3,4** |
| NQS-sourced chirality | Missing | **PARTIAL; state-source issue fixed, observable remains a proxy** |
| CLI and result validation | FAIL | **PASS for tested committed paths** |
| CPMC Figure 4 scientific reproduction | Conditional pass | **Conditional pass, substantially strengthened** |
| Clean-checkout/public delivery | FAIL | **Still FAIL** |
| Overall complete reproduction | FAIL | **Still FAIL** |

### 11.3 Commands and observed results

The documented solution-local environment was used after the repository-root
.venv failed to start because it referenced a missing CPython 3.14.2
installation. The solution-local environment was healthy:

| Check | Observed result | Verdict |
|---|---|---|
| Python runtime | Python 3.12.12 | PASS |
| Scientific packages | NumPy 2.5.1, SciPy 1.18.0, SymPy 1.14.0 | PASS |
| Test framework | pytest 9.1.1 | PASS |
| pip check | No broken requirements found | PASS |
| Lock snapshot versus pip freeze | 10 locked, 10 installed, zero differences | PASS |
| Tracked tests only | 62 passed in 6.39 s | PASS |
| Entire current worktree | 67 passed in 7.19 s | PASS |
| Base verifier | score 8/8, exit 0 | PASS |
| Research verifier | score 6/6, exit 0 | PASS |
| Review verifier | score 8/8, exit 0 | PASS |
| Untracked combined QMC gate | 67 passed; CPMC_FINALIZER_GATE=PASS; QMC_REVIEW_GATE=PASS | PASS locally |
| Python AST parsing | 32 project Python files parsed | PASS |
| PowerShell parsing | 7 files parsed, zero errors | PASS |
| Git whitespace checks | working and staged diffs clean | PASS |

The difference between 62 and 67 tests is important: five CPMC finalizer tests
are present only in the untracked test_cpmc_finalizer.py file. Therefore, 67
passing tests describes the current local worktree, while the committed
Challenge #15 checkout contains 62 tracked tests.

### 11.4 Negative-path verification

The previous high-severity false-success defect is fixed for the exercised
NQS path.

A forced N=4 run with max_iterations=0 produced:

- optimizer_success=false;
- status=failed;
- variance_l0=0.0110076262;
- variance_l2=0.0002337787;
- residual_l0=0.104917;
- residual_l2=0.0152898;
- command exit code 3.

Passing that failed artifact to the validator produced exit code 6 and the
message that the result status was not complete. Committed tests also reject
NaN/Inf, missing metrics, excessive variance/residual, ED residual failures,
and incomplete status.

Relevant code:

- tracks/qmc/solutions/Plasma-Team/src/chiral_graviton/cli.py:50
- tracks/qmc/solutions/Plasma-Team/src/chiral_graviton/cli.py:68
- tracks/qmc/solutions/Plasma-Team/src/chiral_graviton/cli.py:137
- tracks/qmc/solutions/Plasma-Team/src/chiral_graviton/cli.py:587
- tracks/qmc/solutions/Plasma-Team/tests/test_cli.py:85
- tracks/qmc/solutions/Plasma-Team/tests/test_cli.py:118

**Revalidated status: PASS for the tested CLI quality gates.**

### 11.5 Challenge #15 scientific revalidation

#### 11.5.1 Finite-size core remains valid

The following findings remain valid and pass:

- fermionic antisymmetry through the ordered determinant basis;
- finite-size E(L=0), E(L=2), and Δ;
- projected output-state L²=6;
- the constructively generated five-member L=2 tower;
- small-system algebra and shared-kernel ED consistency.

These statements apply to the finite-size, enumerated, symmetry-projected
benchmark. They do not establish the strong method targets below.

#### 11.5.2 Independent oracle is a real improvement

The new independent_oracle.py does not import the production basis,
interaction, pair-table, or Hamiltonian builder. It independently integrates
the chord-distance Coulomb pseudopotentials and assembles a determinant-space
Hamiltonian for N=3,4.

Observed gap comparisons:

| N | Independent oracle | Production ED | Absolute difference |
|---|---:|---:|---:|
| 3 | 0.118990554618355 | 0.118991576458858 | 1.02184e-6 |
| 4 | 0.131854938914381 | 0.131856754927023 | 1.81601e-6 |

An additional N=4 quadrature check increased the integration grid from
x_order=64, phi_points=256 to x_order=96, phi_points=384:

- default oracle gap: 0.131854938914381;
- higher-order oracle gap: 0.131856212960563;
- higher-order minus production ED: -5.41966e-7;
- pair-projector completeness error: 4.03e-14.

This supports the claim that the agreement is not merely a shared-kernel
identity or an accidental default-grid result.

**Revalidated status: PASS for the requested independent small-N check.
N=5..8 comparisons remain shared-kernel checks.**

#### 11.5.3 Input SO(3) equivariance remains unimplemented

The neural model is still an occupation-bit MLP followed by exact projection
onto ker(L+). The revised irrep_error documentation correctly states that it
certifies the projected output state, not an input-equivariant neural map.
There is still no test that rotates electron coordinates or network inputs and
then reevaluates the network.

The solution README and REPORT now state this limitation honestly. However,
the repository-root README line 10 still calls the method an
SO(3)-equivariant NQS using NetKet/JAX/PyTorch, although the implementation does
not use those frameworks and does not implement input equivariance. The
truthfulness gate scans the solution documents but not this root README.

**Revalidated status: FAIL for input-equivariant NQS; PASS for projected output
irrep certification; documentation is only partially corrected.**

#### 11.5.4 Scalable VMC remains unimplemented

The code still enumerates complete fixed-M bases, constructs the Hamiltonian,
evaluates full vectors with H psi, and performs deterministic optimization.
Posterior sampling draws independently from the already enumerated probability
vector. This is a valid estimator diagnostic, but not a sampling-trained
VMC/MCMC algorithm and not a non-enumerated NQS.

The revised solution documentation now describes this accurately as an N=8--9
bridge rather than a thermodynamic-scale implementation.

**Revalidated status: FAIL for the strong scalable-VMC requirement; claim
hygiene fixed.**

#### 11.5.5 NQS-state chirality is new but still incomplete

The new train_nqs_chirality path trains projected NQS ground and L=2 states and
passes those states to the chirality response. The reviewed N=7 artifact
records:

- state_source=trained_projected_nqs;
- optimizer_success=true;
- bright/dark integrated ratio=616.061;
- lowest-L=2-pole bright/dark ratio=1442.873;
- bright lowest-pole fraction=0.774345;
- projected-irrep error=1.38e-14.

This closes the prior ED-only state-source defect. The operator remains the
m_rel=1↔3 Laughlin parent-channel proxy, not the full finite-sphere Coulomb
metric derivative or complete s2± spectral response.

**Revalidated status: PARTIAL.**

#### 11.5.6 Thermodynamic scaling and N=9 uncertainty remain partial

No new controlled scaling evidence was added. The extrapolations remain:

- all-size linear: 0.12887;
- even linear: 0.12692;
- odd linear: 0.13609;
- quadratic: 0.14223;
- model envelope: approximately 0.01336.

The N=9 artifact is also unchanged: one seed, one width, one optimizer run, no
N=9 independent reference, and no ansatz/restart uncertainty. The solution
documentation now clearly says that the approximately 6.64e-9 sampling error
is not a total physical uncertainty.

**Revalidated status: PARTIAL; reporting fixed, scientific control not added.**

### 11.6 CPMC-Lab Figure 4 revalidation

#### 11.6.1 Confirmed improvements

The current local CPMC finalizer and artifacts now provide:

- all nine U/t=0..8 points in Figure 4(a), Figure 4(b), and Figure 4(c);
- nine digitized ED reference points with a provenance file;
- five-point and three-point derivative estimates;
- their absolute difference as a finite-difference systematic contribution;
- IID, lag-1, integrated-autocorrelation, effective-sample-size, batch, and
  split-half diagnostics;
- selected block-aware standard errors;
- SHA-256 manifests for raw and derived scientific artifacts;
- a check-only finalizer gate;
- nonzero failure for partial markers, NaN blocks, and scientific mismatch;
- MATLAB exception rethrow after FAILED.json is written.

The combined local gate passed and independently verified the listed artifact
hashes. All three panels match the digitized ED curves within the stated
combined uncertainties.

#### 11.6.2 Remaining statistical and numerical limitations

Warnings remain visible in mc_diagnostics.csv:

- U=3 lag-1 correlation is approximately 0.2647;
- U=6 split-half z is approximately 2.0416;
- U=2,3,6,8 have blocking-SE versus IID-SE warnings.

These warnings do not cross the current hard gate thresholds. The revised
selected errors are more conservative than the first report.

At U=8 the potential-energy finite-difference systematic is approximately
0.0538924 and the total reported uncertainty is approximately 0.110401. This
is a useful scheme-sensitivity allowance, but it is not a controlled h→0
derivative extrapolation.

Only one production seed, one Δτ, and one walker population have been run.
The 30 discarded equilibration blocks are not retained, so a direct warm-up
plateau audit is still impossible.

**Revalidated status: conditional scientific PASS, with unresolved stochastic
and algorithmic systematics.**

#### 11.6.3 Remaining CPMC gate and provenance defects

- monitor_and_finalize.ps1 writes FINALIZED.txt only after downstream commands
  succeed, but it does not remove a stale FINALIZED.txt before an early point
  failure or timeout.
- For U=1..8 the point wrapper initially treats accepted as true; only smoke
  and U=0 have point-local scientific acceptance. The later global finalizer
  performs the actual ED comparison, so the point-marker meaning is misleading.
- The ED reference is digitized, not independently recalculated. The
  provenance lacks calibration coordinates, extraction commands, operator
  identity, and an empirical derivation of digitization uncertainty.
- The source version conflict is disclosed and a 15-file source-tree manifest
  exists, but the provenance records no archive hash or acquisition URL.
- report.json, report.html, FINALIZED.txt, and the paper image are not included
  in artifact_manifest.json.

**Revalidated status: PARTIAL for end-to-end provenance and completion
semantics.**

### 11.7 Reproducibility and delivery revalidation

The new requirements-lock.txt exactly matches the ten packages installed in
the reviewed solution-local environment, and bootstrap.ps1 provides a concrete
environment creation path. New schema-2 runs record dependency versions,
platform, timestamps, Git commit and dirty state, resolved run configuration,
and tolerances.

Portfolio-wide provenance remains partial because the principal N=9 result is
an older schema-1 artifact without the expanded metadata or a checkpoint.

More importantly, the clean-delivery failure remains:

- the entire cpmc_lab_fig4 directory is untracked;
- scripts/verify_review_gate.ps1 is untracked;
- tests/test_cpmc_finalizer.py is untracked;
- result directories are ignored and are not available from the PR;
- the committed documents claim 67 tests, but a clean committed checkout has
  62 tracked tests because the five CPMC tests are untracked;
- the local branch is seven commits ahead of plasma/main but is not the public
  PR branch.

Live PR #208 was checked again on 2026-07-30. It remains open at head
56fe57fa1eb456af31eef293c6795b344b72cc1b with one commit and one changed file,
tracks/qmc/solutions/Plasma-Team/README.md. None of the implementation,
remediation, tests, CPMC workflow, or reviewed artifacts are present in that
PR.

**Revalidated status: FAIL for public delivery and clean-checkout
reproducibility.**

### 11.8 Final acceptance matrix after remediation

| Requirement | Revalidated status |
|---|---|
| Fermionic antisymmetry | PASS |
| Finite-size E0, E2, and gap | PASS |
| Projected L²=6 | PASS |
| Constructed fivefold L=2 tower | PASS |
| Independent small-N oracle | PASS for N=3,4 |
| Fail-closed NQS CLI and validator | PASS for tested paths |
| New-run provenance and dependency snapshot | PASS |
| Portfolio-wide artifact provenance | PARTIAL |
| Neural input SO(3) equivariance | FAIL |
| Non-enumerated scalable NQS/VMC | FAIL |
| NQS-state chirality | PARTIAL |
| Full Coulomb metric-derivative chirality | FAIL |
| Controlled thermodynamic extrapolation | FAIL / PARTIAL evidence only |
| N=9 physical precision | PARTIAL |
| CPMC Figure 4(a-c) local scientific result | CONDITIONAL PASS |
| CPMC seed/time-step/walker sensitivity | FAIL |
| CPMC clean-checkout delivery | FAIL |
| Public PR delivery | FAIL |

### 11.9 Revalidated conclusion

The remediation should be credited as real engineering and audit progress. It
fixes the most serious false-success behavior, adds a genuinely independent
small-system oracle, adds an NQS-state chirality path, improves provenance, and
makes the local CPMC analysis much more defensible.

It does not, however, complete the scientific method requested by the strong
interpretation of Challenge #15, and it does not deliver the current work
through the public PR. The most accurate present label remains:

> A finite-size, full-Fock-enumerated, SO(3)-projected neural variational
> benchmark with an independent N=3,4 oracle and NQS parent-channel chirality,
> accompanied by a conditionally reproduced CPMC-Lab Figure 4(a-c).

This addendum changed only review.md. No source, result, branch, commit, PR, or
external publication state was modified during revalidation.

---

## 12. Claude Independent Review Addendum — 2026-07-30

### 12.1 Context and methodology

This addendum represents an independent review by Claude (DeepSeek-v4-pro
model, xhigh reasoning effort) of the latest Challenge #15 ("挑战-fqhe") results,
drawing on three Codex (GPT-5.6-sol) conversation streams and direct inspection
of all available scientific artifacts.

The three Codex conversation streams reviewed:

| Stream | Session ID | Scope |
|---|---|---|
| 复现-qmc基本论文 | 019fa73e | CPMC-Lab Figure 4 reproduction setup: 16-site 1D Hubbard, N_up=5, N_down=7, Nwlk=5000, dtau=0.01, U=0..8 |
| 挑战-fqhe | 019fa7b7 | Challenge #15 NQS implementation: Fock-state enumeration, SO(3) projection, L=2 graviton mode, N=3..9 |
| review | 019fb193 | Comprehensive audit of all artifacts, generating the original review.md and orchestrating P0/P1 remediation |

Codex operated as an orchestrator in all three streams, spawning sub-agents for
implementation, testing, and verification. The review.md file (Sections 1–11
above) is Codex's own audit output, produced during the "review" session. This
Section 12 is Claude's independent re-examination of the same evidence.

### 12.2 Cross-reading the three conversation streams

#### 12.2.1 复现-qmc基本论文 (CPMC Figure 4 reproduction)

This session established the CPMC-Lab Figure 4 reproduction pipeline. Codex
configured the MATLAB CPMC_Lab_20160129 package, set up the 16-site 1D Hubbard
model with 5 spin-up and 7 spin-down electrons, and ran 5000 walkers with a
0.01 time step across nine interaction strengths (U/t = 0 through 8). The
session produced the raw MAT files, block energy CSVs, and summary files stored
under `20260728-165638-cpmc-lab-fig4a-three-point/`.

Key outcomes:
- U=0 check: total energy matches analytic value to ~8×10⁻¹³
- All nine U points completed with 150 blocks each after 30-block equilibration discard
- Initial version plotted only U=0,2,4,6,8 in Figure 4(a); later remediation expanded all panels to all nine points
- Original implementation had acceptance-always-true markers for U=1..8 and would finalize despite partial status

#### 12.2.2 挑战-fqhe (Challenge #15 NQS)

This session implemented the core Challenge #15 solution: a symmetry-projected
neural quantum state for the chiral graviton on the Haldane sphere. The
approach uses:

1. Ordered LLL Fock determinant basis → fermionic antisymmetry
2. Shared MLP over occupation-bit vectors → neural variational ansatz
3. Exact projection onto ker(L_+) → output-state SO(3) irrep certification
4. Deterministic full-basis energy evaluation → optimization (not MCMC-trained)
5. Ladder-operator descent from highest-weight state → fivefold L=2 multiplet

Codex iterated through N=5,6,7,8,9 systems, debugging sparse projection
linear algebra, optimizing the CG eigensolver refinement loop, and adding a
chirality response path. The session produced results under
`20260729-chiral-graviton-strong/`.

Key design decisions visible in the conversation:
- Chose full Fock enumeration over MCMC sampling for small-N correctness
- Chose explicit projection over input-equivariant architecture
- Used ED as the primary small-N reference (shared pseudopotential kernel)
- Added parent-channel chirality as a first step toward full chiral response

#### 12.2.3 review (Comprehensive audit)

This session performed the systematic audit recorded in Sections 1–10 of this
file. Codex read all solution source code, ran the 35-test suite (all passed),
inspected result JSON artifacts, checked the CPMC pipeline, examined git state
and PR #208, and applied the nine acceptance criteria from Section 2.

Notable from the conversation: Codex identified the shared-kernel ED problem
(§4.6), the optimizer-false-success defect (§6.2), the CPMC premature-FINALIZED
defect (§5.2.6), and the method-description mismatch (§7) — all from static
code reading and test execution, without running hours-long production
calculations. This demonstrates the value of structured adversarial audit.

The subsequent remediation (two commits: a974109 + 84ae498) was also
orchestrated through Codex, fixing the P0/P1 defects. Section 11 is Codex's
own revalidation of those fixes.

### 12.3 Claude's independent assessment of the latest 挑战-fqhe results

#### 12.3.1 What is genuinely strong

**Independent small-system oracle.** The new `independent_oracle.py` computes
the chord-distance Coulomb pseudopotentials from first-quantized two-body
integrals without importing the production basis, interaction, pair-table, or
Hamiltonian builder. For N=3,4 the gap agreements are 1.02×10⁻⁶ and 1.82×10⁻⁶
respectively. A higher-order quadrature check (x_order=96, phi_points=384)
brought the N=4 oracle-production discrepancy to 5.42×10⁻⁷. The pair-projector
completeness error is 4.03×10⁻¹⁴. This is a genuinely independent cross-check
that would catch shared-kernel normalization, sign, or unit errors.

**N=7 multiplet quality.** The five M = -2,-1,0,1,2 states show an energy spread
of 1.78×10⁻¹⁵ and L² expectations of 6.00000000000000 (deviation ~10⁻¹⁴). The
rotation equivariance error is 8.16×10⁻¹³. These are essentially at machine
precision for the projection scheme. The NQS gap of 0.129198 matches the ED
gap of 0.129198 to 5×10⁻¹³. This is as clean a finite-size result as one can
ask for at N=7.

**Fail-closed gates verified.** The forced max_iterations=0 audit test produced
optimizer_success=false, status=failed, variance_l0=0.011, residual_l0=0.105,
and exit code 3. The validator rejected the failed artifact with exit code 6.
Committed tests cover NaN/Inf, missing metrics, excessive variance/residual,
ED residual failures, and incomplete status. This is a real engineering
improvement over the original false-success behavior.

**NQS-state chirality.** The new train_nqs_chirality path correctly passes
trained NQS ground and L=2 states to the chirality response, closing the prior
defect where chirality was computed from ED eigenstates. The N=7 result shows
a bright/dark integrated ratio of 616, a lowest-L2-pole ratio of 1443, and a
bright lowest-pole fraction of 0.774. The operator remains the m_rel=1↔3
Laughlin parent-channel proxy rather than the full Coulomb metric derivative.

**CPMC diagnostic thoroughness.** The current CPMC finalizer now reports IID,
lag-1, integrated autocorrelation, effective sample size, batch (2/5/10/15),
and split-half diagnostics for all nine U points, plus SHA-256 artifact
manifests and digitized-ED provenance. The selected uncertainties are more
conservative than the initial report.

#### 12.3.2 What remains incomplete

**Not a scalable VMC.** The code enumerates complete fixed-M Fock sectors (the
N=9 L=2 sector has 343 basis states in the kernel), constructs the Hamiltonian
explicitly, and performs deterministic optimization via `H @ psi`. Posterior
sampling draws independently from the already-enumerated probability vector.
This is valid for N≤9 where the Hilbert space is manageable, but it does not
demonstrate a path to N=12, 14, or beyond where enumeration becomes
impractical. The solution documentation now honestly describes this as a
"bridge" rather than a scalable implementation.

**Not an input-equivariant network.** The neural map is an occupation-bit MLP
with no built-in rotational equivariance. Equivariance is achieved by exact
projection of the output state onto ker(L_+), which certifies the state belongs
to the correct irrep but does not make the network itself equivariant to
rotated inputs. The readme at the repository root (line 10) still describes
this as an "SO(3)-equivariant NQS using NetKet/JAX/PyTorch" — the
implementation uses none of those frameworks and does not implement input
equivariance.

**Chirality is a proxy, not the full response.** The chirality observable uses
a rank-2 tensor connecting m_rel=1 and m_rel=3 Laughlin parent channels. The
full chiral graviton spectral response requires the Coulomb metric derivative
operator s2± acting on the full guiding-center density structure factor. The
current proxy gives qualitatively correct asymmetry, but quantitative
comparison with the literature (e.g., the ~1.4 bright/dark ratio reported in
the original graviton papers) requires the complete operator.

**Thermodynamic limit is model-sensitive.** The four extrapolation models give
Δ∞ estimates spanning 0.12692 to 0.14223 — a range of 0.01531, which exceeds
the individual regression errors (~0.003–0.016) and the model envelope
(0.01336). The N=9 point (gap=0.13051) is NQS-only, and it is above the
linear-all extrapolation (0.12887), pulling the quadratic fit upward. Without
N=10,11,12 NQS results or independent large-N references, one cannot
distinguish between a genuine gap increase at large N, an even-odd oscillation,
or an NQS ansatz bias.

**CPMC has unresolved statistical concerns.** The mc_diagnostics.csv shows:
U=3 lag-1 correlation = 0.265 (threshold >0.2), U=6 split-half z = 2.04
(threshold >2), and U=2,3,6,8 blocking-SE/IID-SE > 1.2. Only one seed, one
Δτ, and one walker population have been run. The 30 discarded equilibration
blocks are not retained, preventing warm-up plateau verification. At U=8 the
finite-difference systematic of 0.054 dominates the statistical error of
0.002, and this is estimated from a single h=1 step rather than an h→0
extrapolation.

**The public PR #208 still contains only the registration README.** None of the
solution implementation, the 62 tracked tests, the CPMC workflow, the
independent oracle, the chirality path, the verification scripts, or the
reviewed artifacts are present in the public PR. The local branch
(challenge/qmc-chiral-graviton-clean) is seven commits ahead of plasma/main but
is not the PR branch. The cpmc_lab_fig4 directory, verify_review_gate.ps1, and
test_cpmc_finalizer.py remain untracked.

### 12.4 Claude's updated acceptance matrix

Claude independently assessed each requirement against the evidence available
as of 2026-07-30. Where Claude's assessment differs from Codex's revalidation
(Section 11.8), the difference is noted.

| Requirement | Codex reval | Claude independent | Notes |
|---|---|---|---|
| Fermionic antisymmetry | PASS | PASS | Agree: ordered Fock determinant basis guarantees this |
| Finite-size E0, E2, gap | PASS | PASS | Agree: direct computation with small-N cross-checks |
| Projected L²=6 | PASS | PASS | Agree: exact projection onto ker(L_+) |
| Fivefold L=2 tower | PASS | PASS | Agree: ladder-operator construction verified |
| Independent small-N oracle | PASS (N=3,4) | PASS (N=3,4) | Agree: genuinely independent, quadrature-converged |
| Fail-closed NQS CLI/validator | PASS | PASS | Agree: tested paths confirmed with forced-failure audit |
| New-run provenance / deps | PASS | PASS | Agree: requirements-lock.txt, schema-2 metadata |
| Portfolio-wide provenance | PARTIAL | PARTIAL | Agree: N=9 artifact is older schema-1 without full metadata |
| Neural input SO(3) equivariance | FAIL | FAIL | Agree: not implemented; output projection only |
| Non-enumerated scalable NQS/VMC | FAIL | FAIL | Agree: full Fock enumeration; documentation now honest |
| NQS-state chirality | PARTIAL | PARTIAL | Agree: state source fixed; operator remains parent-channel proxy |
| Full Coulomb metric-derivative chirality | FAIL | FAIL | Agree: not implemented |
| Controlled thermodynamic extrapolation | FAIL/PARTIAL | FAIL | Claude leans stronger: no evidence of controlled N→∞; model spread > individual errors |
| N=9 physical precision | PARTIAL | PARTIAL | Agree: ~6.6e-9 is sampling error only, not total uncertainty |
| CPMC Fig 4(a-c) local result | CONDITIONAL PASS | CONDITIONAL PASS | Agree: main trends credible but statistical concerns remain |
| CPMC seed/Δτ/walker sensitivity | FAIL | FAIL | Agree: single seed/Δτ/walker; equilibration blocks discarded |
| CPMC clean-checkout delivery | FAIL | FAIL | Agree: cpmc_lab_fig4 untracked |
| Public PR delivery | FAIL | FAIL | Agree: PR #208 is registration README only |

### 12.5 Points of emphasis versus Codex's assessment

Claude's independent review agrees with Codex's revalidated conclusions in
nearly all items. The following deserve additional emphasis:

**The independent oracle is the strongest single improvement.** A
first-quantized, quadrature-converged, genuinely independent cross-check for
N=3,4 is exactly the kind of adversarial verification the acceptance criteria
demand. It would be valuable to extend this to N=5 (Hilbert space dimension
grows but remains ED-tractable) to bridge the gap between "independent
small-N" and "larger-N shared-kernel."

**The gap between local quality and public delivery is the most serious
remaining defect.** The local worktree now contains a substantially validated
finite-size benchmark with independent oracle coverage, fail-closed gates,
provenance tracking, and conditionally reproduced CPMC results. None of this
is accessible from the public PR. A reviewer who clones the repository and
checks out the PR branch sees only a registration README. Until the
implementation, tests, CPMC workflow, and verification scripts enter the PR,
the work cannot be independently reproduced or evaluated.

**The root README method description is factually incorrect.** Line 10 of the
repository root README describes the method as an "SO(3)-equivariant NQS using
NetKet/JAX/PyTorch." The implementation uses none of those frameworks and does
not implement input equivariance. While the solution-local README and REPORT
have been corrected, the root README has not. This matters because the root
README is what a newcomer or reviewer sees first.

**The N=9 result should be treated as a single-configuration bridge, not a
scalability demonstration.** With one seed, one hidden width (24), one
optimizer run, and no independent large-N reference, the N=9 gap of
0.130509(7×10⁻⁹) should be reported as a finite-size extension point rather
than evidence of controlled scaling. The ~6.6×10⁻⁹ sampling error captures
only posterior sampling noise from the fixed enumerated distribution, not
network expressivity error, optimization uncertainty, or finite-size systematics.

### 12.6 Claude's overall verdict

Claude concurs with Codex's revalidated conclusion: **the overall strict
verdict remains NOT ACCEPTED as a complete QMC-track and Challenge #15
reproduction.**

The work represents a credible finite-size, full-Fock-enumerated, SO(3)-projected
neural variational benchmark with genuine improvements over the initial
submission — most notably the independent small-system oracle, the fail-closed
quality gates, and the NQS-state chirality path. The CPMC Figure 4 reproduction
is conditionally credible with substantially improved diagnostics.

However, the strong-method targets of Challenge #15 (scalable VMC, input
equivariance, full chiral response, controlled thermodynamic limit) remain
unmet, and the public delivery gap means the work cannot be independently
verified from the PR. The most accurate label remains:

> A finite-size, full-Fock-enumerated, SO(3)-projected neural variational
> benchmark with an independent N=3,4 oracle and NQS parent-channel chirality,
> accompanied by a conditionally reproduced CPMC-Lab Figure 4(a-c).

### 12.7 Recommended next actions (prioritized)

**Immediate (P0 — blocks public verification):**
1. Merge or rebase the seven local commits into the PR branch and push
2. Track the cpmc_lab_fig4 directory, verify_review_gate.ps1, and
   test_cpmc_finalizer.py
3. Correct the root README method description to match the actual implementation

**Short-term (P1 — completes the finite-size benchmark):**
1. Extend the independent oracle to N=5
2. Run at least one additional CPMC seed for U=3,6 (the points with statistical warnings)
3. Retain equilibration blocks for future warm-up plateau audits
4. Add the N=9 result checkpoint to tracked artifacts with full schema-2 metadata

**Long-term (P2 — Challenge #15 strong targets):**
1. Implement autoregressive/MCMC NQS training on non-enumerated Hilbert spaces
2. Implement the full Coulomb metric-derivative chiral response
3. Add controlled thermodynamic extrapolation with two or more NQS points beyond ED range
4. Implement genuine input-equivariant neural architecture or clearly document the
   output-projection alternative

This addendum (Section 12) was written by Claude after independent reading of
the three Codex conversation streams and direct inspection of all available
scientific artifacts. No source, result, branch, commit, PR, or external
publication state was modified.
