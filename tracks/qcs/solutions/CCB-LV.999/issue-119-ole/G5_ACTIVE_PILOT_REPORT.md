# 49×1296 BP-TN active OLE：G5 feasibility pilot 报告

更新日期：2026-07-30

状态：**NO-GO（58/60 cells 成功；两项超时使预注册资源拟合继续暂缓）**

## 1. 固定问题与运行设置

本次运行只把已验证的 49×648 baseline 输入替换为 tracker 的 49×1296
active 电路，其余物理和数值约定保持不变：

| 项目 | 值 |
| --- | --- |
| active sites | 49-site open heavy-hex interaction graph |
| QASM SHA-256 | `3748e2c026c118f9d6c7499093ea43e41a45251b6bf8d3adb6fb056f718f6cc0` |
| circuit | `L=6`，145 barriers，1,296 CZ gates |
| observable | `O=Z52 Z59 Z72` |
| perturbation | `b=0.25`，`δ=0.15`，24 个 `Rz(0.3)` gates |
| seed bank | `issue119-ole-v1`，seed IDs 1–20 |
| pilot χ | 64、128、192 |
| dtype | `ComplexF64` |
| SVD cutoff | `10⁻¹²` |
| BP | `maxiter=25`，`tolerance=10⁻⁸` |
| tensor normalization | enabled |
| 每个 cell | 16 OpenBLAS threads，1 Julia thread，32 GiB |

这里的 `χ` 是 BP-TN 演化中允许的最大虚拟键维数。增大 `χ` 会保留更多跨
张量切分的相关信息，但 SVD 时间和张量内存都会增加。

运行分为三批：

| Slurm Job | 任务 | wall cap |
| --- | --- | ---: |
| `415669` | 初始 60 cells | 1 h/cell |
| `415961` | χ=128 的 16 个缺失 cells | 2 h/cell |
| `415977` | χ=192 的 20 个 cells | 5 h/cell |

三批都使用 CPU `batch` partition；重跑引用原始 `run_spec.json` 和原始 cell
ID，没有改变物理问题或 seed。

## 2. 最终提取状态

远端结果增量拉取后，60 个计划 cells 中有 58 个完整 success manifests：

| χ | 计划数 | 成功数 | 缺失 seed | 缺失原因 |
| ---: | ---: | ---: | --- | --- |
| 64 | 20 | 20 | — | — |
| 128 | 20 | 19 | 20 | 2 h timeout，完成到 layer 136/145 |
| 192 | 20 | 19 | 5 | 5 h timeout，完成到 layer 137/145 |

两个缺失任务都在接近末层时被 Slurm walltime 终止。日志中没有 QASM
解析错误、NaN、OOM 或 BP 不收敛证据。因此当前缺口是 walltime 问题，而不是
已观察到的数值或内存失败。

### 成功 cells 的数值与资源

| χ | n | sample mean | sample SE | mean wall | max wall | max RSS |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 64 | 20 | 0.3557810933 | 0.0047950560 | 371.78 s | 463.06 s | 1.865 GiB |
| 128 | 19 | 0.5002608855 | 0.0052585438 | 61.45 min | 83.05 min | 4.420 GiB |
| 192 | 19 | 0.6067129125 | 0.0040011571 | 3.530 h | 4.962 h | 9.702 GiB |

所有 58 个成功 cells 都满足：

- `|sample_value|≤1` 且数值有限；
- `bp_nonconverged_layers=0`；
- 最大 BP residual 不超过预设 `10⁻⁸` tolerance；
- 实际最大虚拟键达到请求的 χ；
- peak RSS 远低于 32 GiB cell allocation。

逐张量 normalization 会丢弃独立恢复全局 norm defect 所需的尺度，因此
`norm=unavailable_by_normalization` 是预期状态；报告没有用零值代替缺失诊断。

## 3. 有限 χ 诊断

