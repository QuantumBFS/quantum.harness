# 无符号 QMC 挑战项目完整总结

更新时间：2026-07-29  
科研结果基线提交：`26b0d98`  
当前分支：`work/xianzhi/bottom-up-positive-cones`

## 这份文档解决什么问题

这是项目目前唯一一份**自包含总报告**。读完本文，不需要再打开其他专题文档，也应该能
回答：

1. 我们到底在寻找什么；
2. 尝试过哪些矩阵结构；
3. 哪些结构被证明恒正，哪些被反例排除；
4. 恒正矩阵如何变成 Hamiltonian 或辅助场算法；
5. 构造过哪些物理或非常规模型；
6. 哪些后来发现属于已知理论；
7. 当前真正还剩什么值得继续。

专题文档和代码链接只用于复核，不承担补全本文核心结论的任务。

## 一分钟结论

我们要寻找一类辅助场时间片，使每个蒙卡构型的费米权重

```text
w = det(I + B_L ... B_1)
```

始终非负，并且最好能由一个有意义的相互作用 Hamiltonian 产生。

截至现在：

- 累计检查了 `4,044,000` 个 determinant 主权重；
- 另检查了 640 条 Majorana 历史，每条分别计算 even、odd 和完整 Fock 迹；
- 建立了 59 个 determinant 结构生成器和 19 组机器可读精确证书；
- 保存了精确符号反例、80 位高精度重放和一般解析证明；
- 完整自动回归为 `358 passed`；
- 得到三套直接 determinant 恒正构造族：
  TN 路径、odd monomial/block-TN、tensor-square；
- 得到一套额外的 graded 符号补偿机制；
- 得到一个把已知正半群批量变成 Hermitian 相互作用模型的通用工厂；
- 完成五组早期局域 Hamiltonian 映射和八种后续非常规模型试制品；两批有重叠，
  **不能简单相加成十三个独立模型**；
- 所有已完成物理映射目前都属于已知模型、已知正性类、静态扇区直和或基底/投影变换；
- 因此**确认的新无符号物理类数量仍为零**；
- 当前唯一保留的模型主候选是一般 `m>=3` 的 tensor-square 多通道 Hamiltonian。

一句最诚实的话是：

> 我们还没有交付一个新的无符号物理模型，但已经建立了可靠的搜索、反例、证明和
> Hamiltonian 反推体系，并把大量貌似有希望的方向缩成了一个明确的主候选。

## 1. “找到新东西”其实有三关

项目早期最容易混淆的是：矩阵恒正、辅助场算法和新物理模型不是同一件事。

### 第一关：矩阵条件

找到一个对乘法封闭的矩阵集合 `C`，并证明

```text
B_1,...,B_L in C
=> det(I+B_L...B_1) >= 0
```

对任意深度成立。随机抽样零失败不算证明。

### 第二关：Hamiltonian/HS 映射

必须展示某个物理或 transfer 模型经过 Hubbard–Stratonovich 分解后，每个时间片确实
落入 `C`。不能先找一个漂亮矩阵，再假定总能对应一个有意义的模型。

### 第三关：新颖性

还要排除：

- 只是偶 flavor 平方；
- 只是 Kramers、Majorana 或 split-orthogonal 已知条件；
- 只是 Jordan–Wigner 后的 stoquastic 模型；
- 只是已知 Hamiltonian 的新 HS 写法；
- 只是任意换基、相似变换或静态扇区直和。

本文使用三层模型状态：

| 层级 | 含义 |
|---|---|
| L1 | 模型或 transfer 完整，任意历史严格非负 |
| L2 | 又找到精确相似变换、投影、对偶或已知类约化 |
| L3 | 具备独立物理内容、算法用途、可控热力学极限和未被已知类覆盖的证据 |

只有 L3 才计作“新的无符号物理类”。当前 L3 为零。

## 2. 项目实际完成量

### 2.1 数值扫描

