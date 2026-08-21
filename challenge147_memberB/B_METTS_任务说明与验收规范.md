---
title: "B 角色：二维 METTS 最小正确实现任务说明与验收规范"
version: "1.0"
language: "zh-CN"
intended_use:
  - "大语言模型任务调用"
  - "Agent 系统提示词"
  - "研发任务拆解"
  - "阶段验收"
---

# B 角色：二维 METTS 最小正确实现任务说明与验收规范

## 1. 角色定义

你是项目中的 **B 角色**，负责完成二维 METTS（Minimally Entangled Typical Thermal States）的**最小正确实现**。

你的首要目标不是优化大系统性能，而是先建立一条：

- 逻辑正确；
- 可复现；
- 可诊断；
- 可与精确对角化（ED）对照；
- 可记录样本级运行轨迹；
- 可扩展到后续 \(10\times10\) smoke test

的二维 METTS 基础流程。

---

## 2. 总体目标

完成二维 METTS 的端到端最小闭环，包括：

1. 构造产品态初态；
2. 对初态执行 METTS 虚时间演化；
3. 在演化后的态上测量能量；
4. 计算局域测量概率；
5. 按测量结果随机坍缩到新的产品态；
6. 用坍缩后的产品态生成下一条 METTS 样本；
7. 保存完整的样本级 trace；
8. 在 \(2\times2\)、\(h/J=3.0\) 的小系统上与 ED 对照；
9. 小系统测试通过后，再进行 \(10\times10\) 的 smoke test。

---

## 3. 当前阶段的优先级

### 3.1 必须优先完成

- 产品态初始化；
- METTS 虚时间演化；
- 能量测量；
- 局域概率计算；
- 随机坍缩；
- 下一产品态生成；
- 样本级 trace；
- \(2\times2\) 小系统与 ED 对照；
- 异常检测、日志保存和状态码输出。

### 3.2 当前阶段暂不追求

- \(10\times10\) 的高性能；
- 复杂基混合；
- 过早的性能优化；
- 大规模并行；
- 高级采样策略；
- 未经过小系统验证的算法扩展。

---

## 4. 固定模型与运行约定

在开始实现前，B 必须与 A 明确并统一以下约定：

- Hamiltonian；
- 边界条件；
- 能量单位；
- 参数定义；
- 格点编号顺序；
- 张量网络站点排序；
- 观测量定义；
- \(\beta\) 的定义；
- 虚时间演化长度；
- 数据格式；
- 输出字段；
- 随机种子约定。

首轮对照测试固定使用：

\[
2\times2,\qquad h/J=3.0.
\]

至少选择两个不同的 \(\beta\) 点，与 ED 进行对照。

---

## 5. 核心物理流程

### 5.1 产品态初始化

生成一个局域直积态：

\[
|\sigma\rangle
=
|\sigma_1\rangle\otimes|\sigma_2\rangle\otimes\cdots\otimes|\sigma_N\rangle.
\]

要求：

- 初始态必须可复现；
- 初始态必须关联随机种子；
- 当前阶段优先使用 \(Z\) 基产品态；
- 不要一开始引入复杂基混合；
- 必须记录每个站点的局域状态；
- 必须记录产品态编码或可重建表示。

### 5.2 METTS 虚时间演化

对产品态执行：

\[
|\phi_\sigma\rangle
=
\frac{e^{-\beta H/2}|\sigma\rangle}
{\sqrt{\langle\sigma|e^{-\beta H}|\sigma\rangle}}.
\]

需要特别确认：虚时间演化总长度是

\[
\tau=\beta/2,
\]

即执行算符：

\[
e^{-\beta H/2}.
\]

### 5.3 演化方法

优先使用以下任一方案：

1. 二阶 Suzuki–Trotter；
2. 仓库中已有、并经过验证的虚时间演化接口。

若使用二阶 Suzuki–Trotter，应明确：

- 时间步长 \(\Delta\tau\)；
- 总步数；
- 奇偶层或门层分解；
- 每步后的归一化策略；
- 截断阈值；
- 最大 bond dimension；
- 截断误差记录方式。

不要重复实现仓库中已有且可信的张量网络与演化基础设施。

### 5.4 能量测量

对归一化后的 METTS 样本计算：

\[
E_\sigma
=
\langle\phi_\sigma|H|\phi_\sigma\rangle.
\]

每条样本必须记录：

- 样本能量；
- 演化前后范数；
- 演化步数；
- Trotter 步长；
- 累积截断误差；
- 运行时间；
- 内存估计；
- 状态码。

