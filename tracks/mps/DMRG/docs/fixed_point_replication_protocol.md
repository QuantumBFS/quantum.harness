# 三次独立 13 维固定点复现协议

## Material Passport

- Origin Skill: experiment-agent
- Origin Mode: plan
- Origin Date: 2026-07-16
- Verification Status: PREREGISTERED_UNVERIFIED
- Version Label: fixed_point_replication_v1

状态：`PREREGISTERED_BEFORE_RUN`

冻结日期：2026-07-16

## 研究问题

当前单次 13 维 Newton 固定点及 Jacobian 是否能在三个完全独立的端到端计算中重复，并使固定点选择导致的系统差异小于预声明门槛？

## 独立重复的定义

每个重复必须独立完成：

1. 从裸耦合 `K_nn=0.436` 开始运行两轮 13 项 RG；
2. 在该重复自己的第二轮冻结系综上测量正式 Jacobian；
3. 使用该重复自己的 RG 映射和 Jacobian 解 Newton 固定点；
4. 在新随机链上重新运行一次 RG 验证候选固定点；
5. 使用与优化链不同的随机种子做冻结目标矩验证。

不同重复之间不得共享 RG 轨迹、Jacob​​ian 样本或验证链。只共享论文锁定的模型、算符定义和参数。

## 冻结参数

### 两轮基础 RG

- `L=45`
- `K_nn=0.436`
- 13 个 Supplement 已确认偶算符
- 2 轮 RG
- 每轮 3000 variational steps
- 每步 20 sweeps
- 16 walkers
- `mu=5e-5`
- 每轮冻结验证：5000 thermalization sweeps、10000 measurement sweeps、16 runs

### Jacobian

- 5000 thermalization sweeps/run
- `10^6` measurements/run
- spacing 1 sweep
- 16 independent runs
- 2000 run-level bootstrap replicates
- 解 `A=T^T B`，不显式计算逆矩阵

### Newton 固定点验证

- 解 `(I-T) delta = R(K)-K`
- `condition_number(I-T) <= 10^6`
- `max(abs(delta)) <= 0.05`
- 验证 RG：3000 steps、20 sweeps/step、16 walkers、`mu=5e-5`
- 冻结验证：5000 thermalization sweeps、10000 measurement sweeps、16 runs
- 初始偏置只允许来自同一重复的 `rg2`

## 随机种子

`paper --rounds 2` 会让第二轮自动使用基础种子和验证种子的 `+1`，因此各重复的种子段必须完全分离。

| 重复 | 基础 RG 起始 | 基础验证起始 | Jacobian | 固定点 RG | 固定点验证 |
|---:|---:|---:|---:|---:|---:|
| 1 | 202607301 | 202607401 | 202607501 | 202607601 | 202607701 |
| 2 | 202607311 | 202607411 | 202607511 | 202607611 | 202607711 |
| 3 | 202607321 | 202607421 | 202607521 | 202607621 | 202607721 |

例如重复 1 的两轮基础 RG 使用 `202607301/202607302`，两轮基础验证使用 `202607401/202607402`。三个重复之间没有重叠种子。

## 单次重复的强制验收门

每个重复必须同时满足：

1. 两轮基础 RG 的冻结目标矩均通过 `alpha=0.05` 的全族检验；
2. `condition_number(I-T) <= 10^6`；
3. `max(abs(Newton correction)) <= 0.05`；
4. `Linf(R(K*)-K*) <= 0.001`；
5. `relative_L2(R(K*)-K*) <= 0.005`；
6. 固定点验证的 13 个冻结目标矩通过 `alpha=0.05` 的全族检验；
7. Jacobian 的偶、奇 `B` 条件数均有限，线性方程相对残差小于 `1e-10`；
8. 2000 个 bootstrap 样本全部有效。

任一门失败，该重复标记为失败。禁止改参数后静默重跑；失败原因必须保留。

## 三次重复的一致性门

三个重复全部通过单次门后，再检查：

1. 三个固定点候选之间最大两两 `Linf` 距离不超过 `0.002`；
2. 最大两两相对 `L2` 距离不超过 `0.01`；
3. 三个偶主本征值的 95% bootstrap 区间存在公共交集；
4. 三个奇主本征值的 95% bootstrap 区间存在公共交集。

只有四项全部通过，才能把固定点和 Table I 结果升级为“端到端独立重复通过”。

## 禁止事项

- 禁止根据结果修改上述门槛；
- 禁止用同一批样本同时构造和验证固定点；
- 禁止在看到验证结果后对偏置做事后修正并把同一验证当成独立证据；
- 禁止只比较最近邻耦合而忽略完整 13 维向量；
- 禁止选择最接近论文的单次结果作为最终结果；
- 禁止覆盖旧输出目录。

## 输出目录

```text
output/reproduction/fixed_point_repeats_v1/
  repeat1/
  repeat2/
  repeat3/
  replication_report.json
```

三次重复完成前，不运行论文正式自相关最终实验。

## 协议修订记录

- `v1.0`，2026-07-16：运行前冻结参数、种子和主要门槛。
- `v1.1`，2026-07-16：重复 1 两轮基础 RG 完成后，明确写入原流程已经执行但门槛列表漏写的“基础 RG 冻结目标矩必须通过”要求。数值阈值、参数和种子均未改变；重复 1 的两轮结果已经分别为 `PASS/PASS`。该修订保留在此，不静默覆盖历史。
