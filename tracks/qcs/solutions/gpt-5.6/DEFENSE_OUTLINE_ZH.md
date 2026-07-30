# Challenge 113 中文答辩提纲

建议总时长：5 分钟
主线：识别低秩几何 → 判断何时可迁移 → 验证有限 shot 闭环收益

## 0:00–0:40 问题

量子门的仿真模型可以自动微分，但真实装置通常只能返回有限 shot
估计得到的标量 fidelity。直接在全部脉冲参数上做无梯度闭环优化会消耗
大量实验查询，也容易被测量噪声干扰。

我们的问题是：

> 仿真器给出的 fidelity Hessian 是否能找出一个更小、但仍能迁移到
> 失配装置上的校准空间？

## 0:40–1:30 第一条证据：低秩几何确实存在

我们在 robustness 方向构建了理想、封闭、交换对称的
perfect-blockade 中性原子 CZ 模型：

- 基线 infidelity：`6.5996e-6`；
- Hessian 有效秩：`5`；
- `lambda_5 / lambda_1 = 7.2087e-2`；
- `lambda_6 / lambda_1 = 2.6815e-16`。

这说明在该模型中，几百个波形坐标的局部 fidelity 响应集中在五个实
方向上。

干净 baseline/full 重跑分别通过 32/32 和 33/33 检查；标准库比较器
复核了 3,951 个数值字段和 402 个分类字段，零失配。必须主动说明：
这是合成 perfect-blockade 模型证据，不是论文逐点复现，也不是硬件
保真度。

## 1:30–2:20 第二条证据：低秩空间有明确适用边界

robustness 方向固定五个名义主方向，扫描失真强度和方向：

- 所有方向在 `eta <= 0.35` 时均为 `10/10` 成功；
- `eta = 0.60` 时，三种 principal-space power 的成功数变为
  `10/10`、`6/10`、`2/10`；
- symmetry-breaking 与 new-leakage 两类新物理通道失败。

因此，决定迁移性的不是失真范数本身。更关键的是局部敏感子空间是否
发生强旋转，以及失配是否引入名义响应空间之外的新通道。

## 2:20–3:45 第三条证据：有限 shot 闭环中的收益

我们的独立 CNOT benchmark 有 40 个脉冲参数，名义 Hessian 秩为 15。
我们在打开 holdout 前冻结了方法、24 个 truth cells、四个 nested
shot-noise replicates、三个比较方法和六个判据。

正式 Attempt 49 的 288 次运行全部完成：

| 方法 | 成功率 | 分层经验 truth-cell bootstrap 区间 | queries/run | shots/run |
|---|---:|---:|---:|---:|
| model-informed `k=15` | 90.625% | [81.25%, 97.92%] | 66 | 2,099,200 |
| completed model-informed `k=40` | 25.00% | [12.50%, 37.50%] | 166 | 5,376,000 |
| raw-coordinate `k=40` | 0.00% | [0%, 0%] | 166 | 5,376,000 |

这里的 `[0%, 0%]` 是退化的经验 bootstrap 区间：所有观测到的
raw-`k=40` truth cell 及其重采样都失败。它不等价于“总体成功概率严格为
零”的置信区间。

`k=40` completed方法包含同样的 15 个主方向，只额外加入 25 个名义平坦
方向。因此它的失败不是“没有包含正确空间”，而是这些额外方向在
finite-shot central difference 中消耗查询、注入噪声并竞争 trust
radius。

`k=15` 使用 `39.76%` 的固定 query cap 和 `39.05%` 的固定 shot cap。
六个预注册判据全部通过，独立静态重建为 18/18 PASS。

在线可执行的主要成本比较是固定上限 `66 vs 166 queries`。关闭客户端后，
再从封存结果派生的 restricted-mean post-hoc、oracle-scored first-hit
queries-to-target 分别为：

- `k=15`：48.76 [45.35, 52.47]；
- completed `k=40`：160.63 [153.69, 165.84]；
- raw `k=40`：166。

失败运行按完整方法 cap 计费。这个图直接回应题目的 query-count
deliverable，但不是在线停止规则。

## 3:45–4:30 主动讲清边界

我们不主张：

- 真实硬件或铯原子验证；
- 三个模拟器是同一个物理模型；
- 90.625% 来自 96 个独立装置——独立单位是 24 个 truth cells；
- 已经实现可靠的 online queries-to-target——早停证书实验失败；
- 已证明普适的 `d^2-1` scaling law——该方向被实验否定。

正式成本数字是冻结两周期协议的 deterministic full cap。最终成功是
客户端关闭后用隐藏 exact truth 做的 post-hoc 评分。

## 4:30–5:00 结论

一句话结论：

> 仿真器 Hessian 的活跃子空间可以成为有效的 sim-to-real 校准接口：
> 在失配仍位于可迁移响应范围时，它既减少查询，也避免名义平坦方向
> 带来的有限 shot 噪声；当子空间强旋转或出现新物理通道时，这种接口
> 会失效。

三条证据分别回答：

1. 低秩几何是否存在；
2. 它何时失效；
3. 它在 query-only finite-shot 闭环中能带来多少收益。

## 高频追问

### 为什么不用全部 40 个方向，更多参数不是更灵活吗？

更多方向只在估计足够准确、优化器能有效利用时才有帮助。这里新增的
25 个方向名义曲率接近零，但每个方向仍需要两侧 finite-shot 查询。
它们给全局步长加入估计噪声，并与真正敏感方向共享 trust radius。

### 你们怎样防止挑选了有利的 holdout？

Attempt 49 在打开 truth seeds 前，单独提交并推送了方法、seeds、误差
强度、配对规则、异常处理和六个 gate。正式结果只运行一次，失败也必须
原样保留。

### 四个 replicates 是否把样本量从 24 变成 96？

没有。四个 replicates 只描述同一 truth cell 下的 shot noise。统计
bootstrap 以 truth cell 为单位，并在三个 mismatch family 内分层。

### 为什么可以把两种不同模拟器放在同一个答辩里？

它们不是合并统计证据，而是独立的机理三角验证。neutral-atom 方向说明
低秩结构与失效边界；CNOT 方向说明类似几何在另一合成 benchmark 的
有限 shot 闭环收益。数值和物理参数不跨模型比较。

### 下一步怎样走向真实装置？

把真实装置或更完整平台模拟器封装成
`query(parameters, shots) -> sampled fidelity`，然后重新预注册
benchmark、seeds、gates 和 mismatch 条件。不能在现有 holdout 上继续
调参后再称为确认实验。