共同 seeds 上的 paired mean drift 为：

```text
χ=64→128:  n=19, mean drift=0.1437300444, SE=0.0017172728
χ=128→192: n=18, mean drift=0.1090304951, SE=0.0012502189
```

预注册稳定性阈值为 `0.2874600888`。18 个三点共同 seeds 上，
`|Δ₁₂₈→₁₉₂|` 小于阈值，而且比前一步 drift 小约 24%，所以趋势没有显示
发散；但 `n=18` 而不是规定的 20，正式 `paired_drift_stable` 仍必须判为
false。

另一方面，从 χ=128 到 χ=192 的均值变化仍约为 `0.109`，远大于 Monte Carlo
seed SE。这说明 BP-TN 结果在 χ=192 尚未达到精度收敛，不能把 χ=192 均值直接
当作 active OLE 的最终答案。

## 4. 预注册 G5 gate

| 检查 | 结果 | 证据 |
| --- | --- | --- |
| complete grid | fail | 58/60 success |
| finite and bounded | pass | 58 个成功值均合法 |
| BP stable | pass | 无 BP nonconverged layer |
| χ=128→192 paired drift | formal fail | 只有 18 个三点共同 seeds |
| memory feasible at χ=512 | unavailable | 完整三点资源拟合被暂缓 |
| wall feasible at χ=512 | unavailable | 完整三点资源拟合被暂缓 |
| array recoverable | pass | 两个缺失 cell 可按 selector 独立重跑 |

机器可读结论为：

```text
gate_go=false
failed_checks=complete_grid,paired_drift_stable,memory_feasible,wall_feasible
resource_fit_status=withheld_incomplete_grid
```

因此：

> **G5 仍为 NO-GO，按既定 plan 不能把 BP-TN 路线升级到 G6 production。**

这是一个严格的流程结论，而不是说 58 个结果没有科学价值。它们已经证明：

1. 49×1296 BP-TN 在 χ≤192 可运行且数值稳定；
2. 内存不是当前瓶颈；
3. walltime 随 χ 快速上升；
4. 有限 χ drift 在减小，但 χ=192 尚未收敛。

预注册规则要求每个 χ 的 20-seed 最大 wall/RSS。当前两个缺失任务恰好属于
最慢样本；若直接用 19 个成功样本拟合，会低估尾部 walltime，所以 analyzer
继续拒绝 χ=256/384/512 正式外推。

## 5. 完成 G5 所需的最小动作

只需重跑两个原始 selectors，不需要重做其余 58 cells：

| cell | 参数 | 建议资源 |
| --- | --- | --- |
| `cell-0059` | seed=20，χ=128，δ=0.15 | 16 CPU，32 GiB，3 h |
| `cell-0015` | seed=5，χ=192，δ=0.15 | 16 CPU，32 GiB，7 h |

两项保守申请上限合计为 160 CPU·h。完成后才能发布：

- 20-seed 的两段 paired drift；
- 基于每个 χ 最大 wall/RSS 的经验资源拟合；
- χ=256、384、512 的 1.2× safety-factor 预测；
- 是否允许 BP-TN 进入 G6 的正式决定。

本报告只给出建议，没有自动提交上述重跑任务。

## 6. 结果索引

- 运行计划：`results/issue119-ole-g5-active-pilot/run_spec.json`
- 机器可读 gate：`results/issue119-ole-g5-active-pilot/g5-assessment.json`
- 汇总表：`results/issue119-ole-g5-active-pilot/g5-summary.csv`
- 资源图：`results/issue119-ole-g5-active-pilot/g5-resource-fit.png`
- 初始日志：`results/issue119-ole-g5-active-pilot/slurm-logs/`
- 重跑日志：`results/issue119-ole-g5-active-pilot/slurm-retry-logs/`

![G5 incomplete resource gate](../../../../../results/issue119-ole-g5-active-pilot/g5-resource-fit.png)