### 5.5 局域测量概率

在当前阶段，仅使用 \(Z\) 基坍缩。

对于每个格点 \(i\)，计算局域结果 \(s_i\) 的条件概率：

\[
p_i(s_i)
=
\frac{
\langle\phi_\sigma|
P_i(s_i)
|\phi_\sigma\rangle
}{
\langle\phi_\sigma|\phi_\sigma\rangle
}.
\]

要求：

- 概率必须为有限数；
- 每个局域概率必须满足非负性；
- 概率和必须在容差内归一；
- 超出容差时不得静默继续；
- 必须保存异常概率、站点位置和中间状态。

### 5.6 随机坍缩

根据局域概率依次采样，生成新的产品态：

\[
|\sigma'\rangle.
\]

要求：

- 使用明确的随机数生成器；
- 每条样本保存 seed；
- 相同配置和 seed 应可重放；
- 保存每个站点的概率与最终采样结果；
- 坍缩失败时输出错误状态，不得伪造样本；
- 坍缩后的态必须重新验证为合法产品态。

### 5.7 生成下一条样本

将坍缩结果作为下一轮输入：

\[
|\sigma\rangle
\leftarrow
|\sigma'\rangle.
\]

重复以下链条：

```text
产品态
  -> 虚时间演化到 β/2
  -> 归一化
  -> 测量能量
  -> 计算局域概率
  -> 随机坍缩
  -> 新产品态
```

---

## 6. 推荐执行顺序

### 阶段 1：接口与约定确认

- 与 A 确认 Hamiltonian；
- 确认边界条件；
- 确认单位；
- 确认 ED 输出格式；
- 确认 tanTRG、QMC、METTS 的统一数据格式；
- 确认 \(\beta\) 点；
- 确认 \(2\times2\)、\(h/J=3.0\) 的测试配置。

### 阶段 2：最小单样本闭环

实现并跑通：

1. 产品态构造；
2. 虚时间演化；
3. 归一化；
4. 能量测量；
5. \(Z\) 基概率计算；
6. 随机坍缩；
7. 新产品态生成；
8. trace 保存。

### 阶段 3：小系统正确性验证

在 \(2\times2\)、\(h/J=3.0\) 下：

- 至少测试两个 \(\beta\) 点；
- 与 ED 对照；
- 检查能量；
- 检查范数；
- 检查概率归一；
- 检查相同 seed 的可重放性；
- 检查异常处理；
- 分析 METTS 与 ED 的差异来源。

### 阶段 4：多样本统计

- 连续生成多个 METTS 样本；
- 记录逐样本能量；
- 计算样本均值；
- 计算统计误差；
- 观察热化过程；
- 必要时区分 warm-up 样本与 production 样本；
- 保留完整样本链。

### 阶段 5：\(10\times10\) smoke test

仅在小系统测试通过后执行。

目标不是获得高精度结果，而是确认：

- 程序能够启动；
- 至少完成一个样本；
- 没有立即出现 NaN；
- 内存没有失控；
- wall time 可记录；
- trace 可完整输出；
- 已知失败模式可识别。

---

## 7. 样本级 Trace 规范

每条 METTS 样本至少记录以下字段。

| 字段 | 含义 |
|---|---|
| `sample_id` | 样本编号 |
| `step` | METTS 链步数 |
| `seed` | 随机种子 |
| `beta` | 逆温度 |
| `imag_time_target` | 目标虚时间，必须为 \(\beta/2\) |
| `trotter_order` | Trotter 阶数 |
| `trotter_dt` | Trotter 步长 |
| `trotter_steps` | 演化步数 |
| `initial_product_state` | 初始产品态编码 |
| `collapse_basis` | 坍缩基，当前应为 `Z` |
| `collapse_probabilities` | 局域测量概率 |
| `collapsed_product_state` | 坍缩后产品态 |
| `energy` | 当前样本能量 |
| `norm_before` | 演化或归一化前范数 |
| `norm_after` | 归一化后范数 |
| `truncation_error_step` | 每步截断误差 |
| `truncation_error_total` | 累积截断误差 |
| `max_bond_dimension` | 最大 bond dimension |
| `wall_time_sec` | wall time |
| `memory_estimate_mb` | 内存估计 |
| `status_code` | 状态码 |
| `warnings` | 警告列表 |
| `error_message` | 错误信息 |
| `checkpoint_path` | 中间状态保存位置 |
| `timestamp` | 时间戳 |
| `config_hash` | 配置哈希或版本标识 |
| `code_version` | 代码版本或 commit |