| 扫描批次 | 权重数 | 研究对象 | 最终产出 |
|---|---:|---|---|
| classical groups | 900,000 | 经典群与李代数时间片 | 多个精确负权/复权；零失败项均归入已知机制 |
| Hermitian AZ tenfold | 720,000 | 标准 `4 x 4` AZ 十类 | 六类失败，四类归入 split/Kramers |
| Majorana rotated cones | 448,000 | 共享 `J1`、旋转 `J2` 双锥 | 共同实结构只保实权，不保正权 |
| Majorana small-angle stress | 252,000 | 很小夹角的双锥 | 解析证明任意非零夹角都有反例 |
| frontier semigroups | 720,000 | 路径、环、星、稠密图、分块锥等 15 族 | TN 路径幸存；朴素图推广失败 |
| mixed split stress | 672,000 | 两个旋转 split cones | 得到任意夹角两层解析反例 |
| AZ survivor cones | 140,000 | BDI/AII/DIII/CII 的七个自然半群锥 | 非平凡放松失败；幸存者仍是已知对称 |
| speculative structures | 192,000 | 12 个离散路由、范数、reciprocal、可交换候选 | odd monomial/block-TN 定理；四类失败；其余已知约化 |
| **合计** | **4,044,000** | determinant 主权重 | 扫描只负责淘汰，最终结论由证明或精确证书闭合 |

另有 640 条 Majorana 宇称分辨历史。它们不是普通 determinant 样本，因此不并入上表。

### 2.2 计算资源结论

139.2 万个 frontier 权重在本机累计约 15 单核分钟。当前瓶颈是候选定义、已知类排重和
解析构造，不是算力。只有候选扩展到上万独立结构格、`10^8–10^9` 样本、百维以上矩阵
或大量任意精度异常时，国家超算才成为主力。

## 3. 全部主要研究路线及最终状态

| 方向 | 我们实际做了什么 | 最终状态 |
|---|---|---|
| 经典群 `SL/Sp/SO/SU/U/USp` | 系统随机扫描、精确符号证书、高精度重放 | `SL(2/3,R)`、`Sp(2/4,R)`、`SU(1,1)`、`SU(2,1)`、`SU(3)` 等普遍恒正命题失败；`O(p,q)` 恒等分支、`SU(2)`、`USp` 幸存项属于已知机制 |
| `U(p,q)` 相位 | 解析推导权重相位 | `arg det(I+D)=arg det(D)/2 mod pi`；中心相位和剩余 `Z2` 符号都不能自动消掉，关闭为新单 flavor 类 |
| AZ 十重分类 | 标准 Hermitian `4 x 4` 时间片扫描及精确三因子证书 | A/D/C 出现复权；AI/AIII/CI 出现负权；BDI 是 split，AII/DIII/CII 是 Kramers。普通 AZ 表没有新类 |
| AZ 幸存类半群锥 | BDI/AII/DIII/CII 七个数守恒放松锥 | BDI 两面锥和 DIII/CII 非平凡放松失败；三个幸存者严格保留已知 split/Kramers |
| 旋转 Majorana 双锥 | 直接计算 Spin/Fock 迹，不用 determinant 平方掩盖符号 | 任意非零夹角都有两层负权，完整双锥并集关闭 |
| 两个旋转 split cones | 广扫、边界压力和解析构造 | 任意非平凡主夹角都有负 determinant，关闭 |
| 路径/环/星/稠密 Metzler | 15 族半群扫描和高精度重放 | 只有开放路径 TN 机制严格幸存；环、星、稠密图失败 |
| 每片改变路径 gauge | 每片独立换符号规范 | 48,000 样本中 6,965 个负权，关闭 |
| 分块 split 耦合 | upper-block 与双向 block 对照 | 单向三角因子化安全；任意双向反馈失败 |
| TN 路径物理映射 | Hubbard、`t-V`、精确非对称键门、图论边界 | 矩阵机制严格且超出已排查的固定对称条件；当前物理仍是一维已知模型 |
| ordinary TN 的环/分支推广 | 连续生成元、Fock 正和、分扇区符号规范三层 no-go | 普通数守恒 hopping 图只有开放路径可行，关闭直接推广 |
| odd monomial | 奇数阶正 monomial 的循环分解 | 任意深度严格正，但底层循环公式是已知矩阵事实 |
| odd block-TN | 把正标量换成 TN 块 | 固定全局 partition 严格正；自然局域 crossed-partition 两层精确权重 `-2`，物理推广关闭 |
| graded monomial | 用置换 grade 抵消 determinant parity | 严格正且有局域 Hamiltonian；后来归入已知 Majorana reflection positivity |
| fixed `l_infinity` 收缩 | 允许稠密带符号生成元 | 严格正，但就是公共收缩范数机制 |
| moving contraction metric | 每片各自有收缩 metric | 4,542 个负权，关闭 |
| reciprocal parabolic | `[[H,Q],[0,-H^T]]` 三角结构 | 严格正，但来自已知 reciprocal/三角因子化 |
| reciprocal bicoupled | 打开 lower-block feedback | 3,894 个负权，关闭 |
| commuting dense algebra | 所有时间片在同一可交换代数 | 严格正但属于可积对照 |
| near-commuting union | 不同但相近的可交换代数混用 | 846 个负权，关闭 |
| `D_4` Lusztig/Chevalley 正锥 | 正/带符号根方向 | 归入已知 split `SO(4,4)` |
| R01 fixed Klein–Hodge | 六模式重叠数守恒/BdG bridge | 24 个 bridge 坐标全部 exact-zero；只关闭该固定变换 |
| Fock–CP/Choi | 13 个 depth-2 Klein 电路、20 种切分、两族共 520 单元 | bridge 在线性 Hermiticity-preserving 条件就归零；关闭有限 Klein 库，一般 non-Klein 仍开放 |
| tensor-square | 任意实 `X` 的 `X tensor X` 表示提升 | 任意深度严格正；`m=2` 属 split；`m=3` 不存在固定伪正交度量，物理排重仍开放 |
| gauge/cocycle | `Z2` Gauss law、Wilson 补偿串、GF(2) 精确消号 | 四/六模式成功；`2 x L` 上补偿串长度随系统增长，简单局域 ansatz 关闭 |
| pseudo-Hermitian Stark | 单向 Stark 链、显式 metric 和 Hermitian partner | 变换正确，但 partner 不唯一；只作方法校准 |
| star-to-chain | Lanczos/Krylov 把稠密 bath 变成链 | 精确且有用，但属于标准 chain mapping |
| adjoint lift | `X tensor X^(-T)`、cosh gate、swap metric | 整个族在已知 `O(p,q)` 恒等分支，padding 后为 split 类；关闭为新机制 |
| grade-charge full trace | 守恒 ancilla、局部三模式 vertex、full trace | 完整 Hamiltonian 是静态 ancilla-bit 扇区直和；降级为方法工具 |
| 非诱导 exterior cone | 合作者独立分支负责 exact-card/pressure 扫描 | 本分支不重复；等待通过证书门的候选 |
| 复 Majorana/Pfaffian 完整矩阵定理 | 已有直接 Spin/Fock 迹 oracle 和部分规范表示 | 主办方要求的完整简洁定理尚未完成 |

