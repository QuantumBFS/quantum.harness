# AZ 幸存类半群锥初筛

更新时间：2026-07-28

## 结论

`AZ-survivor-cones-v1` 已在标准 `4 x 4` 数守恒表示中完成 560 个参数格点、
140,000 个行列式权重。结果很明确：

- BDI 固定 split-contraction 锥、AII 非 Hermitian Kramers 代数和 CII
  Kramers 保持锥三个已知正对照没有稳定负权或复权；
- 允许 BDI 每片独立选择收缩/膨胀方向后，出现 4,219 个稳定负权；
- DIII 的粒子-空穴保持 metric cone 从深度 3 开始普遍产生复权；
- DIII/CII 的 generic positive direction 在深度 2 已普遍产生复权。

因此，这批最自然的数守恒 AZ 锥推广没有留下新的正性机制。它把搜索空间缩小到真正的
BdG/复 Majorana/Pfaffian 条件、比 TN 更大的乘法半群，以及由具体物理模型限制出的锥交集。

## 协议

每族使用 20,000 个权重，覆盖：

```text
depth = 2,3,4,8,16
scale = 0.5,1,2,3
seed  = 9401,9402,9403,9404
samples per cell = 250
```

全部 560 个格点完成，生成元结构残差最大值为零，累计 cell runtime 约 57.5 秒。
协议定义位于 `protocols/az-survivor-cones-v1/`，忽略出 Git 的完整 manifest 和汇总位于
`tracks/qmc/results/no-negative-vibes/az-survivor-cones-v1/`。

## 汇总

| 矩阵族 | positive | negative | complex | zero | uncertain | 判断 |
|---|---:|---:|---:|---:|---:|---|
| BDI fixed split cone | 18,832 | 0 | 0 | 110 | 1,058 | 已知正对照 |
| BDI two-sided cone | 14,869 | 4,219 | 0 | 32 | 880 | 淘汰 |
| AII non-Hermitian Kramers | 20,000 | 0 | 0 | 0 | 0 | 已知正对照 |
| DIII PHS-preserving cone | 4,001 | 0 | 14,437 | 42 | 1,520 | 淘汰 |
| DIII generic cone | 2 | 0 | 18,621 | 31 | 1,346 | 淘汰 |
| CII Kramers-preserving cone | 18,702 | 0 | 0 | 40 | 1,258 | 已知正对照 |
| CII generic cone | 1 | 0 | 18,591 | 35 | 1,373 | 淘汰 |

`uncertain` 和 `zero` 集中在大尺度、深乘积的 float64 病态区，不作为正性证据，也不作为
反例。已知正对照中的代表性 `uncertain` 用 80 位重放后恢复为正数；CII 样本的虚部相对
实部约为 `10^-67`，来自保存下来的 float64 输入没有精确满足反幺正约束。

## 80 位代表反例

| 失败族 | 最小失败深度 | 代表格点 | 80 位重放 |
|---|---:|---|---|
| BDI two-sided | 2 | `cell-0089` | `-2.80225731260794046748...` |
| DIII PHS-preserving | 3 | `cell-0257` | `22.23417880962057... + 1.77164826298851... i` |
| DIII generic | 2 | `cell-0321` | `12.59577301129741... - 0.121686038227327... i` |
| CII generic | 2 | `cell-0481` | `13.96952277806837... - 0.273798688846233... i` |

这些样本的 `cond(I+D)` 约为 `1.8`–`22.7`，不是病态矩阵造成的符号误判。它们是稳健的
高精度数值淘汰证书。BDI 两面锥还可进一步精确关闭；其余三个复权族若要写成最终数学
定理，仍应继续把最小反例有理化或符号化。

## BDI 两面锥的精确反例

取 `eta=diag(1,-1)`，以及两个零模向量

```text
u = (1,1)^T,       v = (1,-1)^T,
N = eta u u^T,     M = -eta v v^T.
```

`N` 属于正向 split-contraction 锥，`M` 属于反向锥，并且 `N^2=M^2=0`。因此

```text
det[I + exp(qN) exp(qM)] = 4(1-q^2).
```

把它嵌入本轮使用的 `eta=diag(1,1,-1,-1)` 后，两个不活跃方向各贡献因子 2：

```text
w_4d = 16(1-q^2).
```

任意 `q>1` 都给出严格负权，所以 BDI 正向/反向完整并集不只是“随机扫描看起来失败”，
而是在两层、秩一锥边界上解析失败。实现与回归测试位于
`oracle/az_semigroup_cones.py::bdi_two_sided_boundary_counterexample`。

## 为什么三个幸存者不是新发现

### BDI fixed split cone

它就是一个固定不定度量下的单向 contraction cone，属于已知 split/contraction-semigroup
机制。把同一时间序列扩展到正负两个方向后立即出现负权，因此不能靠“两面化”得到更大类。

### AII non-Hermitian Kramers algebra

每个生成元都保持同一个平方为 `-1` 的反幺正时间反演。乘积的谱按 Kramers 共轭对配对，
所以 determinant 非负；这正是已知 Kramers 机制，不是新锥。

### CII Kramers-preserving cone

虽然写成 CII chiral metric 加 PSD 方向，但对 PSD 方向施加同一个时间反演约束后，每片
仍保留固定 Kramers 对称。零失败来自已知机制。拿掉这个约束，深度 2 就普遍得到复权。

## 边界

这轮只回答：

```text
标准 4 x 4 数守恒表示
+ 最自然的 chiral-metric PSD 方向
+ determinant 权重
```

它不回答完整 BdG 问题。配对时间片的物理权重可能是 Pfaffian 或 Majorana Spin trace，
而 determinant 只看到它的平方；因此不能用本轮结果声称 DIII/CII 的全部配对半群已经
关闭。

下一步不再把这些失败族扩到百万样本，而是：

1. 写清复 Majorana 非 Hermitian 条件和 Pfaffian/Spin-trace 分支；
2. 只扫描满足具体 pairing/HS 可达约束的子空间；
3. 同步搜索比 TN 更大的主子式非负乘法半群或真正改变 Hilbert 空间的 gauge/ancilla
   编码。
