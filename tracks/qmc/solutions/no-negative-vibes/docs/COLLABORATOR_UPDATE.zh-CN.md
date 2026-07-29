# 无符号 QMC challenge：合作者进展说明

更新时间：2026-07-29

## 7 月 29 日最新收缩

首批非常规模型的三个优先候选已完成解析排重：

- `adjoint lift X tensor X^(-T)` 的整个族位于固定 `O(p,q)` 恒等连通分支，padding
  后就是已知 split-orthogonal 机制，关闭为新正性机制；
- grade-charge full Hamiltonian 是所有守恒 ancilla-bit 扇区的静态直和，ancilla
  没有动力学，降级为方法工具；
- tensor-square 权重可精确分解为
  `|det(I+iX)|^2 det(I+Lambda^2 X)^2`，因此不是不可约的新 determinant 机制；
  但 `m=3` 完整表示的固定伪正交度量线性系统满秩，排除了最简单的固定
  `O(p,q)` 解释，故只保留其多通道 Hamiltonian 的物理和 Majorana/Pfaffian 排重。

同一个 Stark 非厄米链既有对角 Hermitian partner，也可经任意 unitary 换基得到长程
partner，所以该路线只作方法校准。总集成分支完整回归当前为 `370 passed`。详见
[三个候选的排查结果](THREE_CANDIDATE_AUDIT_RESULTS.md)。

## 一句话状态

我们已经累计检查 4,044,000 个主权重，另做 640 条宇称分辨 Majorana 历史；每条历史
分别计算 even、odd 和完整 Fock 迹。我们已完成经典群、标准 Hermitian AZ、Majorana 双锥、
15 个新半群候选和七个 AZ 幸存类自然半群锥的系统排查。我们找到一个有一般证明的
恒正矩阵类：三对角 Metzler
路径生成元的指数乘积全非负，因此任意维数、任意时间片都有 `det(I+D)>=1`。它已映射到
开放 Hubbard 链和单 flavor 排斥 `t-V` 链的 HS 时间片。现在又得到排斥 `t-V` 局部
键门的精确非对称 TN 高斯分解，而且三站点重叠键无法由一个固定度量共同 Hermitian 化；
因此 TN 已经成为真实辅助场算法，不再只是抽象矩阵类。但一维开边界无符号本身已知，
目前仍不能声称发现了新 Hamiltonian。另一方面，任意两个不同旋转的 split cones 已由
显式两层反例完全关闭。BDI/AII/DIII/CII 的自然数守恒锥也完成第一轮：真正放松已知
对称的四项均产生负权或复权，三个零失败项仍只是已知 split/Kramers 机制。最新一轮又
找到有一般证明的奇数阶 positive-monomial / block-TN 路由半群；但它最自然的局域闭包
已被两个合法时间片的精确反例 `det(I+XR)=-2` 关闭。抽象固定分区定理仍正确，不能直接
升级为局域无符号模型。当前尚未关闭的具体方向是在 canonical convention 下观察到的
Majorana 宇称分辨 period-4 数值猜想。

## 已经完成

1. 建立稳定权重 oracle：
   - 计算 `det(I + exp(A_1)...exp(A_L))`；
   - 直接计算 Majorana Fock/Spin 迹并保留 determinant 平方根的符号分支；
   - 区分正、负、零、复相位和数值不确定；
   - 对 Fock 乘积逐层正数归一化，对病态 determinant 只记录相位/对数并标记不可用检查；
   - 每个参数格保存种子、结构残差和反例。
2. 建立 59 个 determinant 结构生成器：
   - 15 个经典群/李代数候选；
   - 10 个 AZ Hermitian 时间片类；
   - 15 个路径、图、混合锥和分块半群候选/对照。
   - 7 个 BDI/AII/DIII/CII 自然半群锥候选/对照。
   - 12 个 odd-monomial、公共范数、reciprocal、`D_4` 和可交换代数激进候选/对照。
