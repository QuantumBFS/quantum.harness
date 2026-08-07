# 三次独立固定点复现协议 v3

## Material Passport

- Origin Skill: experiment-agent
- Origin Mode: plan
- Origin Date: 2026-07-16
- Verification Status: PREREGISTERED_UNVERIFIED
- Version Label: fixed_point_replication_v3

状态：`PREREGISTERED_BEFORE_NEW_RUNS`

v1、v2 的失败重复均保持原判，不并入 v3。v3 只适用于本文件创建后产生的新数据。

## 核心改变

每次 3000 步论文参数优化后，增加一次预注册、完整 13 维的独立 Newton 校准：

\[
J_{cal}=J_{3000}+C^{-1}\langle S\rangle_{cal}.
\]

校准批次只更新偏置，不能承担验收。随后必须使用新随机种子的确认批次验收 `J_cal`。只允许一次校准，禁止看到确认结果后再次修正。

该设计来自不计入最终结果的校准试验：校准前 RG2 上置信限为 `0.00136043`；一次校准后，独立确认的点估计为 `0.00017154`，95% 上限为 `0.00038179`。

## 每次 RG 的冻结流程

1. `L=45`，13 个 Supplement 偶算符；
2. 3000 variational steps；
3. 每步 20 sweeps，16 walkers，`mu=5e-5`；
4. 只使用第 3000 步 `running_bias`；
5. 独立校准：5000 thermalization + 120000 measurement sweeps/run + 16 runs；
6. Hessian 使用优化轨迹最后 600 步平均协方差；
7. 只做一次完整向量 Newton 校准；
8. `condition_number(C)<=1e6`，`max(abs(delta J_cal))<=0.002`；
9. 独立确认：新种子，5000 thermalization + 120000 measurement sweeps/run + 16 runs；
10. 2000 次 run-level centered simultaneous-deviation bootstrap；
11. 确认门：`95% upper bound of max(abs(delta J))<=0.001`；
12. 确认通过后的校准耦合才作为 RG 输出。

原精确零 z 检验继续记录，但只作诊断。

## Jacobian 与固定点门

- 在校准且确认通过的 RG2 系综上测量；
- 5000 thermalization sweeps/run；
- `10^6` measurements/run，spacing 1；
- 16 independent runs；
- 2000 bootstrap，必须全部有效；
- 偶、奇 `B` 条件数有限；
- 方程相对残差 `<1e-10`；
- Newton 固定点：`cond(I-T)<=1e6`，`max correction<=0.05`；
- 固定点验证 RG 同样执行“3000 步 + 一次校准 + 独立确认”；
- 完整向量残差：`Linf<=0.001` 且相对 `L2<=0.005`。

## 正式种子

| 重复 | 基础 RG | 基础校准 | 基础确认 | 基础 bootstrap | Jacobian | 固定点 RG | 固定点校准 | 固定点确认 | 固定点 bootstrap |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 202609101 | 202609201 | 202609301 | 202609401 | 202609501 | 202609601 | 202609701 | 202609801 | 202609901 |
| 2 | 202609111 | 202609211 | 202609311 | 202609411 | 202609511 | 202609611 | 202609711 | 202609811 | 202609911 |
| 3 | 202609121 | 202609221 | 202609321 | 202609421 | 202609521 | 202609621 | 202609721 | 202609821 | 202609921 |

基础 RG1/RG2 及其校准、确认、bootstrap 分别使用表中起始种子和 `+1`。固定点阶段使用表中独立种子。

## 三重复一致性门

1. 三次固定点候选两两 `Linf<=0.002`；
2. 两两相对 `L2<=0.01`；
3. 偶主本征值 95% bootstrap 区间有公共交集；
4. 奇主本征值 95% bootstrap 区间有公共交集。

## 禁止事项

- 禁止重复校准；
- 禁止用校准批次兼作确认批次；
- 禁止确认失败后更换种子；
- 禁止回收 v1/v2 失败结果；
- 禁止只修正或只检查最近邻项；
- 禁止覆盖任何旧输出。

输出目录：`output/reproduction/fixed_point_repeats_v3/`。