## 4. 三套 determinant 恒正构造

这里的“构造”表示我们有任意维数或任意历史深度的证明，不表示文献史首创。

### 4.1 TN 路径半群

每个实生成元取三对角 Metzler 形式：

```text
A_l =
[ *  +  0  0 ]
[ +  *  +  0 ]
[ 0  +  *  + ]
[ 0  0  +  * ].
```

上下相邻元可不对称，但都非负；对角任意。于是

```text
B_l = exp(A_l)
```

是全非负矩阵，即所有子式都非负。全非负矩阵对乘法封闭，所以

```text
D = B_L...B_1
```

仍全非负。最后

```text
det(I+D) = sum_S det D[S,S] >= 1.                 (TN)
```

这给出单个行列式的严格正性，不依赖双 flavor 平方。项目又证明整个 TN 类不能被一个
固定 Kramers、split metric、实收缩 metric 或当前使用的 Majorana contraction 条件
整体覆盖。

但是 TN 数学本身是经典全非负矩阵理论；目前不能主张文献史上的新矩阵定理。

### 4.2 Odd positive-monomial 与 block-TN

取

```text
B = P diag(d_1,...,d_n),    d_i>0,
```

并限制 `P` 来自奇数阶置换群。每个最终置换循环 `C` 的长度都是奇数，因此

```text
det(I+B) = product_C [1 + product_(i in C) d_i] > 0.   (OM)
```

它对任意乘积深度成立，并允许普通 TN 之外的离散路由。

block-TN 推广把每个 `d_i` 换成可逆 TN 块 `X_i`。一个奇循环贡献

```text
det(I + X_ell...X_1) >= 0.
```

