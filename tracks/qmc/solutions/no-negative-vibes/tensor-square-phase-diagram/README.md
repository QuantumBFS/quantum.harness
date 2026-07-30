# Tensor-Square Phase Diagram

> Submission layout note: generated JSON/CSV/PNG/PDF artifacts are preserved
> under `tracks/qmc/results/no-negative-vibes/tensor-square-phase-diagram/`,
> which is intentionally ignored by Git. This directory contains the tracked
> model, source, tests, notes, and reproduction interface.

本目录是 `No Negative Vibes` 挑战中的独立科研子项目。目标不是继续枚举有限深度的正例，而是把 tensor-square（张量平方）行列式恒正机制落实为一个可扩展的、厄米且允许非局域相互作用的费米子模型，计算其相图，并判断是否产生有论文价值的量子相与临界行为。

## 给执行智能体的硬规则

1. **不要调用或依赖 Superpowers / using-superpowers，也不要生成 Superpowers 风格的计划或规格。** 本目录已经给出获批的模型和执行路线，直接工作。
2. 使用短循环：提出最小实例 → 做最便宜的正确性检查 → 记录并提交 → 扩大扫描 → 根据结果调整。
3. 优先寻找成功的相、临界线和可解释机制。失败参数点达到预设早停条件后立即停止，不在普通失败案例上花时间证明 no-go。
4. 复用已经冻结的精确行列式 oracle。只有 oracle 与独立直接计算不一致时才修基础设施。
5. 每个阶段都要形成小而可审查的 Git 提交，让队友能看到已完成内容，避免重复劳动。
6. 只向团队共享 fork 的个人工作分支推送。**不得更新、合并或改写主办方 PR #178，除非项目负责人另行明确批准。**
7. `COMPUTE_RUNBOOK.md` 含私有网络和机器信息，只能留在本地，禁止提交或上传。`AGENT_HANDOFF.md` 同样永不上传。

## 文件导航

- `MODEL.md`：候选哈密顿量、恒正证明、物理解释和相图变量。
- `RESEARCH_PLAN.md`：从 ED 到结构化 DQMC、有限尺寸标度和论文输出的阶段门。
- `COMPUTE_RUNBOOK.md`：两台计算资源的本地运行方法；**私有，禁止上传**。
- `AGENT_PROMPT.md`：可直接交给执行智能体的任务说明。
- `STATUS.md`：唯一的进度入口；每轮实验后更新。

## Git 边界

可以提交：

- 科学模型、推导、代码、测试、小型基准数据、图、聚合结果和 `STATUS.md`。
- 足以复现实验的参数清单、随机种子规则、依赖锁定和结果哈希。

不得提交：

- `COMPUTE_RUNBOOK.md`、`AGENT_HANDOFF.md`、SSH 密钥、密码、机器地址清单。
- 大型原始轨迹、逐样本矩阵、临时缓存、虚拟环境和构建产物。

建议工作分支：

```text
work/<owner>/tensor-square-phase-diagram
```

提交信息使用阶段前缀，例如：

```text
ts-phase: validate determinant identity
ts-phase: add m=3,4 ED pilot
ts-phase: add structured DQMC weight
ts-phase: summarize pilot phase scan
```

## 完成定义

最低成功标准不是“跑出一张热图”，而是同时满足：

1. 每个 Monte Carlo 权重由直接行列式和 tensor-square 分解双重验证为非负。
2. 小尺寸 QMC 与 ED 在能量、密度和至少一个关联函数上误差内一致。
3. 至少发现一个不由自由费米子、单一平均场通道或完全对称 Casimir 极限解释的稳定区域。
4. 使用多个尺寸和温度给出相边界或明确的交叉区证据，并报告误差、自相关和有限尺寸漂移。
5. 形成可重复运行脚本、参数表、图和论文式机制叙述。

