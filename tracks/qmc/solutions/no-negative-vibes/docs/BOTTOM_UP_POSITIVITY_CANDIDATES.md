# 自底向上正性候选：重叠闭包优先

更新时间：2026-07-29
状态：候选与最小实验设计；除明确标注的恒等式外，不能当作新发现。

## 为什么换搜索方式

此前多条路线都是先在四模式单块中找到正锥，再检查两个局域块重叠后能否共用同一
变换。R01 fixed Klein–Hodge/Fock 方案已经给出最清楚的失败边界：在六模式两个重叠
四模式块上，数守恒和 BdG 两族共 24 个 bridge hopping/pairing 坐标都被 exact
double-dual/Farkas 证书强制为零。

因此下一轮不再把重叠当作最后一项检查。候选的定义必须先回答：

```text
两个共享格点的局域时间片相乘后，为什么仍在同一个正性对象中？
```

候选还必须同时满足：

1. 任意深度闭包，不以有限随机扫描代替证明；
2. 六模式重叠测试中至少一个 bridge 系数非零；
3. 权重可在多项式时间内计算；
4. 有局域 Hermitian Hamiltonian 和正系数 HS/顶点来源；
5. 不约化到 TN、split、Kramers、Majorana reflection、模平方或普通
   stoquastic/loop 表述。

## 候选一：Fock–CP / Choi 正锥

### 定义

当模式数 `n=2r` 为偶数时，Fock 空间维数满足

```text
2^n = (2^r)^2.
```

因此可把 Fock 空间通过一个固定相似变换 `S_n` 识别为
`End(C^(2^r))` 的算符空间。对允许的一体生成元 `A`，要求其 Fock 高斯传播子
`Gamma(exp(A))` 在该识别下成为完全正映射：

```text
Phi_A = S_n Gamma(exp(A)) S_n^(-1),
Phi_A(X) = sum_a K_a X K_a^dagger.
```

完全正映射对正系数和、张量积和复合都闭合。任意历史仍是完全正映射，并且其
Liouville 迹满足

```text
Tr(Phi) = sum_a |Tr(K_a)|^2 >= 0.
```

相似变换保持乘法和迹，所以这直接给出原 Fock 历史的非负权。

### 为什么没有被 R01 关闭

R01 要求固定变换后每个 parity block 都是 entrywise Metzler；这是一个多面锥。
Fock–CP 要求重排后的 Choi 矩阵半正定；这是非多面 PSD 锥。R01 的 bridge
exact-zero 证书只关闭前者，不关闭后者。

### 六模式最小实验

使用与 R01 相同的几何：

```text
X = {0,1,2,3}
Y = {2,3,4,5}
bridge edges = {(0,4),(1,5)}
Fock dimension = 64 = 8^2.
```

第一轮不同时优化任意 `S` 和生成元，避免不可控的非凸搜索：

1. 枚举固定的 Fock tensorization、模式排列、particle-hole 和局域
   Klein/Clifford 微电路；
2. 对每个固定 `S`，把生成元的条件完全正性编译为 Choi/GKS 半正定约束；
3. 分别锚定每个 bridge hopping、pair-create 和 pair-annihilate 系数的正负号；
4. 若有非零 bridge，要求再找到两个不对易可行方向；
5. 对存活解精确重建，并检查是否只是 ket/bra 两半的 Majorana 或模平方分解。

快速停止条件：

- 所有有限深度 `S` 都把 bridge 系数强制为零；
- 只有普通左右乘 `X -> LXR^dagger` 的诱导解；
- 存活锥没有两个不对易方向；
- `S_n` 不能一致嵌入更大模式数。

## 候选二：实 tensor-square 半群

### 已证明的矩阵恒等式

取任意实可逆矩阵 `X`，定义

```text
B = X tensor X.
```

任意历史严格保持同型：

```text
(X_L tensor X_L) ... (X_1 tensor X_1)
  = X_tot tensor X_tot.
```

若 `lambda_i` 是 `X_tot` 的本征值，则

```text
det(I + X_tot tensor X_tot)
  = product_i (1 + lambda_i^2)
    [product_(i<j) (1 + lambda_i lambda_j)]^2
  >= 0.
```

实本征值给出正因子，非实本征值按共轭对组成绝对值平方。因此这是任意维数和
任意深度的严格 determinant 正性机制，不是随机幸存者。

`m=2` 时可写成显式平方和。令 `tau=Tr(X)`、`delta=det(X)`：

```text
det(I + X tensor X)
  = (1+delta)^2 [(1-delta)^2 + tau^2].
```

### 物理接口和已知边界

一体生成元为

```text
A = H tensor I + I tensor H.
```

