# Table I 共同锚点分层重复协议 v5

## Material Passport

- Origin Skill: experiment-agent
- Origin Mode: execution
- Origin Date: 2026-07-16
- Verification Status: PREREGISTERED_UNVERIFIED
- Version Label: table1_replication_v5

状态：`PREREGISTERED_BEFORE_V5_FORMAL_RUNS`

## 目标与数据隔离

目标是复现论文 Table I 的 `L=45 biased` 偶、奇主本征值。v3 和 v4-pilot
仅作为方法开发与锚点校准数据，不并入 v5 正式数值。

v5 固定使用：

- 耦合点：`output/reproduction/fixed_point_repeats_v3/v4_calibration_anchor.json`；
- 已独立确认的冻结偏置：`output/reproduction/fixed_point_v4_pilot/anchor_rg`；
- 锚点实际残差：`Linf=0.000139695`，相对 `L2=0.000760445`；
- `L=45`，13 个 Supplement 偶算符和 5 个奇算符。

正式运行不再优化锚点或偏置。

## 每次正式重复

- 5000 thermalization sweeps/run；
- `10^6` measurements/run；
- spacing 1；
- 16 independent runs；
- 2000 run-level bootstrap，必须全部有效；
- 偶、奇 `B` 条件数有限；
- `A=T^T B` 相对残差 `<1e-10`。

## 分层随机流

使用 4 个 master entropy：202611101、202611111、202611121、202611131。
每次重复从每个 master 家族取 4 条 child stream：

- repeat 1：spawn key 0–3；
- repeat 2：spawn key 4–7；
- repeat 3：spawn key 8–11。

48 条流互不重复。清单冻结在 `config/v5_table1_repeat*_seeds.json`。该设计在结果
产生前固定，目的是防止一个偶然高或低的 master-seed 子集全部落入同一重复。

## 最终汇总规则

三次重复完成后：

1. 合并 48 个 run 的充分统计量，重新计算 pooled 偶、奇 Jacobian；
2. 对 48 个 run 做 2000 次 pooled bootstrap；
3. 用三组本征值极差为统计量，做 10000 次 16/16/16 标签置换；
4. 偶、奇 batch-label permutation `p>0.05`；
5. 论文 `L=45 biased` 数值 3.045 和 7.858 必须落入 pooled 95% CI；
6. 任一条件失败，v5 判为失败，不删 run、不换种子。

## 入口

```text
python reproduce.py table1-v5-repeat --repeat 1
python reproduce.py table1-v5-repeat --repeat 2
python reproduce.py table1-v5-repeat --repeat 3
```

## Protocol amendment: pooled-resampling seeds

Recorded on 2026-07-16 after repeat 1 raw measurements finished, but before
repeat 2, repeat 3, or any pooled resampling was run. The original protocol
already fixed the resampling methods and replicate counts but omitted their
seeds. This amendment changes no raw measurements, estimands, thresholds, or
acceptance criteria.

- pooled 48-run bootstrap seed: `202611301`
- 16/16/16 repeat-label permutation seed: `202611302`

These seeds are frozen and must not be replaced after pooled results are seen.