### 7.1 推荐状态码

| 状态码 | 含义 |
|---|---|
| `OK` | 样本成功完成 |
| `INVALID_CONFIG` | 配置不合法 |
| `INIT_STATE_ERROR` | 产品态初始化失败 |
| `EVOLUTION_NAN` | 虚时间演化出现 NaN/Inf |
| `NORM_ERROR` | 范数异常 |
| `ENERGY_ERROR` | 能量计算异常 |
| `PROBABILITY_ERROR` | 局域概率非法或不归一 |
| `COLLAPSE_ERROR` | 随机坍缩失败 |
| `TRUNCATION_EXCEEDED` | 截断误差超阈值 |
| `MEMORY_LIMIT` | 内存超限 |
| `TIMEOUT` | 运行超时 |
| `CHECKPOINT_ERROR` | 中间状态保存失败 |
| `UNKNOWN_ERROR` | 未分类异常 |

---

## 8. 异常处理要求

不得静默忽略以下情况：

- NaN；
- Inf；
- 范数接近零；
- 范数漂移超阈值；
- 局域概率为负；
- 局域概率大于 1；
- 概率和不为 1；
- 截断误差异常；
- 坍缩结果非法；
- 张量维度不匹配；
- Hamiltonian 与 ED 配置不一致；
- 内存异常增长；
- wall time 超限；
- 中间状态保存失败。

发生异常时必须：

1. 立即标记失败状态；
2. 保存日志；
3. 保存当前配置；
4. 保存随机种子；
5. 保存最近可用的中间状态；
6. 保存发生异常的 step 和站点；
7. 保存概率、范数、能量和截断误差；
8. 不得把失败样本计入正常统计；
9. 不得返回看似正常但实际无效的数值。

---

## 9. 与 ED 的小系统对照

测试配置：

\[
2\times2,\qquad h/J=3.0.
\]

至少在两个 \(\beta\) 点进行对照。

### 9.1 对照内容

- METTS 能量样本均值；
- METTS 统计误差；
- ED 热平均能量；
- 二者绝对差；
- 二者相对差；
- 样本数；
- warm-up 长度；
- Trotter 步长；
- 截断误差；
- 最大 bond dimension；
- 随机种子；
- Hamiltonian、边界和单位。

### 9.2 结果解释

METTS 与 ED 的差异必须能够解释为以下一种或多种来源：

- 有限样本统计误差；
- 热化不足；
- 样本自相关；
- Trotter 误差；
- 张量网络截断误差；
- bond dimension 限制；
- 边界条件不一致；
- Hamiltonian 定义不一致；
- 单位或归一化不一致；
- 测量实现错误。

不得只报告“结果不一致”，必须给出诊断依据。

### 9.3 推荐对照表

| \(\beta\) | ED 能量 | METTS 均值 | METTS 误差 | 绝对差 | 相对差 | 样本数 | \(\Delta\tau\) | 累积截断误差 | 状态 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 待填写 | 待填写 | 待填写 | 待填写 | 待填写 | 待填写 | 待填写 | 待填写 | 待填写 | 待填写 |

---

## 10. B 交付给 A 的内容

B 阶段结束时，应向 A 交付：

1. 小系统 METTS 样本 trace；
2. 与 ED 的比较表；
3. 完整运行配置；
4. 已知失败模式；
5. 异常日志示例；
6. 中间状态或 checkpoint 说明；
7. \(10\times10\) 单样本耗时估计；
8. \(10\times10\) 单样本内存估计；
9. 当前代码版本；
10. 复现实验的命令或调用方式。

---

## 11. 阶段一共同验收标准

阶段一结束时，项目应满足以下共同验收条件：

- QMC 至少提供可信的 \(u(\beta)\) 基准与误差条；
- tanTRG、QMC 和 METTS 的数据格式已统一；
- \(2\times2\) ED 可运行；
- METTS 在小系统端到端完成；
- METTS 与 ED 的差异可解释为统计误差或已记录的张量网络近似；
- \(10\times10\) METTS 至少完成一个 smoke test；
- A 与 B 已确认同一个 Hamiltonian、边界条件和单位。

---

## 12. B 角色完成定义（Definition of Done）

只有同时满足以下条件，B 的阶段任务才算完成：

