# U2/U5 非常规模型卡：Wilson-string gauge 与 grade-charge ancilla

日期：2026-07-29
状态：理论构造笔记；不修改成果总账，不主张新的正性机制。

这两张卡把已经严格成立的两个代数结果写成完整、可执行的模型：

1. `U2`：edge-electric gauge cocycle 变成带 Wilson string 的 Hermitian
   fermion-gauge Hamiltonian；
2. `U5`：graded monomial 的单一全局 grade mode 推广成可分组的守恒
   grade-charge ancilla family。

第一张模型任意深度无符号，但投影后精确约化为 stoquastic link-spin model。
第二张模型任意深度无符号，但正性来源仍是已经完成排重的 graded monomial
cycle factor；全占据 ancilla sector 精确回到已知 Majorana-reflection-positive
模型。二者目前都只按 `L1/L2` 非常规模型记录，不计作新物理类。

---

## 模型卡 U2-W：Gauss 投影的 Wilson-string fermion-gauge model

### U2-W.1 图、Hilbert 空间和 Gauss sector

取任意有限无向图

```text
G = (V,E)
```

并固定一个 fermion mode ordering。每个顶点 `v` 放一个 spinless fermion
`c_v`，每条边 `e` 放一个 `Z2` link qubit。link 的 `Z` 基写成

```text
Z_e |a_e> = (-1)^(a_e) |a_e>,   a_e in {0,1}.
```

未约束 Hilbert 空间是

```text
H_ext = Fock(C^|V|) tensor (C^2)^(tensor |E|).
```

选定背景 charge `q_v in {0,1}`，定义

```text
G_v = (-1)^(q_v+n_v) product_(e incident v) Z_e,
P_q = product_v (1+G_v)/2.
```

物理 Hilbert 空间为

```text
H_q = P_q H_ext.
```

在 occupation/link basis 中，`G_v=+1` 等价于

```text
n_v = q_v + sum_(e incident v) a_e mod 2.             (U2.1)
```

因此一个物理 basis state 由全部 link bits `a=(a_e)` 唯一决定：

```text
|a>_q := |n(a)>_F tensor |a>_Z.
```

物理空间维数是 `2^|E|`。所有物理态具有由 `q` 固定的总 fermion parity。

### U2-W.2 精确 Wilson compensator

对边 `e=(i,j)`，令 `i<j`，并定义 ordering interval

```text
S_e = {v : i < v < j}.
```

标准 Fock basis 中，一次合法 hopping 的 fermion matrix-element sign 是

```text
s_F(e,n) = (-1)^[sum_(v in S_e) n_v].                (U2.2)
```

令 `partial S_e` 表示恰有一个端点落在 `S_e` 内的 hopping edges。把
Gauss law (U2.1) 代入 (U2.2)，得到精确恒等式

```text
sum_(v in S_e) n_v
 = sum_(v in S_e) q_v
   + sum_(f in partial S_e) a_f mod 2.                (U2.3)
```

因此定义 diagonal Wilson operator

```text
W_e
 = (-1)^[sum_(v in S_e)q_v]
   product_(f in partial S_e) Z_f.                    (U2.4)
```

在合法 hopping subspace 上，还可把 (U2.4) 乘以一个在该子空间恒为 `+1`
的 endpoint-constraint phase，得到
`oracle.gauge_cocycle.minimum_legal_compensation()` 返回的最小 support 代表。
两种写法乘在 hopping operator 上完全相同。

重要性质：

- `e` 自身不在 `partial S_e`，所以 `[W_e,X_e]=0`；
- hopping 前后 `W_e` 的 eigenvalue 相同；
- `W_e` 的 matrix-element sign 与 fermion hopping sign 完全相同。

### U2-W.3 Hamiltonian

定义 Hermitian gauge-dressed hopping

```text
J_e
 = (c_i^dagger c_j + c_j^dagger c_i) X_e W_e.        (U2.5)
```

