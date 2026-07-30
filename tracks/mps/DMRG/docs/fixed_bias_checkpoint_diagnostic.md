# 固定偏置检查点诊断协议

## Material Passport

- Origin Skill: experiment-agent
- Origin Mode: plan
- Origin Date: 2026-07-16
- Verification Status: PREREGISTERED_UNVERIFIED
- Version Label: fixed_bias_checkpoint_diagnostic_v1

## 目的

重复 1 的固定点耦合残差通过，但第 13 个冻结目标矩失败。本诊断只区分以下两种原因：

1. `running_bias` 的平均窗口滞后；
2. 3000 步内 `instantaneous_bias` 本身也没有形成稳定区域。

诊断结果不能用于把重复 1 改判为通过，也不能选择最优快照替代正式结果。

## 冻结设计

从已经完成的 `verification_rg/trajectory.npz` 提取第 1800、2400、3000 步：

- `instantaneous_bias`；
- `running_bias`。

共 6 个快照。每个快照使用：

- 5000 thermalization sweeps；
- 10000 measurement sweeps/run；
- 16 independent runs；
- 13 项双侧 Bonferroni 全族检验，`alpha=0.05`；
- 临界 `|z|=2.8905115607`。

| 快照 | 种子 |
|---|---:|
| instantaneous 1800 | 202607801 |
| running 1800 | 202607802 |
| instantaneous 2400 | 202607803 |
| running 2400 | 202607804 |
| instantaneous 3000 | 202607805 |
| running 3000 | 202607806 |

## 解释规则

- running 多数失败、instantaneous 出现稳定通过区：运行平均窗口滞后；
- 两类在相邻检查点均失败或符号剧烈变化：优化轨迹本身未稳定；
- 单个快照通过但相邻检查点失败：不能认定稳定，只视为随机波动；
- 6 个快照全部报告，不做“最佳快照”选择。

由于这是探索性根因诊断，跨 6 个快照不再追加第二层显著性校正；任何快照的 `PASS` 都不能升级为确认性证据。
