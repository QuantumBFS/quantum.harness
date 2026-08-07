# Issue #119：Operator Loschmidt Echo G2 Baseline 复现报告

- 整理日期：2026-07-28
- 对应 issue：https://github.com/QuantumBFS/quantum.harness/issues/119
- 任务阶段：G2 baseline reproduction
- 计算平台：`zyli@172.16.42.215`，Slurm `batch` 分区
- 使用方法：belief-propagation tensor network（BP-TN）

## 1. 结论

49-qubit、648-CZ 的 operator Loschmidt echo（OLE）baseline 已在
χ=192 和 χ=512 上分别完成 20 个固定随机初态 seed 的复现。两组统计结果
均满足预先定义的 G2 接受条件：

`|mean − public reference| ≤ max(0.002, 3 SE)`。

| χ | seed 数 | mean | SE | 95% CI | 公开参考值 | 绝对偏差 | 容差 | 通过 |
|---:|---:|---:|---:|---:|---:|---:|:---:|
| 192 | 20 | 0.8185618335 | 0.0019847196 | [0.8144077675, 0.8227158994] | 0.8202512915 | 0.0016894580 | 0.0059541589 | 是 |
| 512 | 20 | 0.8183229132 | 0.0019858354 | [0.8141665120, 0.8224793144] | 0.8216584890 | 0.0033355758 | 0.0059575061 | 是 |

因此，**G2 baseline 已复现成功，可以进入后续精度提升阶段**。

## 2. 计算对象与协议

本次计算使用 49 个 active qubits、73 层线路和 648 个 CZ gates，测量
observable `Z52 Z59 Z72`。OLE 参数为：

- `L=3`；
- `b=0.25`；
- 扰动强度 `δ=0.15`；
- 固定 seed namespace：`issue119-ole-v1`；
- seed：1–20；
- QASM SHA-256：
  `1705197e7b1ebb02266600b3ddaba0d2c47a96de84c5895e2bb530728b815455`。

数值实现使用 TensorNetworkQuantumSimulator.jl 0.4.4，commit
`b5d4089849de1cc23806aa8325e8db56a55f2e0b`。主要设置为
ComplexF64、SVD cutoff `1e-12`、BP tolerance `1e-8`，每个 Slurm
array cell 使用 1 个 Julia thread 和 16 个 BLAS threads。

## 3. χ=192 与 χ=512 的配对比较

两个 χ 使用完全相同的 20 个随机计算基初态。逐 seed 的
`OLE(χ=512) − OLE(χ=192)` 全部为负，配对统计为：

- paired mean：−0.0002389203；
- paired SE：0.0000065177；
- 95% paired CI：[−0.0002525621, −0.0002252785]；
- 最大绝对 paired difference：0.0002807823。

χ 从 192 提高到 512 后存在稳定但很小的负向修正；其幅度约为
2.39×10⁻⁴，远小于当前 20-seed 均值约 1.99×10⁻³ 的标准误差。因此，
本轮 G2 的主要不确定度来自随机初态采样，而不是 χ 截断。

## 4. 恒等控制

`δ=0`、seed 1 的控制计算在 χ=64 上严格返回 OLE=1.0，最大实际 bond
仅为 32。这验证了未扰动线路 `U` 后接 `U†` 的实现、observable 插入和
归一化协议。

由于该控制线路是严格恒等过程，本轮没有把相同的 `δ=0` 控制重复到全部
χ 和 seed。

## 5. 计算资源实测

生产任务使用普通 `batch` 分区，没有使用 SCNet 或 bigmem。

| χ | 平均 wall time | 最大 wall time | 平均峰值 RSS | 最大峰值 RSS | 最大截断误差 | 最大 BP residual |
|---:|---:|---:|---:|---:|---:|---:|
| 192 | 120.2 s | 129.3 s | 2.27 GiB | 2.37 GiB | 2.50×10⁻⁴ | 4.40×10⁻¹¹ |
| 512 | 134.2 s | 162.0 s | 3.07 GiB | 3.34 GiB | 9.99×10⁻¹³ | 2.84×10⁻¹⁶ |

40 个生产 cells 共消耗：

- aggregate task wall time：1.41 小时；
- allocated CPU time：22.61 CPU-hours；
- BP non-converged layers：0；
- 完整结果：40/40。

实测最大内存仅 3.34 GiB。对当前图、线路深度和软件版本，单 cell
申请 16 GiB 已有超过 4.7 倍余量；若修改线路深度、gate set 或 TNQS
版本，建议先按 32 GiB 做新的资源探针。

Slurm 生产数组 job 为 `410814`；χ=192 和 χ=512 的单点资源探针分别为
jobs `410808` 与 `410810`。

## 6. 调度说明

Slurm 23.11.4 的 `sbatch --test-only` 曾错误预测任务要到 2026-08-06
才启动；实际 smoke allocation、两个资源探针和生产数组都立即获得资源。
因此该 test-only 时间没有被当作真实排队证据。

本次仅使用针对 `zyli@172.16.42.215` 的临时 profile，没有修改或激活
仓库中的 `skills/using-slurm/profiles/active.toml`。

## 7. 验证状态

- χ=192：20/20 seeds 完整，summary accepted；
- χ=512：20/20 seeds 完整，summary accepted；
- 40/40 BP 计算收敛；
- `δ=0` 恒等控制返回 1.0；
- Julia G2 测试：60/60 通过；
- Python array-entry 测试：5/5 通过；
- 仓库测试：223/223 通过，覆盖率 95%；
- 参数扫描状态：success 38、failed 0、missing 0、pending 0。

## 8. 阶段判断与下一步

G2 的目标是确认已有 BP-TN baseline 能被稳定、可重复地获得；该目标已经
完成。当前不需要为 G2 追加 χ=256/384，也不需要机械重复 `δ=0` 控制。

建议后续 G3 按以下优先级推进：

1. 先扩大随机初态数量，压低当前占主导的统计误差；
2. 如需建立 χ 外推或误差预算，再补充 χ=256/384 的 paired 数据；
3. 在同一线路、同一 seed bank 和同一接受指标下测试
   PEPO/Heisenberg-picture 2D tensor network，评估其能否提高精度或降低
   资源成本；
4. 只有在 baseline 误差来源被量化后，再进入 active OLE 问题。

## 9. 本地结果文件

- `G2_RESULTS.md`：baseline 结论与统计摘要；
- `RESOURCE_ESTIMATE.md`：本地和 Slurm 资源实测；
- `runs/baseline-49x648/delta-0p15/chi-192/summary.toml`：
  χ=192 的 20-seed summary；
- `runs/baseline-49x648/delta-0p15/chi-512/summary.toml`：
  χ=512 的 20-seed summary；
- `results/issue119-ole-g2-paired-rest/g2-paired-20.csv`：
  两个 χ 的逐 seed 配对数据；
- `results/issue119-ole-g2-paired-rest/g2-paired-20.png`：
  配对结果图。
