# 4×4 PQMC–UHF-CP 路径桥接：生产结果

## 1. 固定配置与程序职责

- 4×4 square，PBC×PBC，半满 `N↑=N↓=8`；
- `t=1, U=4, Δτ=0.05, β=1, Θ=10, Ltrot=420`；
- 实二值 Hirsch spin HS；
- ALF 右边界为 free，TI 左边界为 `Ueff=4` UHF；
- MATLAB CPMC-Lab 只运行直接 UHF-CP；
- ALF 完整路径只由集群上的 oneMKL/C++ 程序重放。

## 2. PQMC 与直接 CP 基准

128 链、跨链同编号 bin 汇总后的标定结果为：

| 模拟 | 能量 | 误差 | Green 最大误差 | 状态 |
|---|---:|---:|---:|---|
| ALF free/UHF | −13.623403 | 0.003450 | 9.90×10⁻⁹ | 两个门槛通过 |
| ALF free/free | −13.626885 | 0.003640 | 3.41×10⁻⁹ | 两个门槛通过 |
| MATLAB UHF-CP, 1000 walkers | −13.468324 | 0.003115 | — | 直接 CP |

精确能量为 −13.62192。ALF 与精确值相容；当前直接 CP 比精确值高
0.15360。文献给出的同类 UHF/spin-HS 结果 −13.478(2) 也有同方向的
约 0.144 系统偏差。

## 3. 生产构型与数值验证

II 和 TI 各使用 128 条独立链。每链热化 2000 sweep 后，每隔 239 sweep
保存一次，在 sweep 2239–3912 共保存 8 条。因此：

- 每个 ensemble 1024 条；
- 总计 2048 条 6720-bit 路径；
- 256 个 archive 文件；
- 2048 个 sample ID 全部唯一，CRC、header 和 sweep 序列全部通过。

C++ 同时计算 ALF 的 `VK` 切口与 CP 的 `K/2–V–K/2` 切口。ALF 切口只用于
逐路径验证，CP 对称切口用于抽样效率和后续物理分析。

| 验证量 | 结果 |
|---|---:|
| ALF/C++ 最大 `log|D|` 残差 | 8.19×10⁻¹² |
| 中央能量残差 95% 分位 | 3.86×10⁻⁹ |
| overlap identity 残差 99% 分位 | 4.73×10⁻¹¹ |
| 稳定化间隔 1/5/10 最大核心差异 | 5.92×10⁻¹⁰ |
| 数值歧义路径比例 | 3.125% |
| replay 数值门槛 | 通过 |

所有 1024 条 TI 路径均 `alive`，且 `D_TI>0`。数值歧义表示 ALF/C++ 的
局域能量或 identity 诊断未过严格门槛，不表示负权重或物理节点；抽样效率
分析排除了这些路径。

## 4. 最差 1% 抽样效率

对 976 条无数值歧义的 TI 路径定义

```text
log sampling efficiency = log Q_CP(X) − log D_TI(X).
```

这里只使用其相对排序；`D_TI` 与 `Q_CP` 的构型无关归一化常数不影响排序。

主要结果：

- 最差 1% 共 10 条；
- 其中 8/10 的 `log D_TI` 高于全部样本的中位数，因而不是低权重尾部；
- 若使用被极端大权重支配的算术平均权重作门槛，则为 0/10；在当前
  1024 条重尾样本上该门槛不稳健，因此中位数是“典型重要构型”的主定义；
- 抽样效率与 prefix barrier 的 Spearman 相关系数为 −0.933；
- 抽样效率与 `log10(min σ)` 的 Spearman 相关系数为 +0.758；
- `log Q_CP` 与 `log D_TI` 的 Spearman 相关系数只有 +0.272。

因此 CP 概率与真实路径权重只有弱排序一致性；低效率主要与传播过程中
接近低 overlap 子空间以及累计 prefix 缺口相关。

## 5. 空间 pattern 与时间 pattern

最差 10 条路径的最大 prefix 缺口全部出现在最后四分之一，平均 slice 为
393.1；全部 TI 路径的平均 bottleneck slice 为 165.9。