- [ ] 产品态初始化可运行；
- [ ] 虚时间演化明确执行到 \(\beta/2\)；
- [ ] 使用二阶 Suzuki–Trotter 或仓库中已验证的演化接口；
- [ ] 能量测量可运行；
- [ ] \(Z\) 基局域概率可计算；
- [ ] 随机坍缩可运行；
- [ ] 下一产品态可生成；
- [ ] 每条样本都有完整 trace；
- [ ] 异常不会被静默忽略；
- [ ] 失败时保存日志和中间状态；
- [ ] \(2\times2\)、\(h/J=3.0\) 至少两个 \(\beta\) 点完成 ED 对照；
- [ ] 对照差异有统计或数值误差解释；
- [ ] 小系统测试通过；
- [ ] \(10\times10\) 至少完成一个 smoke test；
- [ ] 向 A 交付 trace、比较表、配置、失败模式、耗时和内存估计；
- [ ] A 与 B 对 Hamiltonian、边界和单位达成一致。

---

## 13. 面向大语言模型的任务调用模板

下面的文本可直接作为 Agent 或大语言模型的任务提示词。

```text
你是项目中的 B 角色，负责二维 METTS 的最小正确实现。

目标：
先完成产品态初始化、虚时间演化到 β/2、能量测量、Z 基局域概率计算、随机坍缩、下一产品态生成和样本级 trace。暂时不要追求 10×10 的性能。

固定验证配置：
- 系统尺寸：2×2
- 参数：h/J = 3.0
- 至少两个 β 点
- 与 exact diagonalization 对照

实现要求：
1. 优先复用仓库已有的张量网络和虚时间演化接口。
2. 使用二阶 Suzuki–Trotter，或使用仓库中已经验证的虚时间演化方法。
3. 虚时间总长度必须为 β/2，即应用 exp(-βH/2)。
4. 当前阶段仅使用 Z 基坍缩，不引入复杂基混合。
5. 每条样本必须记录 step、seed、β、Trotter 步长、能量、范数、截断误差、基选择、wall time、内存和状态码。
6. 不得静默忽略 NaN、Inf、概率异常、范数异常或坍缩失败。
7. 发生异常时保存日志、配置、seed 和中间状态。
8. 小系统测试通过后，才执行 10×10 smoke test。
9. 最终向 A 交付小系统 trace、ED 比较表、运行配置、已知失败模式、10×10 单样本耗时和内存估计。
10. 开始前与 A 确认 Hamiltonian、边界条件和单位完全一致。

输出时请按以下顺序：
- 当前实现状态
- 使用的接口与配置
- 已完成模块
- 未完成模块
- 小系统测试结果
- ED 对照结果
- 异常与失败模式
- trace 文件位置
- 下一步行动
```

---

## 14. 推荐输出目录结构

```text
metts_runs/
├── configs/
│   └── 2x2_h3_beta_<value>.yaml
├── traces/
│   ├── sample_000001.json
│   ├── sample_000002.json
│   └── chain_summary.csv
├── checkpoints/
│   ├── sample_000001_step_<n>.ckpt
│   └── failed_sample_<id>.ckpt
├── logs/
│   ├── run.log
│   └── errors.log
├── comparisons/
│   └── metts_vs_ed.csv
└── reports/
    └── phase1_B_report.md
```

---

## 15. 推荐单样本 Trace 示例

```json
{
  "sample_id": 1,
  "step": 1,
  "seed": 20260729,
  "beta": 1.0,
  "imag_time_target": 0.5,
  "trotter_order": 2,
  "trotter_dt": 0.05,
  "trotter_steps": 10,
  "initial_product_state": ["up", "down", "up", "down"],
  "collapse_basis": "Z",
  "collapse_probabilities": [
    {"site": 0, "p_up": 0.61, "p_down": 0.39},
    {"site": 1, "p_up": 0.44, "p_down": 0.56}
  ],
  "collapsed_product_state": ["up", "down", "down", "up"],
  "energy": -1.234,
  "norm_before": 0.873,
  "norm_after": 1.0,
  "truncation_error_step": [1.0e-10, 1.3e-10],
  "truncation_error_total": 2.3e-10,
  "max_bond_dimension": 32,
  "wall_time_sec": 0.84,
  "memory_estimate_mb": 118.0,
  "status_code": "OK",
  "warnings": [],
  "error_message": null,
  "checkpoint_path": "checkpoints/sample_000001.ckpt",
  "config_hash": "待填写",
  "code_version": "待填写"
}
```
