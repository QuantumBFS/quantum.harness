# TN 平面网络的逆 HS 候选卡

日期：2026-07-28  
负责人：`xianzhipan`  
分支：`work/xianzhi/tn-inverse-hs`  
状态：`known-mechanism`（精确物理 witness；因 stoquastic 等价而降级）

## 1. 研究问题与候选定义

目标不是给任意 TN 矩阵取对数，而是从局域、精确的算符恒等式

```text
-v_local = sum_s p_s Gaussian(B_s),    p_s > 0, B_s TN
```

反向设计一个有明确相互作用、可在格点上重复铺设的 Hermitian 费米子
Hamiltonian。这里 `Gaussian(B)` 是数守恒单粒子矩阵 `B` 的 Fock 空间
二次量子化表示。

第一候选使用三个连续排序的费米模式和 elementary Jacobi shears

```text
x_12(a) = I + a E_12,
x_23(b) = I + b E_23,                 a,b > 0,
X = x_12(a) x_23(b),
Y = x_23(b) x_12(a).
```

`X`、`Y` 及其转置都是可逆 TN 矩阵。拟证明并实现

```text
Q_123 = Gaussian(X) + Gaussian(Y)
      + Gaussian(X^T) + Gaussian(Y^T)

      = 4
      + 2a (c_1^dag c_2 + h.c.)
      + 2b (c_2^dag c_3 + h.c.)
      + ab [c_1^dag (1-2n_2) c_3 + h.c.].
```

于是 `v_123 = -g Q_123`（`g>0`）有一个四值、等正权的精确连续时间
辅助场分解。把同一顶点平移到一条开放有序链的相邻三站点上时，每个
辅助场矩阵仍为 TN，任意历史的 grand-canonical determinant 非负。

第二候选是在四个连续模式上对两个不交叠 shear 的乘积与转置做同样
的 Hermitian 化，检查所得 pair-hopping / simultaneous-hopping 顶点
是否比第一候选有更独立的物理意义。只有第一候选完成严格闭环后才进入
第二候选。

## 2. 相对共享基线 `e915e48` 的新增内容

共享基线已经完成：

- TN 乘法半群与 `det(I+D)` 正性；
- 开放 Hubbard/`t-V` 链的 density-channel 映射；
- 两站点排斥 `t-V` 键门的精确非对称 TN Gaussian 正和；
- 固定 Fock 基下普通远邻 hopping 的正和 no-go。

本候选第一次把 Loewner--Whitney/Jacobi 因子的**次序差**直接用作
相互作用来源。目标相互作用不是普通远邻 hopping，而带有中间站点
Jordan--Wigner 宇称，因此不受已有普通 hopping no-go 排除。

## 3. 物理权重与 HS 来源

使用连续时间 interaction expansion：

```text
H = H_0 + sum_i v_i,
Z = sum_C (product of positive scalar coefficients)
          det[I + time_ordered_product(B_C)].
```

`H_0` 只允许开放路径的实 hopping、化学势或其他 TN-compatible
单粒子项。每个 `-v_i` 是四个 TN Gaussian 顶点的正和，所以任意
辅助场历史的单粒子乘积仍 TN。

需要分别核对：

1. 算符恒等式在完整 `2^3` 维 Fock 空间精确成立；
2. 顶点在重叠三站点上的嵌入仍 TN；
3. Hamiltonian Hermitian、局域且不需要复 HS 系数；
4. 常数和最近邻 hopping counterterm 的符号与 `H_0` 兼容；
5. 该模型是否只是 Jordan--Wigner 后显然 stoquastic 的 XY 模型。

## 4. 已知机制排重

- **TN**：属于；这是从 TN 构造物理顶点，而不是新矩阵机制。
- **固定 Fock 基 stoquasticity**：高度可能属于，必须显式写出
  Jordan--Wigner 映射；若属于，只能定位为有意义的物理实现/算法，
  不能宣称新的 sign-free 机制。
- **split-orthogonal / Kramers / Majorana**：尚未逐模型审计；矩阵正性
  已由 TN 充分保证，不把“无法立刻看出等价”当作新颖性证据。
- **普通远邻 hopping no-go**：不属于其假设，因为目标 hopping 带
  `(1-2n_2)` 宇称串。
- **flavor doubling / determinant square**：不使用；目标是单 flavor、
  单 determinant。

## 5. 最小检验与证据纪律

第一个非平凡系统是三个模式、八维 Fock 空间。

计划：

1. 用显式 Jordan--Wigner 矩阵构造 `c_i`、`n_i`；
2. 独立从所有子式构造 `Gaussian(B)`；
3. 对符号参数或多组非退化有理参数验证上述恒等式；
4. 检查所有 `B_s` 子式非负、任意代表历史的 determinant 非负；
5. 写出 Jordan--Wigner 后的自旋 Hamiltonian；
6. 在四至六站点重叠顶点上穷举短历史作为实现回归，而不把零失败当证明。

大型随机扫描不是本轮前置条件；精确局部代数和半群闭包已经足够决定
第一候选是否成立。

## 6. 成功、失败与停止条件

成功标准：

- 有机器可验证的精确局部 HS 恒等式；
- 有任意系统尺寸/任意历史的 TN 正性证明；
- 得到局域、Hermitian、含真实多体相关 hopping 的 Hamiltonian；
- 准确说明其与 stoquastic/Jordan--Wigner 已知机制的关系；
- 若不新，仍给出可复现的 determinant-QMC 实现价值或明确边界。

停止/降级条件：

- 恒等式在完整 Fock 空间不成立；
- overlapping embedding 离开 TN；
- 只能通过非局域 counterterm 或负/复标量实现；
- 模型严格退化为已有 stoquastic spin 模型且没有独立算法价值。

若第一候选因最后一条降级，将把结论保留为“positive-TN inverse HS 的
stoquastic 边界”，并另开候选研究 signed/graded TN；不在本分支悄悄
扩大研究范围。

## 7. 首轮结案

第一候选的局部恒等式、任意历史正性和物理 Hamiltonian 已全部完成，
详见 [TN_NETWORK_PHYSICAL_MODEL.md](TN_NETWORK_PHYSICAL_MODEL.md)。

Jordan--Wigner 逐矩阵元审计表明它精确等价于 ferromagnetic
hard-core-boson/XY 最近邻加次近邻 hopping。更一般地，任何固定
Fock 基下的正系数 TN Gaussian 正和都会使 `-v` 逐元非负，因此物理
顶点已经 stoquastic。

这触发了本卡的降级条件。四模式 pair-hopping 即使成立也不能越过同一
一般命题，所以不再为寻找新 sign-free 机制而继续枚举；后续 signed/
graded TN 必须单独认领。