对任意 plaquette 或更一般的图 cycle `p`，定义 magnetic flip

```text
M_p = product_(e in boundary p) X_e.                  (U2.6)
```

允许任意实 diagonal potential

```text
V_diag = V({n_v},{Z_e}),
```

例如 chemical potential、density interaction、electric energy 和 diagonal
flux interaction。完整 Hamiltonian 是

```text
H_U2
 = -sum_e t_e J_e
   -sum_p K_p M_p
   +V_diag,                                           (U2.7)

t_e >= 0,  K_p >= 0.
```

`J_e` 和 `M_p` 都与所有 `G_v` 对易，所以 (U2.7) 严格保持 `H_q`。

#### `2 x 2` 方环的显式最小模型

取 row-major ordering `(0,1,2,3)`、`q_v=0` 和 edges

```text
E={(0,1),(0,2),(1,3),(2,3)}.
```

现有 exact minimizer 给出

```text
W_(0,1) = 1,
W_(2,3) = 1,
W_(0,2) = Z_(0,1) Z_(1,3),
W_(1,3) = -Z_(0,1) Z_(0,2).                          (U2.7a)
```

唯一 plaquette vertex 是

```text
M_square = X_(0,1)X_(0,2)X_(1,3)X_(2,3).             (U2.7b)
```

把 (U2.7a)--(U2.7b) 直接代入 (U2.5)--(U2.7)，就是一个无需再求解
GF(2) 方程的 `4` fermion + `4` link-qubit minimal working model。

### U2-W.4 Hermiticity

`J_e` Hermitian，原因是：

1. `c_i^dagger c_j+c_j^dagger c_i` Hermitian；
2. `X_e`、`W_e` Hermitian；
3. matter 与 link operators 对易；
4. `[X_e,W_e]=0`。

`M_p` 和 `V_diag` 也显然 Hermitian。因此 `H_U2=H_U2^dagger`，不需要
pseudo-Hermitian metric。

`J_e` 的 reverse matrix element 使用同一个 `W_e` phase；这正是现有
`reverse_phase_failures=0` 的 operator 版本。

### U2-W.5 transfer vertices 和正 scalar coefficients

在物理 basis `|a>_q` 中，

```text
_q<a'|J_e|a>_q
 = 1,   若 e 上 hopping 合法且 a'=a xor e;
 = 0,   其他情况。                                  (U2.8)
```

fermion sign 与 `W_e` sign 在 (U2.8) 中逐跳相消。类似地，

```text
_q<a'|M_p|a>_q
 = 1,   若 a'=a xor boundary(p);
 = 0,   其他情况。                                  (U2.9)
```

可使用以下 exact local-in-time transfer vertices：

```text
T_e(dt) = exp(dt t_e J_e),
T_p(dt) = exp(dt K_p M_p),
T_D(dt) = exp(-dt V_diag).                            (U2.10)
```

`J_e` 在每个合法二态 block 中是 `sigma_x`，在非法态上为零，所以

```text
exp(x J_e)
 = I-P_e + cosh(x)P_e + sinh(x)J_e.                  (U2.11)
```

这里 `P_e` 是 hopping-legality projector。`cosh(x)`、`sinh(x)` 对
`x>=0` 非负。又因为 `M_p^2=I`，

```text
exp(x M_p) = cosh(x) I + sinh(x) M_p.                (U2.12)
```

所以所有非对角 transfer scalar coefficients 均非负，diagonal transfer
的每个 matrix element 也为正：

```text
t_e, K_p, cosh(dt t_e), sinh(dt t_e),
cosh(dt K_p), sinh(dt K_p) >= 0,
<a|exp(-dt V_diag)|a> > 0.
```

### U2-W.6 QMC weight

连续时间展开把 `V_diag` 当作 diagonal part。一个构型 `C` 包含：