3. 完成八轮主扫描和一轮宇称 survey：
   - `classical-groups-v1`：900 格、900,000 个乘积；
   - `az-tenfold-hermitian-v1`：720 格、720,000 个乘积。
   - `majorana-shared-reality-cones-v2`：1,792 格、448,000 个直接 Fock 迹；
   - `majorana-small-angle-stress-v1`：840 格、252,000 个直接 Fock 迹。
   - `frontier-semigroups-v1`：1,440 格、720,000 个行列式；
   - `frontier-mixed-split-stress-v1`：672 格、672,000 个行列式。
   - `az-survivor-cones-v1`：560 格、140,000 个行列式。
   - `speculative-structures-v1`：960 格、192,000 个行列式。
   - `majorana-parity-v1`：640 条历史，每条计算两个 sector traces 和一个完整 Fock 迹。
4. 加入 80 位任意精度反例重放、开放 Hubbard/`t-V` 链 HS 最小实现、精确非对称键门
   分解、graded-monomial 的 Majorana 包含证书、block-TN 局域闭包精确反例和最新三个
   候选审计证书；358 个自动测试全通过。

## 当前最重要的结果

### 经典群

- 精确或数值排除：`SL(2/3,R)`、`Sp(2/4,R)`、`SU(1,1)`、`SU(2,1)`、`SU(3)`；
- `U(2)`、`U(1,1)` 的单 flavor determinant 一般为复数；
- `U(p,q)` 相位已经理论分类：
  `arg det(I+D)=arg det(D)/2 mod pi`，连续中心相位之外只剩二值正负号；
- 零负例项都能约化到已知 split-orthogonal、共轭配对或 Kramers/Majorana 机制。

### AZ 十类

统一采用 `4 x 4` Hermitian 时间片和标准 TRS/PHS/手征约束：

| 类 | 结果 |
|---|---|
| A、D、C | 从乘积深度 3 开始出现复权，并有精确三因子证书 |
| AI、AIII、CI | 从深度 3 开始出现负权，并有精确三因子证书 |
| BDI | 数值存活，但就是已知 split-orthogonal 块结构 |
| AII、DIII、CII | 数值存活，但都有 `T^2=-1` 的已知 Kramers 机制 |

因此普通 Hermitian AZ 十类没有给出新的恒非负类：六类精确失败，四类约化到已知机制。
对 D/C 等 BdG 类，这里排除的是当前 determinant 命题；完整物理权重仍可能涉及 Pfaffian 或
平方根分支，不能过度解释。

随后对 BDI/AII/DIII/CII 的自然数守恒半群锥做了 14 万权重专用筛选：

- BDI 两面 contraction/expansion 锥出现 4,219 个负权；
- DIII 粒子-空穴保持锥从深度 3 开始产生复权；
- generic DIII/CII positive direction 从深度 2 开始产生复权；
- BDI fixed cone、AII Kramers algebra 和 CII Kramers-preserving cone 零稳定失败，
  但它们分别严格保留已知 split 或 Kramers 机制。

四个最小深度代表反例已用 80 位矩阵指数确认；BDI 两面锥还得到两层解析反例
`16(1-q^2)<0`。本轮不覆盖完整 pairing/Pfaffian/Spin-trace 问题。

### Majorana 双锥

- 两个已知 Majorana 正锥共享同一个 `J1` 实结构，只旋转 `J2` 收缩方向；
- 448,000 个宽扫权重中有 19,128 个负权，0 复权，说明公共 `J1` 只保证实权；
- 已有深度二精确证书 `p=2-2*cosh(1)<0`，但 determinant 为 `p^2>0`；
- 小角压力测试追加 252,000 个权重，角度 `0.4` 的 4/6-Majorana 负例均由 80 位 Fock
  重放确认；
- 找到 4-Majorana、两层的解析反例族
  `p(theta,q)=-4*sin(theta)*sinh(q)^2<0`，对每个 `0<theta<pi` 成立；
- 因此不存在只由夹角控制的完整双锥恒正小角区；此前 `0.05–0.3` 随机零命中只是抽样漏掉
  秩一零权边界。

### 新半群与全非负路径