固定全局 block partition 的数学结论严格成立。问题出在物理局域化：当每个格点独立
选择 `C3` route，再加入跨格点 hopping 时，不同时间片使用了交叉 partition。两个各自
合法的时间片已经给出

```text
det(I+XR) = -2.
```

因此自然局域模型路线被精确关闭。

### 4.3 Tensor-square

令每个时间片为

```text
B_l = X_l tensor X_l,    X_l real.
```

乘法闭包给出总历史

```text
B_L...B_1 = X tensor X,
X = X_L...X_1.
```

最新得到的完整分解是

```text
det(I + X tensor X)
 = det(I+X^2) det(I+Lambda^2 X)^2
 = |det(I+iX)|^2 det(I+Lambda^2 X)^2 >= 0.        (TS)
```

因此 tensor-square determinant 正性最终是复模平方乘实平方，不是不可再拆的新代数
机制。

但这个分解只作用于完整历史 `X`，不会自动给出逐时间片的普通双 flavor 模型。
`m=2` 底空间确实保存 split `O(2,2)` metric；对 `m=3`，我们精确求解所有 traceless
生成元在九维 product space 上的固定双线性型条件。81 个未知量的约束矩阵秩为 81，
所以不存在任何非零固定伪正交 metric。

这只排除了最简单的固定 `O(p,q)` 解释，尚未排除更一般 Majorana、Pfaffian 或
contraction-semigroup 表示。因此 tensor-square 的矩阵正性不再主张新颖，但其
`m>=3` 多通道 Hamiltonian 仍是当前唯一模型主候选。

## 5. 一套 graded 正权机制

允许正 monomial 矩阵包含 transposition：

```text
B = P diag(d_1,...,d_n),    d_i>=1,
chi(B)=sgn(P).
```

则

```text
chi(B) det(I+B) >= 0.                              (G)
```

物理连续时间展开每插入一个 crossing vertex 也带一个负号，两个符号逐历史抵消，而
不是事后取绝对值。

边 `e=(i,j)` 上的单粒子矩阵为

```text
B_e(r) = I outside (i,j) direct-sum r[[0,1],[1,0]],    r>1.
```

其 Fock lift 是

```text
Gamma(B_e)
 = 1-n_i-n_j +(1-r^2)n_i n_j
   +r(c_i^dag c_j+c_j^dag c_i).
```

取

```text
H = sum_e q_e Gamma(B_e),    q_e>0,
```

便得到任意图、任意 Taylor 阶数逐历史非负的局域 Hermitian 相互作用模型。

然而 centered 后的一体 kernel 逐边负半定，密度相互作用为吸引，因此整个模型严格落入
2016 Majorana reflection positivity。`r=1` 顶点又是已知 `su(1|1)` graded
permutation。它是有用的特殊连续时间展开，不是新物理类。

## 6. 通用 Hermitian 模型工厂

这是后期非常规模型工作的核心基础设施，但不是新的 determinant 定理。

假设一个实矩阵集合 `C` 满足：

```text
B,C in C => BC in C,
B in C   => B^T in C,
D in C   => det(I+D)>=0.
```

选择有限多个 atoms `B_a in C` 和正系数 `q_a`，在数守恒 Fock 空间定义

```text
H_C = -sum_a q_a [Gamma(B_a)+Gamma(B_a)^dagger].  (F)
```

因为 `Gamma(B)^dagger=Gamma(B^T)`，`H_C` 严格 Hermitian。Taylor 展开中的任意
oriented word 都满足

```text
Tr Gamma(C_1...C_L)
 = det(I+C_1...C_L) >= 0.
```

因此工厂能把任意已证明的乘法、转置封闭正半群变成逐 word 无符号的 Hermitian
相互作用模型。`Gamma(B)` 的 minor 展开可产生长程和任意体数作用。

工厂的价值是系统生成模型；模型是否新颖仍需单独排重。

## 7. Hamiltonian 和模型构造总表

下面把早期五组局域映射与后期八种试制品放在同一张表中。带“扩展”者与前面模型有重叠，
因此不做简单数量相加。

