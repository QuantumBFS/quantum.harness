# 非常规模型发现主线：先保正性，再追问物理性

更新时间：2026-07-29

状态：正式研究方向与证据标准；第一批结果见
[非常规模型第一批结果](UNCONVENTIONAL_MODEL_BATCH1_RESULTS.md)。

## 一句话目标

从已经严格成立的正性矩阵类反推大量完整但可能非常规的 Hamiltonian/transfer
models。第一阶段不再要求短程、几何局域、Hermitian 单时间片或普通物质自由度；
得到严格无符号模型以后，再研究它是否能通过相似变换、对偶、投影、积分掉 ancilla、
基变换或低能约化变成更有物理意义的系统。

这条线与合作者的 non-induced exterior-cone 大筛选分工：

```text
合作者：继续发现新的底层正锥和筛选候选；
本分支：开采已有严格正性类的非常规模型与物理约化。
```

不重复实现对方的 exterior candidate grammar、sharding 或 pressure scan。

## 为什么放宽物理限制

此前采用的升级标准过早同时要求：

```text
短程 + 局域 + Hermitian + 普通 HS + 立即可解释的材料模型。
```

这会在矩阵正性已经成立时，因最直接物理映射不够漂亮而停止。例如：

- tensor-square 的一般维数版本有严格任意深度正性，但辅助场绑定整行/整列；
- gauge/cocycle 能逐跳精确消号，但需要 system-size Wilson string；
- odd fixed-partition block-TN 的抽象定理成立，自然局域 crossed-partition 闭包失败；
- graded monomial 的全局 grade ancilla 是严格的，但不是普通局域物质模式；
- TN 在“半群顺序”中是局域路径，嵌入目标几何后可以表现为长程 hopping；
- 非对称 TN 时间片本身非 Hermitian，却可组成 Hermitian 正系数物理顶点。

这些不应直接升级成新物理类，但也不应因第一种映射不自然就停止开采。

## 第一阶段允许什么

允许的模型包括：

1. **长程 Hermitian**：hopping、density coupling 或多体顶点的作用距离随系统增长；
2. **集体/子系统作用**：一个辅助场同时耦合整行、整列、一个 flavor sector 或全局荷；
3. **准 Hermitian / pseudo-Hermitian**：`H` 非 Hermitian，但存在正定 `eta` 满足
   `H^dagger eta = eta H`，从而与 Hermitian Hamiltonian 相似；
4. **实谱非厄米**：先给出可执行的实谱或等谱证书，再研究 Hermitian partner；
5. **非局域相似变换**：允许局域非厄米模型对应长程 Hermitian 模型，或反向对应；
6. **Wilson/parity strings**：相关 hopping 可以带随路径增长的占据或 gauge string；
7. **全局或受约束 ancilla**：允许 superselection sector、投影后 Hilbert 空间和
   Gauss constraints；
8. **多体有效门**：允许 `-log` 一个正 transfer gate 后产生任意阶密度相互作用；
9. **Floquet/nonunitary transfer model**：只要被研究对象和权重定义清楚；
10. **非标准空间解释**：product graph、Fock graph、synthetic dimension、flavor-space
    locality 都可作为第一阶段的几何。

## 仍然不能放松的硬条件

“放开物理性”不等于放开证据。每个候选至少必须给出：

```text
1. 完整模型或 transfer operator；
2. 明确的 partition function / QMC weight；
3. 每个辅助场或顶点的正 scalar coefficient；
4. 任意深度非负证明，或清楚标记为有限深度候选；
5. 生成元、指数或微字分解的可执行证书；
6. Hermitian、准 Hermitian、实谱或一般非厄米中的准确分类；
7. 与 TN、split、Kramers、Majorana、stoquastic、模平方等已知机制的关系；
8. 相似变换若被使用，必须给出 `S`、条件数、系统尺寸标度和是否保持局域性；
9. 不能把“与一个已知模型相似”重新包装成新正性机制；
10. 数值幸存不能冒充任意深度结论。
```

若模型非 Hermitian，不允许只展示几个实本征值。至少需要以下之一：

- 显式正定 metric `eta`；
- 显式相似变换 `h=S H S^-1` 且 `h=h^dagger`；
- 一般尺寸的解析实谱证明；
- 明确承认它是一般非厄米 transfer model，不声称封闭量子 Hamiltonian。

## 三层成果口径

每个对象分层记录，避免再次把“矩阵成功”和“物理发现”混在一起：