最小 `m=2` 已对应四模式正方形；一般情形对应底图的 Cartesian square，允许环、
分支和不对易 Hermitian 时间片。对角 HS 场必须保持 `v_i+v_j` 的绑定结构。

任意独立 onsite 场不会保持该半群。已有精确边界例：

```text
X1 = [[2,-3],[-3,7]]
X2 = [[4,4],[4,5]]
Z  = diag(16,1,1/8,1/16)

det[I + (X1 tensor X1) Z (X2 tensor X2)] = -155085/32.
```

所以下一步不是继续验证恒等式，而是判断绑定场能否来自局域、非平凡、正系数的
HS 分解。若只能产生沿整行/整列的非局域相互作用，该候选降级为严格矩阵类，
不升级为新物理类。

还必须排查它是否已被某个 Majorana/contraction 条件覆盖。Kronecker 本征值公式
本身是标准表示论，首创性只能来自新的 QMC 子类及其物理实现。

## 候选三：局域 gauge 投影与 overlap 2-cocycle

### 核心想法

普通费米局域移动在 occupation basis 中是带符号的部分置换：

```text
M_s |nu> = sign(s,nu) |s nu>.
```

负号取决于两个移动如何重叠和交换。引入边或面上的局域 gauge qubit，寻找局域
相位规则，使 gauge 历史产生同样的负号并逐构型抵消。等价地，把费米交换
2-cocycle 变成扩展 Hilbert 空间中的局域 coboundary。

另一种等价入口是在 Gauss 约束后的物理子空间寻找正锥：

```text
P = product_v (1+G_v)/2,
G_v = (-1)^(n_v) product_(e incident v) X_e.
```

这里两个重叠块天然共享同一条 link/plaquette 变量，不允许各自选择漂亮基底。

### 最小实验

1. 四模式方环加四条 link qubit；
2. 把局域补偿条件写成 `GF(2)` 线性方程/XOR-SAT；
3. 检查同一跳跃两次、不相交交换、三步 braid、最小 plaquette；
4. 扩到两个共享边的六模式方环；
5. 精确枚举闭合 words 到深度 8，并要求 bridge hopping 非零。

快速停止条件：

- 四模式方环已经无局域解；
- 六模式共边要求所有 bridge 为零；
- 补偿需要随系统长度增长的 Wilson string；
- projected trace 出现精确负权；
- 只是已知高维 bosonization、第二共轭 flavor、Majorana 或普通
  stoquastic 编码。

使用 gauge/ancilla 本身不是新结果。可认领的新内容只能是新的 projected cone、
非平凡 overlap cocycle 恒等式，或逐构型正且可由 HS 到达的子类。

## 候选四：正乘法表与正字符

这是用于检验“重叠闭包优先”原则的低成本基准。

若有限代数有基 `b_i`，满足

```text
b_i b_j = sum_k N_ij^k b_k,  N_ij^k >= 0,
Tr(b_i) >= 0,
```

则任意正系数局域元素的任意乘积都有非负迹。进一步要求一族代数 `A_n` 具有正的
局域嵌入，重叠闭包就成为定义的一部分。

一个具体实例是不平衡 graded permutation。局域空间有 `p` 个偶态和 `q` 个奇态，
`p>=q`；最终置换 `pi` 的迹为

```text
Tr rho_(p|q)(pi)
  = product_(cycles C) [p + (-1)^(|C|-1) q] >= 0.
```

这已经给出任意图和任意深度的正字符定理。首测使用 `p|q=3|2`，避免 `p=q`
退化为常见平方/零权。但它很可能属于已知 `su(p|q)` spin-chain/loop/SSE
表述，而且尚不是 Gaussian determinant 类，因此目前只作基准，不列为主攻。

## 已停止的宽泛方向

一般 P/P0/EP 条件不能替代乘法半群。精确二阶例子：

```text
A = [[1,-5],[0,1]]
B = [[1,-4],[5,1]]
```

`A`、`B` 都是 P 矩阵，但

```text
det(I+AB) = -1.
```

因此不再大规模搜索“每个单片的主子式看起来都正”的宽类。非诱导
exterior-Metzler 仍保留为备线，但必须直接从六模式重叠块开始，并把非零 bridge
写成硬约束。

## 执行优先级

```text
1. 六模式 Fock–CP 固定变换枚举 + Choi SDP
2. tensor-square 的局域 HS 可达性与已知类排重
3. 四/六模式 gauge-cocycle GF(2) 可行性
4. graded positive-character 文献排重
5. non-induced complementary exterior cone
```

前三项均为小矩阵、SDP 或有限域线性方程，预计单次本地实验远低于 10 分钟，
当前不需要超算。
