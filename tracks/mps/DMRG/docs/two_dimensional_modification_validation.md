# 二维 VMCRG 与神经扩展修改验证

## Material Passport

- Origin Skill: academic-research-suite / experiment-agent
- Origin Mode: run + validate
- Origin Date: 2026-07-17
- Verification Status: VERIFIED_FOR_DETERMINISTIC_AND_SMOKE_SCOPE
- Version Label: 2d_uniform_reference_hardening_v1

## 修改目标

在不改变论文均匀目标的前提下，防止把参考分布误解释为物理温度，并验证
二维论文实现和神经扩展仍能运行。

## 修改

1. 新增 `ReferenceDistribution2D`，要求同时提供样本和 `log_probability`。
2. 新增论文默认的 `UniformIsingReference2D`。
3. 对参考样本形状、`-1/+1` 支持集和有限对数概率做强校验。
4. 神经模型加载显式关闭 pickle，并拒绝缺失字段和非有限参数。
5. 神经实验配置记录参考分布角色、恢复公式和物理温度来源。
6. 神经输入地图必须使用 Supplement 的 13 个偶算符名称。

## 验证结果

| 检查 | 结果 |
|---|---|
| `python reproduce.py test` | 55/55 PASS |
| 编译采样器与参考采样器轨迹一致 | PASS |
| 神经解析梯度与有限差分一致 | PASS |
| 均匀参考支持集和精确 `log p` | PASS |
| 非法参考样本拒绝 | PASS |
| 非有限神经参数拒绝 | PASS |
| 修改后神经 smoke 全流程 | COMPLETED，按设计标记 `NOT_FORMAL` |
| 修改后论文端到端 smoke | COMPLETED，按设计标记 `SMOKE_PIPELINE_COMPLETED_NOT_A_SCIENTIFIC_RESULT` |

## 未宣称

- smoke 结果不具有物理统计意义；
- 当前修改没有解决 Table I 的固定点选择系统误差；
- 当前代码不是三维实现；
- 当前神经表示不是论文原方法或纯神经替代。
