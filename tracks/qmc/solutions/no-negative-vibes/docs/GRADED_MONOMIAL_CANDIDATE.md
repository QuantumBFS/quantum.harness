# Graded monomial crossing：TN 的带符号交换扩张

日期：2026-07-28  
负责人：`xianzhipan`  
分支：`work/xianzhi/graded-monomial`  
状态：`proof-candidate`

## 1. 候选定义

纯正系数 TN Gaussian 正和已经被固定 Fock 基 stoquastic 定理封闭。本候选只放宽
一个条件：允许平面网络出现 permutation crossing，同时把 permutation parity 记录为
一个可乘的标量 grade。

令

```text
B = P D,
```

其中 `P` 是置换矩阵，`D=diag(d_1,...,d_n)` 且 `d_i >= 1`。定义

```text
chi(B) = sgn(P).
```

两个这种矩阵的乘积仍为 `P'D'`，所有新对角权仍不小于一，并且
`chi(B_2 B_1)=chi(B_2)chi(B_1)`。

希望证明：

```text
chi(B) det(I+B) >= 0
```

对整个乘法半群成立。因此若一次连续时间顶点的标量符号等于 `chi(B_s)`，任意深度
构型的标量符号都会精确抵消 determinant 符号。

这可视为“正对角 TN 网络 + 带 Z2 grade 的 crossing”，不是 TN 本身。

## 2. 为什么可能非负

把 `P` 分解成不交循环。长度为 `ell` 的循环贡献

```text
1 + (-1)^(ell-1) product_(i in cycle) d_i.
```

奇循环因子为正；偶循环因子非正。偶循环的个数模二恰好给出 `sgn(P)`，所以乘上
`chi(B)` 后整个 determinant 非负。

这是一般证明路线，不依赖有限深度扫描。数值枚举只负责检查实现、乘法顺序和 Fock
约定。

它补上了此前 positive-monomial 批次留下的一个缺口：此前通过禁止偶阶置换来避免负
权；这里保留偶置换，但用可乘 grade 抵消它的符号。

## 3. 最小物理来源

在图的一条边 `e=(i,j)` 上取 mode transposition `P_e`，并令

```text
D_e(r) = diag(1,...,r at i,...,r at j,...,1),  r>1,
B_e(r) = P_e D_e(r).
```

`B_e` 是实对称正 monomial 矩阵，`chi(B_e)=-1`。它的完整 Fock lift 是局域
Hermitian 算符

```text
Gamma(B_e)
 = 1 - n_i - n_j
   + (1-r^2)n_i n_j
   + r(c_i^dag c_j + c_j^dag c_i).
```

考虑物理 Hamiltonian

```text
H = sum_e q_e Gamma(B_e),        q_e>0.
```

连续时间 Taylor/interaction expansion 的一次插入为

```text
-q_e Gamma(B_e).
```

长度 `k` 历史的标量符号是 `(-1)^k`，也等于所有 edge transposition 乘积的
permutation parity。因此

```text
W_C = (product_e q_e) (-1)^k det(I+B_C) >= 0.
```

去掉常数与化学势后，每条边就是

```text
+t_e(c_i^dag c_j+h.c.) - U_e n_i n_j,

t_e = q_e r_e > 0,
U_e = q_e(r_e^2-1) > 0.
```

也就是带正号 hopping 和吸引相互作用的 spinless-fermion `t-V` 模型。对奇环，正
hopping 的符号积不能由站点 `+/-` gauge 全部改成 stoquastic 负号；这提供最小的
非二分、非固定 Fock-sign-gauge 物理实例。

给定任意 `t_e,U_e>0`，方程

```text
U_e/t_e = r_e - 1/r_e
```

有唯一 `r_e>1`，再取 `q_e=t_e/r_e`。相互作用与 hopping 因而不是只覆盖一条特殊
参数曲线；顶点同时固定一个可明确写出的边化学势。

## 4. 已知机制排重

- **ordinary TN**：不属于；一次 transposition 已有负 determinant 和负二阶子式。
- **TN 正 Gaussian 正和**：不属于；每次 transposition 的标量系数为负。
- **奇数阶 positive-monomial**：不属于；本候选的最小生成元正是奇置换/二循环。
- **固定站点/Fock 对角符号规范**：奇环预期不属于，需穷举证书。
- **flavor doubling / modulus square**：定义中没有。
- **split、Majorana/Kramers、contraction semigroup**：尚未完成代数排重。
- **文献史新颖性**：不主张；必须核对 fermion permutation/loop、meron-cluster、
  CT-INT 与 attractive spinless-fermion 文献。

协作者的 R01–R03 分别研究 Klein/Fock circuit、Klein–Spinor HS 和 `D4` triality；
本候选研究的是一维表示 `sgn(P)` 对 monomial determinant 的逐历史抵消，不占用上述
表示锥认领。

## 5. 最小验证

必须完成：

1. 任意 mode pair 上 `Gamma(B_e)` 与上述二体算符逐矩阵元相等；
2. 不等 `r_e` 的三角图历史穷举，并与循环分解公式交叉检查；
3. 精确证明任意深度，而不是用“零负样本”替代理论；
4. 枚举三角图一粒子 sector 的全部站点符号 gauge，证明不能全部变成非正 off-diagonal；
5. 对 Taylor 系数同时用物理 Hamiltonian 矩阵乘方和 auxiliary histories 计算；
6. 检查零权边界 `d_i=1`、非法 `r<=1` 和浮点容差；
7. 完成已知 sign-free 机制与文献排重。

## 6. 升级与停止条件

升级为 `physical-candidate` 需要：

- 局域算符恒等式；
- 任意历史一般证明；
- 三角/奇环非固定 gauge 证书；
- 可执行测试全部通过。

立即停止或降级，如果：

- 标量 grade 在混合边历史中不再等于最终 permutation parity；
- 物理顶点不能保持局域 Hermitian；
- 奇环模型可由一个固定局域规范直接化为已知 stoquastic 模型；
- 文献表明这正是已有 loop/meron 算法的标准重写。

