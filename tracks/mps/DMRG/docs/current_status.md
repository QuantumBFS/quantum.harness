# 当前复现状态

> 本文件保留为历史阶段记录。最新状态、结果和后续路线统一见
> [`../PROJECT_STATUS_AND_ROADMAP.md`](../PROJECT_STATUS_AND_ROADMAP.md)。

日期：2026-07-17

## 结论

二维 `L=45` VMCRG 的算法、Supplement 13 个偶算符、5 个奇算符、局部
Metropolis 增量、Jacobian 指标和混合神经扩展均已实现并通过确定性测试。
但 Table I 仍只能标记为部分复现：论文直接 RG2 系综和校准 13 维固定点
分别复现了奇、偶主本征值，没有同一个冻结系综同时覆盖论文两个数值。

## 当前证据

| 阶段 | 状态 | 当前证据 |
|---|---|---|
| 文献证据 | 通过 | 正文、accepted manuscript、`SM.pdf` 和 arXiv 源文件已保存 |
| 13 偶 + 5 奇算符 | 通过 | 2026-07-17 再次逐项核对 Supplement 第 3-4 页，坐标完全一致 |
| 确定性测试 | 通过 | `python reproduce.py test`：58/58 通过 |
| 论文直接 RG2 Jacobian | 部分通过 | `lambda_e=3.01562 [3.00529,3.02572]`；`lambda_o=7.85186 [7.84261,7.86131]` |
| 校准固定点 32 链 | 部分通过 | `lambda_e=3.04494 [3.03310,3.05714]`；`lambda_o=7.87970 [7.87436,7.88521]` |
| 固定点选择误差 | 已确认 | 两种冻结系综移动偶、奇本征值；不能把固定点研究结果冒充论文直接复现 |
| RG2 映射不确定性协议 | 代码与预注册完成 | 三套独立随机流、RG2 硬门槛和分层 bootstrap 已通过测试与 dry-run；正式 repeat 尚未启动 |
| 论文临界慢化 | 未完成正式结果 | 实现和入口存在，尚无正式 paper autocorrelation 输出 |
| 混合神经正式挑战 | 已有一次通过结果 | `output/neural_hybrid_easy_formal_v2` 通过原预声明门；不是论文原结果 |
| 修改后神经 smoke | 通过连接测试 | `tmp/neural_uniform_reference_smoke` 完成训练、验证、投影、消融和自相关，正确标记 `NOT_FORMAL` |
| 原始 26 到 13 筛选 | 缺源证据 | 公开 Supplement 只给筛选后的 13 项，原始 26 项仍只能作为候选重构 |

## 关键边界

1. 论文直接流程：从 `K_nn=0.436` 出发，使用第二轮 RG 冻结系综测量 Table I。
2. `fixed-point-*` 和 `table1-v5-repeat` 是固定点敏感性研究，不是论文直接流程。
3. 均匀块自旋是变分参考分布，不是微观物理温度。
4. 非均匀参考必须同时提供归一化 `log_probability`，恢复公式为
   `H_prime=-V_min-log(p_ref)+constant`。
5. 神经结果是 `13项线性偏置 + D4/Z2局域神经残差`，不是纯神经网络，也不属于原论文。
6. 当前代码只支持二维平方晶格，不能直接外推三维。

## 当前唯一优先任务

执行 `python reproduce.py paper-table1-repeat --repeat 1`。它会先完成两轮 RG，
然后检查 RG2 的完整 13 维耦合漂移、协方差和 Bonferroni 冻结矩门槛；失败则在
`16 × 10^6` Jacobian 测量前停止。repeat 1 通过后才依次执行 repeat 2、3，最后
运行 `paper-table1-assess`。神经正式挑战和临界慢化暂缓。