- 初始 link state `a_0`；
- 有序 hopping vertices `e_1,...`；
- 有序 plaquette vertices `p_1,...`；
- 闭合条件 `a(beta)=a_0`。

其权重为

```text
w_U2(C)
 = exp[-integral_0^beta V_diag(a(tau)) d tau]
   product_(hopping vertices l) t_(e_l)
   product_(plaquette vertices m) K_(p_m)             (U2.13)
```

乘以正的有序时间积分 measure。非法历史权重为零。合法闭合历史满足

```text
w_U2(C) >= 0
```

逐构型成立。

若使用离散时间，任意排列的 (U2.10) 乘积都逐元非负，trace 也非负。

### U2-W.7 任意深度证书

任意深度正性不依赖有限枚举，而来自两个逐顶点 operator 恒等式：

```text
fermion hopping sign * W_e sign = +1,
Gauss law is preserved by every J_e and M_p.
```

因此每个 transfer vertex 在同一个物理 basis 中逐元非负；非负矩阵对任意乘法
深度封闭。

现有精确程序已经检查：

```text
2 x 2 ladder: 16 gauge states, 32 legal transitions, 0 failures;
2 x 3 ladder: 128 gauge states, 448 legal transitions, 0 failures;
closed words through depth 8: 0 sign failures.
```

这些枚举是实现回归；一般证明是 (U2.3)。

### U2-W.8 string 与 gauge 尺度

资源数量：

```text
matter modes = |V|,
link qubits  = |E|,
Gauss constraints = |V|.
```

`J_e` 的 fermion hopping 和 `X_e` 是 edge-local，但 `W_e` 一般是 Wilson
string。对 row-major ordering 的 open `2 x L` ladder，中央 rung 的最小
compensator 满足

```text
rung variables in W_e = L-1,
phase support          = L+1,       L>=3,
graph radius           = ceil((L-1)/2).               (U2.14)
```

所以原 fermion-gauge 表示中的 Hamiltonian support 随系统增长。这是允许的
`U2` 非常规性，不应重新描述成短程模型。

### U2-W.9 gauge fixing / 投影约化

定义 basis isometry

```text
U_q : |a> -> |n(a)>_F tensor |a>_Z.
```

令

```text
xi_v(a) = (-1)^(q_v) product_(f incident v) Z_f,
Pi_e = [1-xi_i xi_j]/2.                               (U2.15)
```

`Pi_e` 正是“edge endpoints 恰有一个 fermion”的 projector。直接由
(U2.8) 得

```text
U_q^dagger J_e U_q = X_e Pi_e,
U_q^dagger M_p U_q = product_(f in boundary p)X_f.    (U2.16)
```

因此 gauge-fixed partner 是

```text
H_link
 = -sum_e t_e X_e Pi_e
   -sum_p K_p product_(f in boundary p)X_f
   +V_diag({xi_v},{Z_e}).                              (U2.17)
```

`Pi_e` 只依赖两个 endpoint stars，故 (U2.17) 在 bounded-degree graph 上
是局域 kinetically constrained link-spin Hamiltonian。它在 `Z` basis 中
stoquastic。

这说明 Wilson string 是 fermionic occupation ordering 与 Gauss encoding 的表示
代价；投影后没有产生新的 sign-free mechanism。

`oracle/gauge_cocycle.py::constrained_gauge_hamiltonian` 已直接在
`|a>_q` link-bit 基中构造 (U2.17)，同时保留 fermion sign 与 Wilson sign 的显式
相消。`2 x 2` 回归核对完整 `16 x 16` Hamiltonian、正反跃迁、Hermiticity 和所有
非对角元非正，而不再只检查单步 phase。

### U2-W.10 最快已知类排重和判定

最快排重顺序：

1. 用 (U2.16) 构造 exact code-space matrix；
2. 检查所有 off-diagonal entries of `H_link` 非正；
3. 标记为 stoquastic/worldline 类；
4. 再与 exact bosonization / Jordan--Wigner gauge encoding 对照。