- 三对角 Metzler 路径的矩阵指数是全非负矩阵，乘积仍全非负；
- `det(I+D)` 等于全部主子式之和，所以一般性地有 `det(I+D)>=1`；
- 类中同时包含 `+D/-D`，已严格排除固定 Kramers、split/contraction metric；标准
  Majorana 加倍后也排除 Wei 2024 的固定 `J_2` 条件，包括固定复正交换基；
- 环、星形、稠密 Metzler 图和逐片独立符号规范均已出现负权；
- 掺杂开放 Hubbard 链和单 flavor 排斥 `t-V` 开链的离散 HS 时间片都落入该类；
- 任意两个不同旋转 split cones 的完整并集都有
  `w=16[1-q^2 sin^2(theta)]<0` 的两层反例；
- 139.2 万个新权重的累计 CPU 时间约 15 分钟，说明当前不需要超算。

### 精确非对称 `t-V` 键门

- 对 `h_b=-t(c_1^dag c_2+h.c.)+Vn_1n_2-mu_b(n_1+n_2)`，构造了两个显式
  `2 x 2` TN 矩阵 `B_+/-`，严格满足
  `exp(-dt h_b)=[Gamma(B_+)+Gamma(B_-)]/2`；
- 这不是小步长近似，每个局部键门恒等式在有限 `dt` 上精确；
- 一个连续参数 `0<=kappa<1` 控制左右 hopping 的非对称性，但不改变物理门；
- 单独一个键仍共享非对角正定度量；三站点重叠键的共同对称 intertwiner 空间则为零，
  已防止把孤立键假象误报成新机制；
- 四站点 9 个依次键门的 `2^9=512` 个场构型全部满足单行列式严格正；另一组三站点枚举
  配分函数对 `kappa=0,0.3,0.6,0.9` 数值不变；
- 连续 TN 切锥只能是三对角 Metzler，说明环、分支或远邻 hopping 不能靠裸 TN 动能
  直接加入；
- TN 高斯算符在 Fock 基中的矩阵元都是非负子式，普通远邻 hopping 却会随中间占据数
  翻转符号，所以任意 TN 高斯正和也不能直接产生环或真正分支；
- 即使允许每个粒子数扇区独立做固定符号规范，2–6 站点全部连通图穷举仍只有开放路径
  幸存：`1,3,12,60,360=N!/2`，环和三支星形都有二粒子交换负闭环；
- 普通 ancilla 的 Fock 投影/偏迹仍保持逐元非负，也不能修复远邻 hopping；
- 下一突破口已收窄为非平凡 gauge/ancilla 编码、带宇称串相关 hopping、
  pairing/Majorana 或更大半群。

### 激进候选首批

- 12 族、192,000 个 determinant 权重的正式扫描全部完成；
- 奇数阶 positive-monomial 满足
  `det(I+B)=product_C(1+product_{i in C}d_i)>0`，是任意深度的一般证明；
- 三循环已有负的非主子式，所以它不属于 ordinary TN；类包含任意正对角矩阵，也排除
  固定 Kramers 和公共范数收缩；
- 奇数循环的固定分区 block-TN 推广同样严格恒正；但局域站点内 `C3` 路由与跨站
  flavor-preserving TN hopping 使用交叉分区，已经在两站点、三 flavor、两层得到
  `det(I+XR)=-2`，因此最自然的局域闭包不成立；
- 偶阶 `V4` 路由已有精确 `-9/4` 反例；moving metric、双向 reciprocal coupling 和
  near-commuting 并集分别产生 4,542、3,894、846 个负权，代表例均由 80 位重放；
- fixed `l_infinity`、reciprocal-parabolic 和 commuting 类严格恒正，但分别属于公共
  收缩、三角因子化和可积对照；`D_4` Lusztig 则约化到已知 split `SO(4,4)`；
- 另做 640 条 Majorana 宇称分辨历史：在 canonical `J1/J2` 和当前 Jordan-Wigner
  取向下，`m=2..6` 中猜想扇区 `pi_*=(-1)^[m(m+1)/2]` 全部正，互补扇区累计观察到
  204 个 float64 负权。这个 convention-dependent 猜想尚无证明，互补负例也尚未做
  任意精度重放。

### Graded monomial crossing：正确，但不是新物理类

