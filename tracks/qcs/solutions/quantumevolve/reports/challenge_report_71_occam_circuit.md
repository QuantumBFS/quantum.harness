# Challenge Report: #71 Occam's Circuit

## Issue
**#71** — Occam's Circuit：从多项式级 train 样本恢复隐藏布尔函数，给出最小且能泛化的电路。
官方交付：4 个 mystery 电路、测试输出预测、搜索脚本和方法说明。

## 官方要求 vs 达成情况

| 要求 | 状态 |
|------|------|
| 注册（PR #181） | ✅ 已注册，团队 `quantumevolve` |
| accepted 标签 | ✅ 有 |
| 4 个 mystery 恢复 | ⚠️ 部分完成（practice-add-n4 达到 100% accuracy / 17 gates） |
| 测试输出预测 | ⚠️ 训练一致性已建立，全 mystery 预测未完全输出 |
| score=1.0 | ❌ 最高 0.9960 |

## 进化统计

| 指标 | 值 |
|------|-----|
| DB 数 | 31 |
| 总评估次数 | 208 |
| 总候选数 | 213 |
| LLM 调用 | 451 |
| Token 消耗 | ~4.28M |
| 最高分 | **0.9960** |
| 最高分 DB | `occam_suite_qwen38_100plus_v15.db` |
| 最高分代数 | gen=3 |

## 迭代轨迹（v15 最佳 run，22 evals）

```
gen= 0  score=0.9958  ← 种子基线
gen= 1  score=0.9959  ← 微提升
gen= 2  score=0.0059  ← 回退（LLM 产出错误电路）
gen= 3  score=0.9960  ← 达到最高分（本 run 峰值）
gen= 4  score=0.9960  ← 持平
gen= 5-7  score=0.006  ← 大幅回退
gen= 8  score=0.9958  ← 恢复
gen= 9-10 score=0.006  ← 再次回退
gen=11  score=0.9960  ← 恢复到峰值
gen=12-18 score≈0.996  ← 在峰值附近震荡
gen=19-21 score≈0.006  ← 最终回退，未恢复
```

## 成功原因
1. **种子代码质量高**：种子已经达到 score=0.9958（100% accuracy, 17 gates），进化只需微调
2. **评估器设计合理**：同时考核训练集 accuracy 和门数紧度，给了 LLM 明确的优化方向
3. **多实例 suite 评估**：v12+ 切换到 4 个 mystery 联合评估，更鲁棒

## 失败原因
1. **0.996→1.0 的 gap 无法跨越**：最后 0.4% 需要减少门数（17→更少），LLM 反复尝试但产出的电路要么门数相同、要么 accuracy 下降导致 score 暴跌到 0.006
2. **score 悬崖效应**：accuracy 下降导致 score 从 0.996 直接跌到 0.006，没有中间状态——LLM 无法从失败中学习（失败候选的 metrics 差异太大，缺乏梯度信号）
3. **震荡而非收敛**：gen 5-7、9-10、19-21 的反复回退说明进化没有锁定最佳策略，MCTS 探索浪费了大量 budget 在已知不好的区域

## 反思与体会
- **离散目标的进化天然困难**：布尔电路是离散结构，不像连续优化那样有梯度——一次 gate 变更要么保持 correctness 要么完全破坏
- **score 设计应该平滑**：如果 evaluator 对"门数减少但 accuracy 不完美"给出部分分数而非归零，进化会有更好的梯度信号
- **early stopping 有价值**：v15 在 gen=3 就达到峰值，后面 18 代全是在峰值附近震荡——配置 max_stagnation_gens=6 本应在 gen=9 就停止