| 模型/顶点 | 核心构造 | 得到了什么 | 最终归属 |
|---|---|---|---|
| 开放 Hubbard 链 | 开放路径动能 + Hirsch 对角 HS | 任意化学势下两个自旋 determinant 各自 TN 正 | 已知一维无符号基线 |
| 单 flavor 排斥 `t-V` 开链 | 路径动能 + 键密度 HS | 单个 determinant 逐构型严格正 | 已知 Jordan–Wigner 一维模型 |
| 非对称 `t-V` 精确键门 | `exp(-dt h_b)=[Gamma(B_+)+Gamma(B_-)]/2`，`B_+/-` 为非对称 TN | 真实物理键门的精确正系数辅助场分解；重叠键无共同 Hermitian metric | 算法表达有价值，Hamiltonian 已知 |
| 三站点 parity-string hopping | TN inverse-HS 顶点 | 局域 density-assisted/宇称串 hopping | Jordan–Wigner 后为 stoquastic XY/hard-core boson |
| graded-monomial 奇环 | `H=sum_e q_e Gamma(B_e)` | 奇环上不能用简单站点 gauge 变成 stoquastic，但任意 history 正 | 已知 Majorana reflection-positive 类 |
| tensor-square 四模式 plaquette | `B_s=X_s tensor X_s` 的两值正 HS | 方形 hopping 加一对对角模式排斥 | `m=2` 属 split `O(2,2)` |
| tensor-square 连续模型（扩展） | `H=K-(1/2)sum_a g_a Q_a^2` | 集体密度、同步 bond、correlated pair hopping；多通道可不对易 | L1；`m>=3` 是当前唯一主候选 |
| tensor-square 正 transfer（扩展） | `T=T_K^(1/2)cosh(Q)T_K^(1/2)`，`H_eff=-log(T)/dt` | 精确 all-body 有效 Hamiltonian；`m=3` 最多可出现九体项 | L1；正性机制与上一项相同 |
| odd block-TN 工厂模型（扩展） | `H=-sum q_a[Gamma(B_a)+h.c.]`，固定 partition | 同步三腿 synthetic ladder、六体 density 项 | 固定全局模型 L1；自然局域化有 `-2` 反例 |
| adjoint lift | `B(X)=X tensor X^(-T)`，两场 cosh gate | difference-coordinate 相互作用模型接口 | 整体属于已知 `O(p,q)`/split 类 |
| grade-charge full trace（扩展） | 给 crossing group 加守恒费米 ancilla | 可用 ancilla 数量换取局部三模式 vertex | 静态扇区直和；不是新 ancilla 动力学 |
| Wilson-string fermion-gauge | Gauss 投影、fermion hopping 携带 `Z2` Wilson compensator | 四/六模式逐 vertex 非负，可加 plaquette dynamics | 精确映到局域 stoquastic constrained link-spin；L1+L2 |
| 单向 Stark pseudo-Hermitian 链 | `h_NH=R_g^(-1) D R_g`，`eta=R_g^dagger R_g` | 局域非厄米链和对角/长程 Hermitian partners | partner 不唯一，只作 L2 校准 |
| star-to-chain TN bath | 以 impurity 为首 Krylov vector 的正交 Lanczos | 稠密长程 bath 变成 endpoint-interacting 链 | 标准 Wilson/Lanczos mapping；L2 校准 |

### 为什么 Stark 的长程 partner 不算发现

若

```text
H_NH = S^(-1) D S
```

且 `D` 是对角 Hermitian 矩阵，那么任取 unitary `U`，

```text
h_U = U D U^dagger,
S_U = U S
```

都满足

```text
H_NH = S_U^(-1) h_U S_U.
```

`U=I` 给最简单的对角 partner；Fourier 或稠密 `U` 给长程 partner。长程外观可能只是
基底选择。只有物理格点、可观测量、允许的变换、相似变换局域性和条件数都受到控制时，
partner 才可能具有独立物理意义。

### 为什么 grade-charge 不是动态新模型

每个 ancilla 占据数都与 Hamiltonian 对易，所以

```text
H_full = direct_sum_z H_z.
```

ancilla 只是静态 bit。full trace 对这些扇区求和可以恢复正权，但没有产生会传播或纠缠的
新自由度。除非以后加入仍保持正性的 ancilla 跃迁，否则它只作为方法工具。

### 为什么 adjoint lift 已经关闭

对

```text
B(X)=X tensor X^(-T),    det X>0,
```