当前判定：

```text
完整 Hermitian model：是
正 scalar coefficients：是
任意深度证书：是
fermion 表示局域：否，含 system-size Wilson string
投影后可执行：是
新正性机制：否，精确约化到 stoquastic link-spin model
层级：L1 + L2
```

它仍有实际用途：这是现有 GF(2) cocycle 解对应的最直接 Hamiltonian，而不是
“存在某个补偿相位”的抽象描述。

---

## 模型卡 U5-G：分组 grade charges 的 Hermitian ancilla model

### U5-G.1 Hilbert 空间与 grade 分组

取任意有限图 `G=(V,E)`，每个顶点放一个 spinless physical fermion。把 edges
分成 `m` 个不交 grade groups：

```text
E = disjoint_union_(g=1)^m E_g,
alpha(e)=g iff e in E_g.
```

每个 group 放一个守恒 ancillary fermion `a_g`。完整 Hilbert 空间是

```text
H_U5 = Fock(C^(|V|+m)).
```

每个 `n_(a_g)` 都将在 Hamiltonian 中守恒。

两个重要极限：

```text
m=1:      一个全局 grade mode，连接所有物理 edges；
m=|E|:    每条 edge 一个 grade mode，每个 vertex 具有三模式局域 support。
```

中间分组给出 ancilla 数量与几何作用范围之间的连续 tradeoff。

### U5-G.2 single-particle fields

对 edge `e=(i,j)` 取 `r_e>1`，定义 physical dilated transposition

```text
B_e
 = identity outside (i,j)
   direct-sum r_e [[0,1],[1,0]].                      (U5.1)
```

在 group ancilla `a_(alpha(e))` 上同时乘 `-r_e`，其他 ancillas 保持
identity：

```text
Btilde_e
 = B_e direct-sum (-r_e)_(a_alpha(e))
   direct-sum I_(other ancillas).                     (U5.2)
```

令 `Gamma` 为 number-conserving Gaussian Fock lift。局域 Fock vertex 是

```text
V_e = Gamma(Btilde_e)
     = Gamma(B_e) [1-(1+r_e)n_(a_alpha(e))].           (U5.3)
```

其中

```text
Gamma(B_e)
 = 1-n_i-n_j +(1-r_e^2)n_i n_j
   +r_e(c_i^dagger c_j+c_j^dagger c_i).               (U5.4)
```

### U5-G.3 Hamiltonian 与正 scalar coefficients

定义

```text
H_U5 = -sum_(e in E) q_e V_e,   q_e>0.                (U5.5)
```

这是一个包含 conditional hopping、density coupling 和
`n_ancilla n_i n_j` 项的完整 interacting Hamiltonian。

连续时间展开为

```text
exp(-beta H_U5)
 = sum_(k>=0) beta^k/k!
   sum_(e_1,...,e_k)
   product_l q_(e_l)
   V_(e_k)...V_(e_1).                                 (U5.6)
```

所有 auxiliary/vertex scalar coefficients

```text
beta^k/k! product_l q_(e_l)
```

严格为正。

### U5-G.4 Hermiticity 与实指数证书

`B_e` 和 `Btilde_e` 都是实对称矩阵，所以

```text
V_e=V_e^dagger,
H_U5=H_U5^dagger.                                     (U5.7)
```

`Btilde_e` 的负 eigenvalue 有两个：

- physical antisymmetric endpoint mode 的 `-r_e`；
- grade ancilla mode 的 `-r_e`。

在 symmetric endpoint mode 上取 generator `log r_e`。在
“antisymmetric endpoint mode + grade ancilla”二维平面上取

```text
A_e = (log r_e) I_2 + pi [[0,-1],[1,0]].              (U5.8)
```

则该平面上 `exp(A_e)=-r_e I_2`。因此每个 `Btilde_e` 都有显式实
generator；这不是把负 determinant matrix 假装成实指数。

