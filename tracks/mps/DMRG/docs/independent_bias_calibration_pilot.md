# 独立偏置校准试验

## Material Passport

- Origin Skill: experiment-agent
- Origin Mode: plan
- Origin Date: 2026-07-16
- Verification Status: PREREGISTERED_UNVERIFIED
- Version Label: independent_bias_calibration_pilot_v1

状态：`PREREGISTERED_BEFORE_CORRECTION`

## 目的

v2 重复 1 的 RG2 在正式等价门失败，最大残余为 `even_08_square`，`delta J=0.0010877426`。检查最后 300 至 2400 步的瞬时偏置平均后，没有任何窗口向该修正方向移动，因此排除“运行平均窗口过长”作为主要原因。

本试验只回答：一次独立线性响应校准能否把完整 13 维偏置带入 `1e-3` 等价区间。它不改判 v2 重复 1，也不计入最终三次重复。

## 冻结步骤

1. 输入固定为 `fixed_point_repeats_v2/repeat1/base/rg2`；
2. 校准矩固定为该 RG2 已完成的独立 120000-sweep 验证；
3. Hessian 固定为该 RG2 优化轨迹最后 600 步平均协方差；
4. 只做一次 `J_new=J+Cov^-1<S>`；
5. 条件数上限 `1e6`，单次修正信赖半径 `0.002`；
6. 禁止第二次修正；
7. 使用新种子 `202608701` 做 5000 thermalization + 120000 measurement sweeps/run + 16 runs；
8. 使用 `202608702` 做 2000 次 run-level simultaneous-deviation bootstrap；
9. 通过门保持不变：95% 上置信限 `max(abs(delta J)) <= 0.001`。

只有本试验通过，才允许为未来的新重复预注册“校准批次与确认批次严格分离”的协议。失败则停止，不追加修正。
