# 六模式 Fock–CP 首轮筛选结果

更新时间：2026-07-29

## 一句话结论

Fock–CP 的最自然 Klein-circuit 实现没有产生重叠正锥：在 13 个深度不超过 2 的
连续 Klein–Hodge 电路、20 种 `8 x 8` Fock tensorization、数守恒与 BdG 两族共
520 个线性系统中，所有 bridge hopping/pairing 都已经被
Hermiticity-preserving 条件强制为零。

这关闭的是一个明确的有限变换库，不是所有 Fock–CP/Choi 锥。

## 测试对象

六个物理模式上的两个重叠四模式块为

```text
X = {0,1,2,3}
Y = {2,3,4,5}
bridge edges = {(0,4),(1,5)}.
```

Fock 空间维数为 `64=8^2`。每个固定变换后，把 64 维 Fock 向量空间按三个
ket modes 和三个 bra modes 识别为 `End(C^8)`。

固定变换库包含：

```text
identity
K0, K1, K2
Ki Kj,  i,j in {0,1,2}
```

其中 `Ki` 是作用在连续四模式 `{i,i+1,i+2,i+3}` 上的 Klein–Hodge 门。
因此共有 `1+3+9=13` 个电路。旧 R01 的

```text
U6 = K2 K0
```

是其中一个单元，不是被单独特殊处理。

每个电路检查全部 `C(6,3)=20` 种 ket/bra 切分，以及：

- 数守恒基：24 个生成元，4 个 bridge hopping 坐标；
- BdG 基：42 个生成元，8 个 bridge hopping/pairing 坐标；
- support mask：`rings-bridges`。

总计：

```text
13 transforms x 20 tensorizations x 2 families = 520 cells.
```

## 为什么先检查 Hermiticity preserving

完全正映射一定保持 Hermitian 算符为 Hermitian 算符。对每个固定变换和切分，
将每个 Fock 二次生成元 reshuffle 成 Choi 矩阵 `J_i`，先精确写出实系数线性条件

```text
sum_i x_i (J_i - J_i^dagger) = 0.
```

只有这个线性零空间中的方向才可能是 CP-semigroup 生成元。随后才需要检查条件
Choi 块是否半正定。

本轮所有 bridge 在第一道线性门就消失，因此 SDP 求解器和后续随机正锥采样都不会
改变 bridge 结论。

## 数值结果

使用 `float64` SVD，relative rank tolerance 为 `1e-10`：

| family | cells | HP dimension range | conditional-span rank | HP bridge cells | 最大 bridge 零空间投影 |
|---|---:|---:|---:|---:|---:|
| number-conserving | 260 | 1–7 | 0–3 | 0 | `4.61e-15` |
| BdG | 260 | 1–12 | 0–9 | 0 | `6.98e-15` |
| 合计 | 520 | 1–12 | 0–9 | 0 | `<7.0e-15` |

`HP bridge cells=0` 表示没有任何测试单元允许 bridge 系数进入
Hermiticity-preserving 零空间。随机抽取的条件 CP 方向中，bridge 计数同样为零。

旧 `U6=K2 K0` 在两族、全部 20 种切分中都只剩一维纯 drift 子空间，bridge 为零。
这与 R01 的 Metzler exact-zero 结论相互独立但方向一致。

## 能说什么，不能说什么

可以说：

- 已建立 Liouville–Choi、完全正和条件完全正的可测试 oracle；
- 已系统排除 identity 与全部深度不超过 2 的连续 Klein 电路；
- 失败发生在 CP 半正定约束之前，是一个更便宜的线性障碍；
- 旧 R01 变换不能通过“把 entrywise cone 换成 Choi PSD cone”直接复活。

不能说：

- 所有 Fock–CP 变换都不存在；
- 任意非高斯 Fock circuit 都失败；
- 当前浮点秩测试已经是 exact Farkas/no-go 证书；
- Fock–CP 路线已经没有研究价值。

若要把本结论升级为 exact no-go，需对 520 个 Hermiticity 线性系统做
`Q(sqrt(2))` rank/nullspace 重建。由于最大 bridge 投影与容差相差四个数量级，
当前数值结论足以决定下一步，不值得在同一有限电路库上先投入昂贵 exact 化。

## 下一步

1. 主线转到已经有任意深度恒正定理的 tensor-square 类，优先解决绑定 HS 场能否
   来自局域相互作用；
2. Fock–CP 只保留结构上真正不同的变换，例如非 Klein 的局域 entangling circuit
   或直接由正乘法代数诱导的 Choi basis；
3. 不为当前 finite Klein catalog 安装 SDP 求解器，因为 bridge 已在线性门消失。

机器可读摘要：

- `fixtures/fock_cp_overlap_screen.json`
- `protocols/fock-cp-overlap-v1/`

原始逐单元 JSON 保存在 gitignored 结果目录：

```text
tracks/qmc/results/no-negative-vibes/fock-cp-overlap-v1/
```
