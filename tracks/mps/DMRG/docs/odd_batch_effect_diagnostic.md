# 奇区块 master-seed 批次效应诊断

## Material Passport

- Origin Skill: experiment-agent
- Origin Mode: execution
- Origin Date: 2026-07-16
- Verification Status: PREREGISTERED_UNVERIFIED
- Version Label: odd_batch_effect_diagnostic_v1

状态：`PREREGISTERED_AFTER_V4_PILOT_FAIL_BEFORE_THIRD_BATCH`

## 已有证据

共同锚点 v4-pilot 的偶区块通过，但奇区块失败：两批差 `0.04338908`，
标准化差 `2.919`。16 个已有 run 的等分置换检验为 `p=0.004972`。

奇磁化 cross moment 和 block-square moment 的积分自相关时间分别约 6 和 5
sweeps，A/B 组相近；因此当前证据不支持热化不足或长自相关解释。

## 冻结第三批

- 输入：与 v4-pilot A/B 完全相同的 `anchor_rg`；
- seed：202610521；
- 5000 thermalization sweeps/run；
- 250000 measurements/run；
- 8 independent runs；
- spacing 1；
- 2000 bootstrap。

## 冻结检验

合并 A/B/C 共 24 个 run。以三批最大本征值减最小本征值为统计量，随机置换
run 标签为三个等大的 8-run 组，执行 10000 次置换，seed 202610522。

- `p<=0.05`：记录为 `BATCH_EFFECT_DETECTED`；
- `p>0.05`：记录为 `NO_BATCH_EFFECT_DETECTED`。

该诊断不改变 v4-pilot 的 FAIL，不把第三批替换成新的“通过批次”，也不能作为
正式 Table I 结果。

唯一入口：

```text
python reproduce.py fixed-point-v4-batch-diagnostic
```