交换两个 tensor 因子的 swap metric `K` 满足

```text
B(X)^T K B(X)=K.
```

其 signature 是

```text
p=m(m+1)/2,    q=m(m-1)/2.
```

`GL^+(m,R)` 连通，lift 连续且把单位元送到单位元，因此整个族位于固定 `O(p,q)` 的
恒等连通分支。给较小 signature 补 `m` 个平凡单位方向后就是 split `O(p,p)`，权重只
多一个正因子 `2^m`。所以它不是新的正性机制。

## 8. 最重要的精确失败结果

随机扫描只负责找到嫌疑点。以下公式或精确证书才是真正关闭方向的依据：

| 被关闭的想法 | 最小证据 | 含义 |
|---|---|---|
| 旋转 Majorana 双锥的小角安全区 | `p(theta,q)=-4 sin(theta)sinh(q)^2<0` | 任意 `0<theta<pi` 都有两层负 Spin/Fock 迹 |
| 两个旋转 split cones 的并集 | `w=16[1-q^2 sin^2(theta)]` | 任意非平凡主夹角取足够大 `q` 都负 |
| BDI 两面 contraction/expansion | `w=16(1-q^2)` | 同一 split 结构的双向放松也不安全 |
| odd block-TN 自然局域拼接 | `det(I+XR)=-2` | 每片合法不代表 crossed partition 的乘积合法 |
| 偶阶 monomial 路由 | `det(I+P Delta)=(1-q^2)(1-q^-2)`；`q=2` 时 `-9/4` | 关键是奇循环，不是 monomial 本身 |
| 普通环/分支 TN hopping | Fock 矩阵元的 Jordan–Wigner 占据依赖反号 | TN Gaussian 正和也无法产生普通远邻 hopping |
| 每粒子数扇区独立符号 gauge | 2–6 站点全连通图穷举只有 `N!/2` 条标号路径 | 环和三支星形有不可消除的交换负闭环 |
| edge-electric gauge 局域扩展 | `2 x L` 中央 hop 必须读取其余全部 `L-1` 条竖边 | 简单消号严格产生 system-size Wilson string |

这些失败不是“白做”：它们把搜索空间从模糊猜想缩成了明确禁区，避免团队和后续 agent
重复投入。

## 9. Majorana 问题为什么仍没有完全结束

对复反对称 Majorana 时间片，真正物理权重可能是 Spin trace

```text
p = Tr_Spin product_l exp(gamma^T A_l gamma/4),
```

而 determinant 只满足

```text
p^2 = det(I+D).
```

determinant 看不到平方根分支的正负。因此普通 determinant 零负例不能证明
Majorana positivity。

目前已经完成：

- 直接 Fock/Spin 迹 oracle；
- 固定 `J1,J2` 规范下的双锥反例；
- determinant 平方交叉检查；
- 640 条宇称分辨历史的 period-4 数值规律。

尚未完成：

- 2016 复 Majorana 条件的完整简洁纯矩阵定理；
- pairing/BdG/Pfaffian 半群的系统分类；
- 宇称分辨猜想的任意深度证明或精确反例；
- 与实际 pairing Hamiltonian 的双向 HS 映射。

所以不能说“Majorana 类已经全部检查完”。

## 10. 当前仍开放的方向

按优先级和责任边界整理如下：

### 主线：`m>=3` tensor-square 多通道 Hamiltonian

已经有：

- 任意深度 determinant 证明；
- 完整 Hermitian Hamiltonian；
- 多个不对易 HS channel；
- Kac scaling；
- Fock 与精确 `-log` MWE；
- `m=3` 不存在固定伪正交 metric 的精确 no-go。

还缺：

1. 逐时间片 Majorana/Pfaffian/contraction-semigroup 排重；
2. 选择一个最小三通道模型，解释其相互作用和守恒量；
3. 判断它是否只是已知模型的换基或 flavor 重组；
4. 若幸存，实现 vertex-word 采样和可观测量。

### 支线：复 Majorana/Pfaffian 工具

只做到足以可靠审计 tensor-square 和合作者候选，不把重写全部已知理论无限扩张为主任务。

### 协作线：non-induced exterior cone

由合作者分支负责 exact-card/pressure 扫描。本分支只复核通过证书门的候选，避免重复。