### L1：严格非常规无符号模型

模型完整，权重任意深度非负，但可能长程、全局约束或非厄米。

### L2：可约化模型

给出精确变换，把 L1 对象映射成以下至少一种：

- Hermitian 但长程；
- 局域但非 Hermitian 且实谱；
- 受约束局域 gauge model；
- 某个物理低能 sector；
- 可采样的有限体/集体相互作用模型。

### L3：物理候选

进一步具有清晰参数区间、热力学极限、可测 observable、算法优势和未被已知无符号类
覆盖的证据。只有 L3 才参与“新的无符号物理类”计数。

## 第一批来源池

### U1. Tensor-square 集体密度模型

保持

```text
B_s = X_s tensor X_s
```

的严格闭包，接受一个辅助场同时控制 product lattice 的整行/整列。优先反推

```text
H_int = -(1/dt) log cosh(Q),
Q = sum_(ij) (u_i+u_j) n_(ij),
```

以及多个受控集体荷的正场分解。研究 Fourier/synthetic-dimension 变换后能否获得
较自然的 subsystem-symmetric、长程 Hermitian 或局域非 Hermitian partner。

### U2. Wilson-string gauge Hamiltonian

保留 gauge/cocycle 已证明的精确补偿 phase，不再因 string 长度增长立即淘汰。把
非局域 string Hamiltonian 写完整，并检查：

- 是否在另一 gauge fixing 中变成局域；
- 是否等价于已知 Jordan--Wigner/exact bosonization；
- 加入动力学 gauge 项后是否仍逐构型正。

### U3. Fixed-partition odd block-TN

不再要求每个空间局域块拥有独立 partition。允许全局 flavor partition、dense
inter-block hopping 和 synthetic dimensions，从严格 block-TN 定理反推 Hermitian
正和顶点。自然 crossed-partition 反例仍保留，不能被绕过或删除。

### U4. TN/graded 的准 Hermitian 相似轨道

从严格正的 TN 或 graded transfer atoms 出发，系统搜索固定非酉 `S`：

```text
B_s' = S B_s S^-1.
```

权重和任意深度正性保持不变。目标不是把固定相似轨道冒充新矩阵类，而是寻找：

```text
原模型：Hermitian 但长程/全局
相似模型：局域非 Hermitian、实谱
```

或反向的 locality tradeoff，并记录 metric `eta=S^(-dagger)S^-1`。

### U5. 全局 grade-ancilla 与投影模型

保留 graded monomial 的共享守恒 ancilla，把它明确当作全局算法/规范模式。探索固定
ancilla sector、投影 trace、多个 grade charges 和非局域 Hermitian partner；同时
保留其已知 Majorana-reflection 归属，只有新的 projected subclass 才可能升级。

### U6. 正 transfer gate 的 `-log` 模型

对任意已有正系数 Gaussian sum

```text
G = sum_s p_s Gamma(B_s),  p_s>0,
```

若 `G` 为正定 Hermitian，定义

```text
H_eff = -(1/dt) log G.
```

允许 `H_eff` 包含长程和任意阶多体项。先得到精确/高精度的 Fock-space
Hamiltonian，再寻找低秩、稀疏、对称或准局域结构。

## 执行漏斗

```text
严格正性来源
→ 自动生成完整 Fock/transfer model
→ Hermiticity / pseudo-Hermiticity / spectrum 分类
→ 作用支持、体数和系统尺寸标度
→ 固定相似变换、对偶、投影和 Fourier 约化
→ 已知类排重
→ 保留 L1/L2；只有满足完整物理标准才升级 L3
```

初筛优先使用 4–8 模式精确代数或高精度矩阵，不需要超算。只有出现能扩展到系统尺寸且
有限深度未能判定的候选，才进入大规模计算。

## 第一轮交付

已完成并汇总到
[非常规模型第一批结果](UNCONVENTIONAL_MODEL_BATCH1_RESULTS.md)：

1. 八种非常规模型构造，覆盖 U1–U6；
2. tensor-square、odd block-TN、grade-charge 等完整 Hamiltonian/transfer MWE；
3. Stark 链的显式正 metric、相似变换和条件数证书；
4. 每个模型的支持范围、体数、Hermiticity、L1/L2/L3 和已知类标签；
5. 六个 oracle 模块和对应自动回归；
6. “值得排重 / 已知约化 / 校准对象”的统一结果表。