### U5-G.5 QMC history weight

对 history

```text
h=(e_1,...,e_k)
```

定义 physical product

```text
D_h = B_(e_k)...B_(e_1).                              (U5.9)
```

对每个 grade group 定义

```text
k_g = number of l with alpha(e_l)=g,
R_g = product_(l: alpha(e_l)=g) r_(e_l),              (U5.10)
```

空乘积取 `R_g=1`。由于 extended product 对 ancillas 是 diagonal，

```text
Tr_Fock[V_(e_k)...V_(e_1)]
 = det(I+D_h)
   product_(g=1)^m [1+(-1)^(k_g)R_g].                 (U5.11)
```

所以逐 history QMC weight 是

```text
w_U5(h)
 = beta^k/k! product_l q_(e_l)
   det(I+D_h)
   product_g [1+(-1)^(k_g)R_g].                       (U5.12)
```

计算成本为一次 physical determinant，加上 `m` 个 scalar factors。

### U5-G.6 任意深度非负证明

`D_h` 是 positive monomial matrix。每个 `B_e` 的 permutation part
是一个 transposition，所以

```text
sgn(permutation of D_h)=(-1)^k.
```

现有 graded cycle-factor theorem 给出

```text
(-1)^k det(I+D_h) >= 0.                               (U5.13)
```

另一方面，`r_e>1` 意味着

```text
sign[1+(-1)^(k_g)R_g] = (-1)^(k_g).                  (U5.14)
```

因此

```text
sign product_g[1+(-1)^(k_g)R_g]
 = (-1)^[sum_g k_g]
 = (-1)^k.                                            (U5.15)
```

(U5.13) 与 (U5.15) 的 signs 精确相消：

```text
w_U5(h) >= 0
```

对任意 graph、任意 edge ordering、任意 overlap 和任意 history depth
成立。

这比有限深度扫描更强；数值只需回归公式实现。

### U5-G.7 ancilla 数量与空间 support

每个 vertex `V_e` 的代数 support 是

```text
{physical i, physical j, grade ancilla alpha(e)}.
```

但几何 locality 取决于分组：

| 分组 | ancilla 数 | 单个 ancilla degree | 几何判定 |
|---|---:|---:|---|
| 全部 edges 同组 | `1` | `O(|E|)` | global star / synthetic dimension |
| 每个 spatial patch 一组 | patch 数 | patch edge 数 | subsystem-local |
| 每条 edge 单独一组 | `|E|` | `1` | 真正三模式 edge-local |

所以该 family 明确展示：

```text
O(1) grade memory + system-size connectivity
<---- tradeoff ---->
O(|E|) grade memory + bounded local support.
```

每边 ancilla 版本不是新的正性定理；它只是把同一个乘法 grade 分布存储。

### U5-G.8 projection、fugacity 与约化

#### 全 trace

(U5.11) 是对所有 ancilla occupations 求 trace，逐 history 非负。

#### 全占据 projection

令

```text
P_occ = product_g n_(a_g).
```

在此 sector，

```text
V_e -> -r_e Gamma(B_e),
P_occ H_U5 P_occ
 -> sum_e q_e r_e Gamma(B_e).                          (U5.16)
```

这精确回到已完成的 graded-transposition Hamiltonian，只是 coupling
改成 `q_e r_e>0`。其 CT Taylor sign 与 determinant grade 相消。

#### 全空 projection

在所有 ancillas 为空的 sector，

```text
H_U5 -> -sum_e q_e Gamma(B_e),
```

该 sector 一般不具备同一正性证书。不能因为 full trace 正就声称每个
superselection sector 都正。

#### 正 fugacity family

因为所有 `n_(a_g)` 守恒，可考虑 weighted trace

```text
Z(x) = Tr[product_g x_g^(n_a_g) exp(-beta H_U5)].
```

history factor变为

```text
product_g [1+x_g(-1)^(k_g)R_g].                       (U5.17)
```