瓶颈层的空间描述量为：

| 描述量 | 全部路径均值 | 最差 1% 均值 |
|---|---:|---:|
| `|Σ_i x_i|` | 3.10 | 2.00 |
| `|Σ_i (−1)^i x_i|` | 3.34 | 2.80 |
| PBC domain walls（最大 32） | 16.20 | 15.80 |
| 到全 +/全 − 的最小 Hamming 距离 | 6.45 | 7.00 |
| 到两种 checkerboard 的最小 Hamming 距离 | 6.33 | 6.60 |

10 个瓶颈层的 16-bit mask 全部不同。这组数据不支持“全 +1/全 −1”或单一
checkerboard 辅助场 pattern；瓶颈层在这些简单空间统计上与普通随机层接近。

稳定出现的是时间 pattern：低效率路径在虚时后段积累越来越大的 proposal
缺口，而不是由某一个特殊空间切片单独决定。

## 6. 详细 heat-bath 行走

对 5 条 TI 低 proposal 路径及 5 条按 ensemble、训练/留出集合和能量 decile
匹配的普通路径，重放全部局部更新：

| 量 | 低 proposal | 匹配对照 |
|---|---:|---:|
| 总 surprisal `−Σ log q` | 6748.1 | 5619.0 |
| `q<10⁻³` 的局部更新数 | 46.4 | 23.2 |
| `q<10⁻⁶` 的局部更新数 | 2.2 | 0.8 |
| 最大单步 surprisal | 16.57 | 14.02 |
| 最大 100 个事件占总 surprisal | 11.21% | 10.53% |

低效率路径比对照多约 1129 的总 surprisal，`q<10⁻³` 事件数恰好约为两倍；
但最大 100 个事件所占比例只增加约 6.5%，最大 10 个事件的占比几乎不变。
所以主机制不是一个孤立的极小概率事件，而是很多偏低概率选择沿长路径累计。
少量极小概率事件会加重问题，但不是总缺口的主要来源。

## 7. 能量重加权能说明什么

只用 held-out 的 64 条链、排除数值歧义路径，并把 ALF 切口重加权到 CP 对称
切口，得到

```text
E = −13.648 ± 0.122  （leave-one-chain-out jackknife，494 条路径）.
```

它与精确能量相容，但误差远大于 0.005，不能据此声称“纳入低概率路径已经
恢复精确能量”。当前生产样本足以识别抽样概率失配及其时间结构，不足以完成
精度级的能量恢复检验。后者需要沿同一 128 条链继续追加 archive，提高
held-out 的有效样本数。

## 8. 结论

这次计算给出的直接证据是：

1. 在全部测试路径均正权重、均可完整传播的条件下，UHF-CP 仍可对真实权重
   典型甚至偏大的路径赋予极低的精确抽样概率；
2. 这种失配与低 overlap/小奇异值相关，但在本样本中没有观察到真正的
   零 overlap 阻断；
3. 没有发现 DQMC 单点模型式的简单单层空间 pattern；
4. 更清楚的结构是长虚时方向上许多偏低 heat-bath 概率的累计，最大缺口
   通常在传播末段出现。

因此，这里更合适的图像不是“一个节点墙挡住所有路径”，而是 UHF guide
定义的局部条件概率在长路径上持续错配；即使每一步都非零，多个近节点/低
overlap 区域的累计抑制仍可使有限 walker population 实际上无法覆盖重要路径。

## 9. 主要可复现输出

- `results/cluster_production_128/replay_validation.json`
- `results/cluster_production_128/replay_strata.csv`
- `results/cluster_production_128/sampling_efficiency_summary.json`
- `results/cluster_production_128/worst_efficiency_1pct.csv`
- `results/cluster_production_128/trace_dynamics_summary.json`
- `results/cluster_production_128/sampling_efficiency_patterns.pdf`
- `archives/cluster_production_128/archive_index.json`
- `replay/cluster_production_128/traces/full_trace_steps.csv`