### 低优先级开放项

- 一般 non-Klein、非高斯 entangling circuit 的 Fock–CP/Choi 锥；
- 真正带动态 ancilla 且仍保持正权的 grade-charge 扩展；
- modified-Gauss projected cone，前提是先写出逐构型正 transfer matrix；
- Majorana 宇称 period-4 猜想。

## 11. 已提出但不能当作完成结果的方向

早期候选卡还提出过 spinor/Fock Metzler、pairwise-overlap Majorana cone nerve、
positive character、物理受限锥交集等想法。它们没有全部进入正式实现或一般证明。

保留这些候选卡是为了记录思路，不代表：

- 已经扫描；
- 已经证明；
- 已经得到 Hamiltonian；
- 或已经完成主办方要求。

本文把“提出”“实现”“扫描”“证明”“物理映射”严格分开。

## 12. 当前最准确的成果口径

### 可以说

- 我们建立了可复现的 determinant 与 Majorana Spin/Fock 权重 oracle；
- 完成了 404.4 万主权重的结构化筛选和大量精确闭合；
- 得到 TN、odd monomial/block-TN、tensor-square 三套严格 determinant 构造族；
- 得到一套 graded 逐历史符号抵消机制；
- 得到通用 Hermitian semigroup model factory；
- 构造并验证了多组局域、长程、多体、ancilla、gauge 和 pseudo-Hermitian 模型；
- 已经知道这些模型为什么正，以及多数为什么不够新；
- 当前 tensor-square `m>=3` 多通道模型值得继续深挖。

### 不能说

- 已经发现新的无符号物理类；
- tensor-square 是不可约的新行列式正性机制；
- grade-charge 产生了新的动态 ancilla 相；
- 找到一个长程 Hermitian partner 就发现了长程物理；
- 主办方要求的完整复 Majorana/Pfaffian 问题已经解决；
- 404.4 万随机样本穷尽了所有候选。

### 给合作者的一句话

> 我们已经把经典群、AZ、旋转 Majorana/split 双锥、朴素图半群和多批激进候选做了
> 系统筛选与精确闭合；得到三套严格 determinant 构造、一套 graded 正权机制和一个
> 通用 Hermitian 模型工厂，但所有已完成物理映射目前仍可归入已知类或精确约化。
> 最新排查后只保留 `m>=3` tensor-square 多通道 Hamiltonian 为主候选，确认的新
> 无符号物理类仍为零。

## 13. 复现与证据在哪里

### 核心代码

- `oracle/`：矩阵生成器、determinant、Majorana trace、模型和精确审计；
- `tests/`：解析恒等式、精确反例和 Hamiltonian 映射回归；
- `fixtures/`：机器可读精确证书；
- `protocols/`：扫描参数、种子和可恢复运行协议；
- `tracks/qmc/results/no-negative-vibes/`：不提交 Git 的大体积逐格结果。

### 当前质量状态

```text
python -m pytest -q
358 passed
```

最新三个候选额外有：

- tensor-square 模平方/外幂平方精确整数锚点；
- `m=3` 固定伪正交 metric 的 81 阶满秩 no-go；
- grade-charge 三种布局的完整 Fock 直和重构；
- adjoint lift 在 `m=2,3,4` 的 metric、signature、determinant 和 padding 证书。

### 专题复核入口

本文已经包含全部核心结论；若要查看推导细节，可进入：

- [全非负路径半群](TOTAL_NONNEGATIVE_PATH_CLASS.md)
- [TN 物理映射边界](TN_PHYSICAL_MAPPING_FRONTIER.md)
- [激进结构首批结果](SPECULATIVE_STRUCTURE_RESULTS.md)
- [Graded monomial 结果](GRADED_MONOMIAL_RESULTS.md)
- [Tensor-square 结果](TENSOR_SQUARE_RESULTS.md)
- [八种非常规模型](UNCONVENTIONAL_MODEL_BATCH1_RESULTS.md)
- [最新三个候选审计](THREE_CANDIDATE_AUDIT_RESULTS.md)
- [主办方方向完成度](ORGANIZER_DIRECTION_AUDIT.md)
- [精确证书](EXACT_CERTIFICATES.md)

历史计划和候选卡只作为审计记录。若它们与本文冲突，以本文、机器可读证书和当前测试为准。