- 已证明 `D_ii>=1` 时 `sgn(P) det(I+P D)>=0`，并构造 dilated transposition
  的逐历史正权、局域吸引 spinless 模型和单 grade-ancilla 实指数 lift；
- 三角形模型不能靠站点 `+/-` gauge 变成固定 Fock 基 stoquastic，这说明它不是原
  pure-TN 路径模型；
- 但 `r=1` 局部顶点精确等于已知 `su(1|1)` graded permutation；
- 更决定性的是，centered 后每条边的一体 kernel 本征值为
  `-q(r-1)^2/2`、`-q(r+1)^2/2`，且相互作用为负，因此整个 Hamiltonian 明确属于
  Wei et al. 2016 的 Majorana reflection positivity 类；
- monomial 矩阵的 cycle-factor 又是已知特征多项式公式的直接推论；
- 结论降为 `known-monomial-factorization / known-majorana-subclass /
  useful-reformulation`：保留特殊 CT 展开和可执行证书，不声称新的矩阵定理或
  无符号 Hamiltonian 类。

## 我们没有声称什么

- 没有声称随机扫描能证明非负；
- 没有声称已经发现新无符号 QMC 类；
- 没有把复权自动等同于所有 BdG QMC 表述都有相位问题；
- 没有把 TN 路径数学类直接称为新物理发现；开放一维模型本身已有无符号先例。

## 下一步建议

不再重复扫描整个命名群、普通 AZ 类、自然数守恒 AZ metric cone 或同分布双锥。下一步
围绕尚未关闭的候选闭环：

1. 把 graded monomial 作为已知类约化案例、把 odd block-TN 局域映射作为精确失败案例
   存档，不再投入新物理类的主线资源；
2. 从 2016 Majorana reflection-positivity 证明中推导或推翻受保护宇称公式；
3. 若该方向不能闭环，再进入 spinor-Metzler、非诱导 exterior-cone 和 gauge/ancilla
   编码。

任何新候选按以下漏斗处理：

```text
定义与已知类排重
→ 小维度/深度反例搜索
→ 失败项精确化
→ 幸存项扩大扫描
→ 数学证明
→ Hamiltonian 与 HS 映射
```

只有候选格扩展到一万以上或预计达到 `10^8` 次检验后，才需要迁移到超算 CPU 任务数组。

## 查看入口

- [总入口](../START_HERE.md)
- [成果总账](RESULTS_LEDGER.md)
- [主办方方向完成度](ORGANIZER_DIRECTION_AUDIT.md)
- [下一阶段研究计划](NEXT_RESEARCH_PLAN.md)
- [全非负路径类](TOTAL_NONNEGATIVE_PATH_CLASS.md)
- [TN 新机制审计](TN_NOVELTY_AUDIT.md)
- [TN 物理映射前沿](TN_PHYSICAL_MAPPING_FRONTIER.md)
- [复合矩阵规范 no-go](COMPOUND_GAUGE_NO_GO.md)
- [新半群初筛结果](FRONTIER_SEMIGROUP_RESULTS.md)
- [AZ 幸存类半群锥](AZ_SURVIVOR_CONE_RESULTS.md)
- [激进候选首批结果](SPECULATIVE_STRUCTURE_RESULTS.md)
- [graded monomial 结果与排重](GRADED_MONOMIAL_RESULTS.md)
- [odd block-TN 局域性审计](ODD_BLOCK_TN_LOCALITY_AUDIT.md)
- [激进候选清单](SPECULATIVE_CANDIDATE_BATCH.md)
- [Majorana 双锥结果](MAJORANA_CONE_RESULTS.md)
- [AZ 十类结果](AZ_TENFOLD_RESULTS.md)
- [经典群基线](BASELINE_RESULTS.md)
- [精确证书说明](EXACT_CERTIFICATES.md)
- [算力策略](COMPUTE_STRATEGY.md)

生成的完整逐格数据按 harness 约定保存在本地 `tracks/qmc/results/no-negative-vibes/`，不提交
Git；协议、汇总数字、精确证书和复现代码均保存在工作分支中。
