# Stage 3 — 双机首轮粗相图

日期：2026-07-29

## 运行范围

完整运行批准网格：

```text
m = 4, 6, 8
βg_A = 2, 4, 8
g_B/g_A = 0, 0.25, 0.5, 1, 2
t/g_A = 0, 0.25, 0.5, 1, 2
μ/g_A = -1.5, 0, 1.5
Δτg_A = 0.2
```

每个 cell 使用 40 个 warmup sweep、80 个 measurement sweep、每 2 sweep
测量一次。WSL 分片使用 14 workers 完成 135 个 cell，CPU machine 使用
62 workers 完成 540 个 cell；所有 BLAS 均为单线程。seed 由
`SHA256(experiment_id|cell_id|worker_id)` 的前 32 bit 唯一确定。

## 正确性门

```text
expected / complete cells  = 675 / 675
missing / error / duplicate = 0 / 0 / 0
BROKEN regions             = 0
minimum direct sign        = +1
maximum log-weight error   = 9.8639e-7
β=2 stabilized retries     = 17
```

`β=4,8` 从开始即使用 SVD 缩放长乘积。17 个 `β=2` cell 的逐样本审计达到
重跑阈值后，以同一确定性 seed 走稳定化路径并通过。checkpoint 和运行
日志保留在计算机上；Git 只保存约 640 KiB 的聚合表、图和 manifest。

最终生产结果从干净提交
`b4459ae0d1c64ba021ffce634d26402362575171` 在两台机器重新完整运行。
675 个 cell 的 fingerprint 均包含该源码 revision、参数、seed 与采样日程；
两机 manifest 均记录 `dirty=false`。逐样本最大 log-weight error 实际为
`9.8639e-7`，密度范围为 `[5.5448e-9, 1+3.3307e-8]`。

唯一触及旧密度阈值的点是稳定化 `t=0` 对照
`(g_B/g_A,t/g_A,μ/g_A,m,β)=(2,0,1.5,4,8)`；其平均密度 `0.999874`、
log-weight error `5.68e-14`、direct sign `+1`，确认是双精度舍入。
密度审计容差因此经 Red→Green 回归统一为 `1e-7`，而 `2e-6` 越界仍会失败。

## 首轮分类

控制线修正后的 75 个 region 分类为：

```text
SURVIVE = 14
EXTEND  = 27
STOP    = 34
BROKEN  = 0
```

`g_B=0` 是单通道基准，`t=0` 已在 ED 轮早停；两者仍显示在粗图中，但
不会进入密集扫描预算。

## 最稳健的正面候选

半填充出现连续的尺寸/降温增强带。核心代表点如下：

| g_B/g_A | t/g_A | μ/g_A | Q²(β=2,m=8) | Q²(β=8,m=8) | m4→m8 ΔQ² | thermal z |
|---:|---:|---:|---:|---:|---:|---:|
| 0.25 | 0.25 | 0 | 1.948 | 2.361 | 1.191 | 10.81 |
| 0.25 | 0.50 | 0 | 2.162 | 2.486 | 1.178 | 5.26 |
| 0.25 | 1.00 | 0 | 2.418 | 2.572 | 1.310 | 7.42 |
| 0.50 | 0.25 | 0 | 1.926 | 2.445 | 1.209 | 7.22 |
| 0.50 | 0.50 | 0 | 2.220 | 2.515 | 1.252 | 8.75 |
| 1.00 | 0.25 | 0 | 1.802 | 2.327 | 1.286 | 4.83 |

这一带不是单通道控制的简单重复，并与 ED 在 `g_B/g_A≈1` 的 gap 谷相接。
它是 Stage 4 的第一优先区域，但短链结果仍不能直接称为有序相或临界线。

## 次级幸存者与经验调整

完整 14 点列表见 `aggregate/survivors.csv` 和 `survivors.json`。其中
`g_B/g_A≈1` 的若干点主要因 channel balance 换序而幸存；代表点
`(g,t,μ)=(1,1,-1.5)` 还同时具有 `β8−β2 ΔQ²=0.135`（`11.6σ`）。
不过 `μ=+1.5` 与 `-1.5` 的短链图并非处处对称，下一轮必须成对加长，
避免把自相关或热化差异误判成掺杂不对称。

27 个 EXTEND 中只保留与核心带相邻且已有正趋势的少数点，例如
`(g,t,μ)=(0.5,1,0)` 和 `(1,0.5,0)`；它们的 β=8,m=8 有效样本不足 4，
所以不在本轮升级为 SURVIVE。其余 EXTEND 不获得长链预算。

## 产物

- `results/stage3_coarse_20260729/aggregate/summary.json`
- `results/stage3_coarse_20260729/aggregate/table.csv`
- `results/stage3_coarse_20260729/aggregate/regions.csv`
- `results/stage3_coarse_20260729/aggregate/survivors.csv`
- `results/stage3_coarse_20260729/aggregate/survivors.json`
- `results/stage3_coarse_20260729/aggregate/figures/rough_phase_diagram.png`
