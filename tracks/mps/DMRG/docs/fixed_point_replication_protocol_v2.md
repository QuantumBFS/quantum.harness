# 三次独立固定点复现协议 v2

## Material Passport

- Origin Skill: experiment-agent
- Origin Mode: plan
- Origin Date: 2026-07-16
- Verification Status: PREREGISTERED_UNVERIFIED
- Version Label: fixed_point_replication_v2

状态：`PREREGISTERED_BEFORE_NEW_RUNS`

本协议只适用于创建后产生的新数据。v1 的重复 1 仍按 v1 判为失败，不追溯改判。

## 修改原因

v1 把“13 个矩是否显著偏离精确零”作为通过门。检查点诊断发现，同一个最终运行平均偏置在两个独立 16-run 验证批次中分别得到 `max|z|=3.68022` 和 `1.64543`，但对应的线性响应耦合修正仅为 `5.46e-4` 和 `4.67e-4`。这说明显著性检验回答的不是“偏置在复现精度内是否等价于最优偏置”。

v2 改为耦合空间等价门：

\[
\delta J=C^{-1}\langle S\rangle,
\]

其中 `C` 是同次优化最后 600 步的平均协方差，`<S>` 来自与优化链独立的冻结验证链。该量只用于验收，不写回偏置，不产生修正后的结果。

## 冻结参数

### 每次 RG

- `L=45`
- 13 个 Supplement 已确认偶算符
- 3000 variational steps
- 每步 20 sweeps
- 16 walkers
- `mu=5e-5`
- 输出只使用第 3000 步 `running_bias`
- 禁止使用 `instantaneous_bias`

### 冻结偏置验证

- 5000 thermalization sweeps/run
- 120000 measurement sweeps/run
- 16 independent runs
- 保存全部 `16 x 13` run-level 算符均值
- 协方差取同次优化轨迹最后 600 步平均
- 2000 次 run-level bootstrap
- bootstrap 随机种子必须在运行前冻结
- 计算每个 bootstrap 样本的 `max(abs(delta J* - delta J_hat))`
- 取该同时偏差的 95% 上分位数，使用保守的 `higher` 分位数规则
- 上置信限定义为 `max(abs(delta J_hat)) + deviation_quantile_95`

正式通过条件：

1. `condition_number(C) <= 1e6`；
2. `95% upper bound of max(abs(delta J)) <= 0.001`。

`0.001` 与完整固定点耦合向量的绝对残差门同量级，也是项目已有 Newton 偏置安全半径；不是根据某个新重复结果选择。原 Bonferroni z 检验继续输出，但只作诊断，不决定通过或失败。

### Jacobian 与固定点

- 两轮基础 RG 后，在该重复自己的第二轮冻结系综测量 Jacobian
- 5000 thermalization sweeps/run
- `10^6` measurements/run，spacing 1 sweep
- 16 independent runs
- 2000 run-level bootstrap，必须全部有效
- 解 `A=T^T B`，禁止显式求逆
- 解 `(I-T) delta=R(K)-K`
- `condition_number(I-T) <= 1e6`
- `max(abs(Newton correction)) <= 0.05`
- 新独立链验证候选固定点
- `Linf(R(K*)-K*) <= 0.001`
- `relative_L2(R(K*)-K*) <= 0.005`
- 候选固定点的冻结偏置必须通过上述耦合空间等价门

## 新的独立重复与种子

| 重复 | 基础 RG | 基础冻结验证 | Jacobian | 固定点 RG | 固定点冻结验证 | 等价门 bootstrap |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 202607901 | 202608001 | 202608101 | 202608201 | 202608301 | 202608401 |
| 2 | 202607911 | 202608011 | 202608111 | 202608211 | 202608311 | 202608411 |
| 3 | 202607921 | 202608021 | 202608121 | 202608221 | 202608321 | 202608421 |

两轮基础 RG 和相应验证的第二轮种子自动在表中起始值上加 1。不同重复不得共享轨迹、Jacobian 样本或验证链。

## 三重复一致性门

三个重复均通过单次门后，还必须满足：

1. 固定点候选两两 `Linf <= 0.002`；
2. 固定点候选两两相对 `L2 <= 0.01`；
3. 三个偶主本征值的 95% bootstrap 区间有公共交集；
4. 三个奇主本征值的 95% bootstrap 区间有公共交集。

## 禁止事项

- 禁止用冻结验证结果修正同一偏置后再把它计为独立通过；
- 禁止挑选检查点、随机种子或最接近论文的重复；
- 禁止把 v1 的失败重复追溯并入 v2；
- 禁止只检查最近邻分量；
- 禁止覆盖旧输出。

输出目录：`output/reproduction/fixed_point_repeats_v2/`。

## 协议修订记录

- `v2.0`：将验收目标从精确零显著性改为耦合空间等价，并初始设置 10000 measurement sweeps/run。
- `v2.1`：在任何正式 v2 重复开始前，用不计入最终结果的代码功效检查发现：点估计 `delta J Linf=0.00063453`，但 10000 sweeps 的 95% bootstrap 上限为 `0.00110113`，无法在 `0.001` 门内给出足够精度。按蒙特卡洛误差的 `1/sqrt(N)` 标度，20000 sweeps 的预期上限约为 `0.000964`，因此只把正式验证长度提高到 20000；耦合门槛、模型、优化参数和正式种子均不变。该功效检查使用种子 `202608501/202608601`，不计入三次确认性重复。
- `v2.2`：第二次功效检查显示 20000 sweeps 的点估计为 `0.00066102`。同时发现 v2.0 的原始 bootstrap 范数分位数不是严格的误差上界，因此在正式重复前纠正为“点估计加 centered simultaneous deviation band”。按正式的 2000 次 bootstrap 实现，该上界为 `0.00131495`，由 `1/sqrt(N)` 标度得到最低需求约 74430 sweeps；独立的 Bonferroni 正态近似给出约 116248 sweeps。正式长度冻结为 120000 sweeps，不再做第三次功效试跑。该功效检查使用种子 `202608502/202608602`，不计入三次确认性重复。