记第 `g` 组中最小的 dilation 为

```text
r_(g,min) = min_(e:alpha(e)=g) r_e.
```

任意深度正性的精确安全边界是

```text
x_g >= 1/r_(g,min).                                  (U5.18)
```

因为 `k_g` 为奇数时 `R_g>=r_(g,min)`，所以
`1-x_g R_g<=0`；偶数时 `1+x_g R_g>0`。每个 factor 的 sign
仍为 `(-1)^(k_g)`。这个边界也是紧的：若
`x_g<1/r_(g,min)`，只取达到最小 dilation 的那条边一次，就得到负权见证。

因此 `x_g>=1` 是一个简单但不必要地保守的充分条件；某些
`x_g<1` 仍严格安全。等价地，可以加入守恒的 ancilla chemical potential，
但允许的正负区间必须用 (U5.18) 而不是只凭 `mu_g` 的符号判断。

### U5-G.9 最小可执行实例

最小非二分测试可取 physical triangle：

```text
V={0,1,2},
E={(0,1),(1,2),(2,0)},
r_e>1, q_e>0.
```

三个直接实现：

1. 一个全局 ancilla：总计 `4` 个 fermion modes；
2. 每条 edge 一个 ancilla：总计 `6` 个 fermion modes；
3. 两组 ancilla：例如两条 edges 共享一个 grade mode，第三条独立。

临时精确回归已对这三种分组分别枚举 `1092` 条、深度不超过 `6` 的 histories，
未出现负权。一般结论仍由 (U5.13)--(U5.15) 给出，不依赖这些样本。

### U5-G.10 最快已知类排重和判定

最快排重顺序：

1. `r_e=1`：直接标记为已知 `su(1|1)` graded permutation；
2. 全占据 projection：调用现有
   `majorana_reflection_certificate()`，它给出负半定 centered
   one-body kernel 与全吸引 density couplings；
3. full model：按守恒 ancilla occupations 分块，识别为 annealed/static
   binary-charge direct sum，而不是一个新的 single-particle cone；
4. 检查是否只是第二共轭 flavor 或 determinant modulus square；
5. 对小图枚举固定 Fock sign gauges，判断是否另有普通 stoquastic reduction。

当前可安全陈述：

```text
完整 Hermitian model：是
正 scalar coefficients：是
任意深度证书：是
全局 ancilla 版本几何局域：否
每边 ancilla 版本几何局域：是，但 ancilla 数 O(|E|)
全占据 sector：已知 Majorana-reflection-positive
新矩阵正性机制：否，仍是 graded monomial factorization
full model 是否为新的 Hamiltonian family：需文献排重
层级：L1；全占据 projection 为已知 L2 reduction
```

不能把“每边 ancilla 后变局域”表述成新的 sign-free theorem；真正新增的只是一个
完整、局域可执行的 ancilla Hamiltonian realization。

---

## 两张卡的边界对照

| 项目 | U2-W Wilson gauge | U5-G grade charges |
|---|---|---|
| Hilbert 扩张 | 每条 edge 一个 qubit + Gauss projection | 每个 grade group 一个 conserved fermion |
| Hamiltonian | Hermitian | Hermitian |
| scalar coefficients | `t_e,K_p>=0` | `q_e>0` |
| 权重对象 | constrained worldline / transfer trace | Gaussian-vertex Fock trace |
| 任意深度来源 | 每个 code-space vertex 逐元非负 | monomial cycle grade × ancilla factors |
| 非常规代价 | fermion 表示含 Wilson string | global mode 高连接度或 `O(|E|)` ancillas |
| 最快约化 | stoquastic link-spin model | occupied sector 属于已知 Majorana 类 |
| 当前层级 | L1 + L2 | L1，projected sector 为已知 L2 |

两张卡都是真正完整的模型，但都没有改变当前“确认的新无符号物理类为零”的计数。
