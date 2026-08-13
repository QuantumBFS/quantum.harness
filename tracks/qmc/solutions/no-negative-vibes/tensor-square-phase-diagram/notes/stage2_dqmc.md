# Stage 2 — DQMC / ED 交叉验证

日期：2026-07-29

## 结论

连续高斯 Hubbard–Stratonovich、tensor-square determinant、Wick 观测量和
checkpoint/resume 路径通过了小尺寸交叉验证。`m=3, β=2` 的三个 Trotter
步长中，能量、密度和 combined-`Q²` 相对有限温 ED 的全部偏差均小于
`1.5σ`。`m=4` 在 `β=8` 时得到

```text
DQMC E            = -17.8794 ± 0.1222
ED ground E       = -17.8512218061
DQMC combined-Q²  =   1.23482 ± 0.01239
ED combined-Q²    =   1.23771958
```

所有审计点的 determinant sign 均为正（浮点归一化后严格记为 `+1`）。

## 低温稳定化

最初的 `β=8` 路径在长时间片乘积条件数达到 `2.6e16–1.5e17` 时失败。
真实 checkpoint 上，朴素 direct 与 structured log-weight 分别为
`1430.3245` 和 `1318.6281`，且出现伪负号；同一历史经 SVD 缩放后两条
独立路径均给出 `383.50364857988774`，Green 函数有限。

因此粗扫的 `β≥4` 点使用缩放奇异值表示，并分别在完整 tensor 空间和
外积空间重建 determinant 作审计。该修复另有稳定长乘积、Wick 对显式
Fock、非相互作用热力学和 bitwise checkpoint/resume 回归测试。

## 性能边界

500 次 BLAS 单线程基准显示，当前 NumPy/Python 结构化路径在
`m=3,4,6` 的 direct/structured wall-time 比仅为 `0.70,0.75,0.83`，
到 `m=8` 才达到 `1.02`。它仍把矩阵存储降低约 `3.0–4.5×`。因此本轮
不把小尺寸加速当作正面结果；粗扫保留结构化路径主要为了内存与独立
恒正审计。

## 产物

- `results/stage2_dqmc_validation/aggregate/summary.json`
- `results/stage2_dqmc_validation/aggregate/table.csv`
- `results/stage2_dqmc_validation/aggregate/figures/dqmc_ed_validation.png`
- `results/stage2_weight_benchmark/aggregate/summary.json`
- `results/stage2_weight_benchmark/aggregate/table.csv`
