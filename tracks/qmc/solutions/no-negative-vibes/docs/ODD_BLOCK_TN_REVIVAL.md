# R1：fixed-partition odd block-TN Hamiltonian 复活审计

日期：2026-07-30
状态：`closed-as-QNC / common-stoquastic-gauge-proved`

## 0. 复活审计后的新结论

本候选已被真正利用并完成第一项传统方法排除：整个 fixed-partition `C3` block-TN
factory 存在共同的 count-sector `+/-1` gauge，变换后 Hamiltonian stoquastic。
因此不再继续 scaling/相图投入；一般证明、发现扫描和回归见
[stoquastic no-go](ODD_BLOCK_TN_STOQUASTIC_NO_GO.md)。

## 1. 研究对象

取三条 route `r=0,1,2`，每条 route 有 `L` 个轨道。固定单粒子空间分解

```text
V = V_0 direct-sum V_1 direct-sum V_2,   dim(V_r)=L,
```

以及同步三循环 `P_C3: V_r -> V_(r+1 mod 3)`。对每个 vertex type `a` 取三个可逆
TN blocks `X_(a,r)`，定义

```text
B_a = P_C3 diag(X_(a,0), X_(a,1), X_(a,2)).
```

一个完全显式、随 `L` 可生成的 TN 子族可由正 bidiagonal factors 构造：

```text
X_(a,r)
 = D_(a,r)
   product_j [I + u_(a,r,j) E_(j,j+1)]
   product_j [I + v_(a,r,j) E_(j+1,j)],

D_(a,r)>0 diagonal,  u_(a,r,j),v_(a,r,j)>=0.
```

每个 factor 都是可逆 TN，乘积仍是可逆 TN。所有 vertex 必须共享同一个三块
partition；禁止把 route 在各空间位置独立化。

在数守恒 Fock 空间定义

```text
H_L = -sum_a q_a [Gamma(B_a) + Gamma(B_a)^dagger],   q_a>0.       (1)
```

式 (1) 是显式 Hermitian、数守恒、一般含高体项的 Hamiltonian，而不只是 transfer
matrix 的记号。

## 2. 已完成的逐历史正性

任意连续时间 history 从 oriented alphabet `{B_a,B_a^T}` 取 word

```text
D = C_1 C_2 ... C_k.
```

固定 partition 的 odd block-TN 类对乘法与转置封闭，故 `D` 仍在同一半群。奇数
block cycle 的 determinant 因子为

```text
det(I + X_ell ... X_1) >= 0
```

（TN 乘积的所有主子式非负）。Fock trace 恒等式给出

```text
Tr[Gamma(D)] = det(I+D) >= 0.
```

因此 (1) 的连续时间 Taylor/SSE-like vertex expansion 中每个 history 的系数和 trace
均非负。已有 `oracle/odd_block_tn_effective.py` 与
`tests/test_odd_block_tn_effective.py` 覆盖小尺寸 Hermiticity、数守恒、任意 word
证书及非零六体项。

## 3. 可运行性为何不是指数 Fock 代价

算法不应显式构造 `2^(3L)` 维 `Gamma(B)`。对 vertex word 只维护 `3L x 3L`
单粒子乘积 `D`，权重由 `det(I+D)` 给出；稳定化可复用 determinant QMC 的 QR/SVD
技术。需要新增的 MWE 是更新比和 observable estimator，而不是重新证明 trace identity。

这给出一个可执行 QMC 表示，但尚未证明 autocorrelation、多尺度稳定性或有限密度物理
是良性的；这些属于 `Q` 与 `P` gate 的剩余工作。

## 4. 缩放问题：本轮第一个真门槛

`Gamma(B)` 的算符范数可能随 `L` 指数增长，所以“公式对所有 L 存在”不等于
Hamiltonian 有良好热力学极限。本轮同时审计两个子族：

### A. contractive anchor

选择 blocks 使 `||B_a||_2<=1`，则 `||Gamma(B_a)||<=1`。若 vertex types 数目
`M_L=O(L)` 且 `q_a=O(1)`，有粗界 `||H_L||=O(L)`。这个子族先建立严格 extensive
基线，但必须检查它是否被公共收缩范数方法直接覆盖、是否只剩真空/弱动力学。

### B. noncontractive Kac family

允许 `||B_a||>1`，根据实测/解析的 `||Gamma(B_a)||` 选择 `q_a(L)`，使
`sum_a q_a ||Gamma(B_a)||=O(L)`。若所需 `q_a` 指数小到使所有关联在
`L -> infinity` 消失，该子族立即判为 `scaling-fail`，不以形式可扩展冒充物理模型。

## 5. 已关闭边界不重开

若让每个 site 独立选择 `C3` route，再用 flavor-preserving TN hopping 连接 sites，
route partition 与 hopping partition 相交。已有六模式两层整数证书

```text
det(I+XR) = -2.
```

因此本研究只处理固定宏观 partition 的同步 route。任何局域化提案必须先重放这条
反例，并指出它引入了什么新的 constraint/gauge/ancilla 机制来避开反例；否则停止。

## 6. 不能提前声称的内容

目前只能声称：

- `H_L` 显式、Hermitian、数守恒；
- 固定 partition 下任意 vertex history 非负；
- 至少一个六模式实例含高于二次的相互作用；
- determinant 权可在单粒子空间计算。

目前不能声称：

- 热力学极限非平凡；
- 不可由 JW、worldline/SSE、stoquastic gauge、matchgate、静态 sector 或隐藏平方模拟；
- 模型在文献中未被研究；
- 已发现 QNC 新体系。

## 7. 下一组最小、可证伪计算

1. 对 `L=2,3` 构造 deterministic bidiagonal TN atoms，核对 fixed partition 与逐 word
   权重；同时保留 crossed-partition `-2` 为负面对照。
2. 计算 occupation-basis Möbius coefficients，确认三体以上项随 `L` 持续存在。
3. 求精确 diagonal phase gauge；失败时输出最短 frustrated sign cycle。
4. 求一体与局域守恒 commutant，排查静态 sector。
5. 比较 contractive 与 Kac 子族的 `||H_L||/L`、密度和 route correlator。
6. 只有 2–5 存活后，才进行以式 (1) 为关键词核心的定向文献检索。

这六步均不触碰合作者的 tensor-square 相图、oddcycle seeds/joint-pair 或 exterior
cone 搜索。
