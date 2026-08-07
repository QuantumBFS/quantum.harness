# ALF TI/II 多链统计与 Green 稳定性协议

适用对象为同一物理参数、投影长度和试探波函数配置下的两种投影边界：

- `TI`：左边界 UHF、右边界 free；
- `II`：左右边界均为 free。

两者都使用 128 个单线程任务；一个任务对应一条独立 Markov 链。

## Bin 汇总

每条链包含 1 个热化 bin 和至少 20 个测量 bin。正式首批每个 bin
包含 150 sweeps；热化 bin 不进入统计。对 batch `a`、测量 bin `b`，先跨 128
条链分别汇总比值观测量的分子和分母：

```text
N_ab = Σ_c N_acb
D_ab = Σ_c D_acb
E_ab = N_ab / D_ab
```

禁止先计算各链比值再平均。总均值仍由全部汇总 bin 的总分子除以总
分母获得。能量误差棒是删除一个跨链汇总 bin 的 ratio jackknife
误差；只有这个误差用于 `statistical_precision_pass`：

```text
statistical_precision_pass =
    (跨链测量 bin 数 >= 20) and (能量误差棒 <= 0.005)
```

另做删除一条 chain slot 的 jackknife，输出每个留一链估计及其误差。
它只诊断链间一致性，不参与上述统计精度判定。

## Green 稳定性

ALF 在每次重新计算 Green 函数时比较传播值和重算值。每条链保存
最大的

```text
δ_G,c = max |G_propagated - G_recalculated|
```

以及该最大值的 `(bin, sweep, direction, slice, i, j, flavor)`。
`direction=1/-1/0` 分别表示正向传播、反向传播和回到零时间片。

```text
green_stability_pass = max_c δ_G,c <= 1e-8
```

报告同时给出全部链的最大值、中位数、95% 分位数和失败链位置。
Green 失败必须缩短 `Nwrap` 后重跑，不能用更多链、bin 或 sweep
修复。本次正式计算固定 `Nwrap=5`。

## 每个 TI/II 点的同构输出

```text
diagnostics/<TI|II>/theta_NNN/
├── raw_chain_bins.csv
├── cross_chain_bins.csv
├── leave_one_chain.csv
├── green_stability.csv
└── summary.json
```

`summary.json` 分别保存 `statistical_precision_pass` 和
`green_stability_pass`，不合并或替代其中任一状态。
