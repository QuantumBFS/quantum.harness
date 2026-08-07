# 共同锚点 Jacobian 诊断协议 v4-pilot

## Material Passport

- Origin Skill: experiment-agent
- Origin Mode: execution
- Origin Date: 2026-07-16
- Verification Status: PREREGISTERED_UNVERIFIED
- Version Label: fixed_point_replication_v4_pilot

状态：`PREREGISTERED_BEFORE_V4_PILOT_RUN`

## 动机

v3 重复 1、2 均单次通过，但跨重复门已经失败：固定点候选最大差
`0.00380659>0.002`，奇本征值区间相隔 `0.00026215`。

交叉计算表明，固定 Jacobian 只更换 RG 映射时，固定点候选最大变化
`0.00376453`；固定 RG 映射只更换 Jacobian 时，最大变化
`0.00009733`。因此首要假设是：两次 Jacobian 测量位于不同 RG2 点，
而不是 Jacobian 采样器本身不稳定。

v3 重复 3 不再运行。旧结果不修改、不并入 v4 正式结果。

## 冻结锚点

`output/reproduction/fixed_point_repeats_v3/v4_calibration_anchor.json`

该向量由 v3 重复 1、2 的两个 RG 映射和两个 Jacobian 等权平均后求 Newton
根得到，只用于 v4 校准。它不是独立验证结果，也不能作为 v3 通过证据。

## 锚点验证

1. `L=45`，13 个 Supplement 偶算符；
2. 3000 variational steps，每步 20 sweeps，16 walkers，`mu=5e-5`；
3. 一次独立校准：5000 thermalization + 120000 measurements/run × 16；
4. 一次新种子独立确认，数据量相同；
5. 校准修正 `Linf<=0.002`；
6. 确认的 95% 耦合修正上界 `<=0.001`；
7. 实际固定点残差 `Linf<=0.001` 且相对 `L2<=0.005`；
8. 任一门失败，试验立即停止，不更新锚点。

## 两批共同点 Jacobian 诊断

两批都使用同一个 `anchor_rg` 目录，因此耦合向量和冻结偏置完全相同：

- 5000 thermalization sweeps/run；
- 250000 measurements/run；
- 8 independent runs；
- spacing 1；
- 2000 bootstrap，必须全部有效；
- 两批使用不同随机种子。

偶、奇区块分别满足：

1. 两批 95% bootstrap 区间有交集；
2. `abs(lambda_a-lambda_b)/sqrt(se_a^2+se_b^2)<=1.96`。

该结果只判断“共同测量点能否消除 v3 的重复间漂移”，不能作为正式 Table I
误差条。通过后才能另行预注册 v4 正式三重复；失败则必须检查采样器或误差估计。

## 冻结种子

- anchor RG: 202610101
- anchor calibration: 202610201
- anchor confirmation: 202610301
- anchor bootstrap: 202610401
- Jacobian batch A: 202610501
- Jacobian batch B: 202610511

## 唯一入口

```text
python reproduce.py fixed-point-v4-pilot
```

禁止覆盖任何已有输出，禁止失败后更换种子重跑。
