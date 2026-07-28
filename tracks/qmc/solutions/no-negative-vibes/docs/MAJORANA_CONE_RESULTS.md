# 共享实结构的 Majorana 双锥扫描

## 一句话结论

两个 Majorana reflection-positive 锥即使共享同一个反线性实结构 `J1`，也不能在不同时间片中
任意混用：共同 `J1` 保证 Fock 迹为实数，但不保证其非负。相反收缩方向已有深度二精确负权
证书；较一般的相对角扫描也发现大量负权。

## 为什么需要新的权重 oracle

对复反对称 Majorana 生成元 `A_l`，物理小系统权重是连续 Spin 表示中的 Fock 迹

```text
p = Tr(exp(h_1) ... exp(h_L)),
h_l = gamma^T A_l gamma / 4.
```

它满足

```text
p^2 = det(I + exp(A_1) ... exp(A_L)).
```

行列式只能看到平方，不能确定 Spin 双覆盖的符号分支。因此本轮直接在维数 `2^N` 的 Fock
空间计算 `p`，同时把行列式恒等式作为条件数允许时的交叉检查。Fock 乘积每层除以一个正的
Frobenius 范数，避免高尺度溢出且不改变符号或相位。

## 候选定义

单个已知正锥由反对易的实正交结构 `J1,J2` 定义：

```text
J1^T A J1 = conjugate(A),
i (J2 A - conjugate(A) J2) <= 0.
```

本轮保留公共 `J1`，把第二套收缩结构写成

```text
J2(theta) = O(theta) J2 O(theta)^T,
```

其中 `O(theta)` 与 `J1` 对易。奇偶时间片分别从 `J2` 和 `J2(theta)` 的已知正锥取样。
这排除了“混用不同实结构所以权重直接变复数”的平凡失败，专门检验共同实权条件是否足以保护
符号。

## 宽扫描 v2

- 4 和 6 个 Majorana，自由 Fock 维数分别为 4 和 8；
- 深度 `2,3,4,6,8,12,16`；
- 尺度 `0.5,1,2,3`；
- 八个相对角，从 `0` 到 `pi`；
- 四个种子、每格 250 个 Fock 迹；
- 1,792 格、448,000 个权重，1,792/1,792 成功；
- 结构残差最大 `1.17e-15`，公共 `J1` 残差最大 `4.78e-16`；
- 0 复权、0 不确定；共 19,128 个负权。

| 相对角 | 4 Majorana：负权/28,000 | 6 Majorana：负权/28,000 |
|---:|---:|---:|
| `0` | 0 | 0 |
| `0.2` | 0 | 0 |
| `0.4` | 3 | 0 |
| `0.8` | 72 | 9 |
| `1.2` | 401 | 64 |
| `pi/2` | 1,303 | 431 |
| `2.2` | 3,849 | 2,518 |
| `pi` | 5,708 | 4,770 |

角度零的 56,000 个样本全部为正，是同一 Majorana 锥定理的正对照。4-Majorana 在角度
`0.8`、6-Majorana 在角度 `1.2` 已从深度二出现负权；夹角越大、生成元尺度越大，失败率
总体越高。

协议在
[majorana-shared-reality-cones-v2](../protocols/majorana-shared-reality-cones-v2/README.md)，
本地结果在
`tracks/qmc/results/no-negative-vibes/majorana-shared-reality-cones-v2/`。

## 深度二精确证书

在 4-Majorana 空间取两个共享 `J1`、但满足 `J2'=-J2` 的生成元。令

```text
alpha = sqrt(pi^2 + 1).
```

第一个生成元的非零结构由实反对称块 `B_12=alpha` 和半正定块 `C=diag(0,2)` 给出；
第二个取 `B=0`、同一个 `C`，再旋转到相反 `J2` 锥。两者都精确满足：

```text
A_l^T = -A_l,
J1^T A_l J1 = conjugate(A_l),
i(J2_l A_l - conjugate(A_l)J2_l) <= 0.
```

在 Fock 奇宇称块中两次演化互相抵消，贡献迹 `2`；偶宇称块贡献 `-2 cosh(1)`。因此

```text
p = 2 - 2 cosh(1) < 0,
det(I + exp(A_1)exp(A_2)) = p^2 > 0.
```

这同时证明双锥并集不是无符号类，并具体展示了 determinant-only oracle 为什么会漏掉
Majorana 权重的负分支。机器可读证书在
[majorana_trace_certificates.json](../fixtures/majorana_trace_certificates.json)，自动测试检查
两个锥条件、宇称块化简、精确负号和生产 oracle。

## 小角压力测试

宽扫描对角度 `0.2` 零命中，因此追加：

- 相对角 `0.05,0.1,0.2,0.3,0.4`；
- 深度最高 32，尺度 `3,4,6`；
- 4/6 Majorana、四个种子、每格 300；
- 840 格、252,000 个直接 Fock 迹，840/840 成功。

结果：

| 相对角 | 4 Majorana：负权/25,200 | 6 Majorana：负权/25,200 |
|---:|---:|---:|
| `0.05` | 0 | 0 |
| `0.1` | 0 | 0 |
| `0.2` | 0 | 0 |
| `0.3` | 0 | 0 |
| `0.4` | 16 | 4 |

角度 `0.4` 的首次压力测试负例都在深度 8：4-Majorana 从尺度 4 出现，6-Majorana 从尺度
6 出现。两个代表样本用 80 位 Fock 迹重放并强制公共 `J1` 到高精度后得到

```text
p_4 = -7.8076325573022858e7,
p_6 = -2.5995080597882497e19,
```

虚部分别为零和约 `1e-62`，所以不是近零误判。

协议在
[majorana-small-angle-stress-v1](../protocols/majorana-small-angle-stress-v1/README.md)，本地结果在
`tracks/qmc/results/no-negative-vibes/majorana-small-angle-stress-v1/`。

## 结果边界与下一步

已经关闭的命题：

1. “每个时间片分别属于某个 Majorana 正锥”不足以保证整条时间历史无符号；
2. 共享同一个 `J1` 只保证权重为实数；
3. 即使只有两个时间片，Spin 分支也可为负，而 determinant 平方仍为正。

尚未关闭的区域：

- 相对角 `0.05–0.3` 的有限网格零命中不是证明；
- 需要解析推导固定角度下两锥乘积的最小 Fock 迹，或用约束优化寻找最坏生成元；
- 如果存在真正的角度/范数联合充分条件，还必须检查它是否超出已知单锥收缩半群并能由
  Hamiltonian 与 Hubbard–Stratonovich 分解实现。

因此下一步应从随机宽扫转为“小角解析/约束优化”，而不是继续增加相同分布的随机样本。
